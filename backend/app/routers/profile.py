from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func, text
from pydantic import BaseModel, HttpUrl
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
