from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func, text
from pydantic import BaseModel, Field, HttpUrl
from app.database import get_db
from app.models.workspace import Workspace, CapabilityProfileVersion
from app.models.user import User
from app.routers.auth import get_current_user
from app.services.profile_extractor import (
    extract_capability_profile,
    extract_icp_and_seller_mirror,
)
from app.services.embedding import EmbeddingProvider, get_embedding_provider
from app.services.llm import LLMProvider, get_llm_client

router = APIRouter(prefix="/profile", tags=["profile"])


class ProfileExtractRequest(BaseModel):
    url: HttpUrl | None = None
    text: str | None = None


class ProfileExtractResponse(BaseModel):
    company_name: str
    capability_summary: str
    signal_keywords: list[str]
    version: int
    icp: str
    seller_mirror: str


class UpdateIcpRequest(BaseModel):
    # max_length ~4000 chars ≈ well under text-embedding-3-small's 8191-token
    # window and keeps a single request from burning unbounded LLM cost.
    icp: str | None = Field(default=None, max_length=4000)
    seller_mirror: str | None = Field(default=None, max_length=4000)


@router.post("/extract", response_model=ProfileExtractResponse)
async def extract_profile(
    body: ProfileExtractRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    emb: EmbeddingProvider = Depends(get_embedding_provider),
    llm: LLMProvider = Depends(get_llm_client),
):
    if not body.url and not body.text:
        raise HTTPException(status_code=400, detail="Provide url or text")

    profile = await extract_capability_profile(
        text=body.text,
        url=str(body.url) if body.url else None,
        llm_override=llm,
    )

    embedding = await emb.embed(profile.capability_summary)

    # Source text for ICP extraction: prefer the user-provided text; if only a
    # URL was given, the capability summary itself is a faithful summary of
    # what the crawler found and is a reasonable substitute.
    icp_source_text = body.text or profile.capability_summary
    icp_text, seller_mirror_text = await extract_icp_and_seller_mirror(
        source_text=icp_source_text,
        llm_override=llm,
    )
    icp_embedding = await emb.embed(icp_text)
    seller_mirror_embedding = await emb.embed(seller_mirror_text)

    # Deactivate previous active version
    await db.execute(
        update(CapabilityProfileVersion)
        .where(CapabilityProfileVersion.workspace_id == current_user.workspace_id)
        .where(CapabilityProfileVersion.is_active.is_(True))
        .values(is_active=False)
    )

    # Count existing versions to determine next version number
    count_result = await db.execute(
        select(func.count())
        .select_from(CapabilityProfileVersion)
        .where(CapabilityProfileVersion.workspace_id == current_user.workspace_id)
    )
    version_number = (count_result.scalar() or 0) + 1

    version = CapabilityProfileVersion(
        workspace_id=current_user.workspace_id,
        version=version_number,
        raw_text=profile.capability_summary,
        source="url" if body.url else "document",
        signal_keywords=profile.signal_keywords,
        anti_keywords=profile.anti_keywords,
        icp=icp_text,
        seller_mirror=seller_mirror_text,
        is_active=True,
    )
    db.add(version)

    await db.execute(
        update(Workspace)
        .where(Workspace.id == current_user.workspace_id)
        .values(capability_profile=profile.capability_summary)
    )

    await db.flush()

    # Store pgvector embeddings via parameterized raw SQL (single round-trip)
    await db.execute(
        text(
            "UPDATE capability_profile_versions "
            "SET embedding = :emb, "
            "    icp_embedding = :icp_emb, "
            "    seller_mirror_embedding = :mirror_emb "
            "WHERE id = :id"
        ),
        {
            "emb": str(embedding),
            "icp_emb": str(icp_embedding),
            "mirror_emb": str(seller_mirror_embedding),
            "id": str(version.id),
        },
    )

    await db.commit()

    return ProfileExtractResponse(
        company_name=profile.company_name,
        capability_summary=profile.capability_summary,
        signal_keywords=profile.signal_keywords,
        version=version_number,
        icp=icp_text,
        seller_mirror=seller_mirror_text,
    )


@router.post("/update-icp")
async def update_icp(
    body: UpdateIcpRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    emb: EmbeddingProvider = Depends(get_embedding_provider),
):
    """Update the active CapabilityProfileVersion's ICP and/or seller_mirror text.

    Re-embeds whichever fields are provided. At least one field must be a
    non-whitespace string. The active version is identified by
    workspace_id + is_active=True.
    """
    # Normalize: strip whitespace, treat "" and "   " as equivalent to missing.
    # Pydantic's max_length guards the upper bound; this guards the lower.
    icp_clean = body.icp.strip() if body.icp else None
    mirror_clean = body.seller_mirror.strip() if body.seller_mirror else None
    if not icp_clean and not mirror_clean:
        raise HTTPException(
            status_code=400,
            detail="Provide at least one non-empty icp or seller_mirror",
        )

    # Resolve the active version id first
    id_result = await db.execute(
        select(CapabilityProfileVersion.id)
        .where(CapabilityProfileVersion.workspace_id == current_user.workspace_id)
        .where(CapabilityProfileVersion.is_active.is_(True))
    )
    version_id = id_result.scalar()
    if version_id is None:
        raise HTTPException(
            status_code=404, detail="No active capability profile found"
        )

    # Phase 1 — compute all embeddings FIRST, before any DB writes. If any
    # embed() call raises (network, 429, 500), no partial write escapes.
    # Do not re-order this block to interleave embeds with SQL writes.
    icp_embedding = await emb.embed(icp_clean) if icp_clean else None
    mirror_embedding = await emb.embed(mirror_clean) if mirror_clean else None

    # Phase 2 — issue all DB writes in the same transaction. SQLAlchemy
    # rolls back if any step below raises before commit.
    text_fields: dict = {}
    if icp_clean:
        text_fields["icp"] = icp_clean
    if mirror_clean:
        text_fields["seller_mirror"] = mirror_clean

    await db.execute(
        update(CapabilityProfileVersion)
        .where(CapabilityProfileVersion.id == version_id)
        .values(**text_fields)
    )

    set_clauses = []
    params: dict = {"id": str(version_id)}
    if icp_embedding is not None:
        set_clauses.append("icp_embedding = :icp_emb")
        params["icp_emb"] = str(icp_embedding)
    if mirror_embedding is not None:
        set_clauses.append("seller_mirror_embedding = :mirror_emb")
        params["mirror_emb"] = str(mirror_embedding)

    await db.execute(
        text(
            "UPDATE capability_profile_versions SET "
            + ", ".join(set_clauses)
            + " WHERE id = :id"
        ),
        params,
    )

    await db.commit()
    return {"ok": True}
