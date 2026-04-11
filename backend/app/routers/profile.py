from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func, text
from pydantic import BaseModel, HttpUrl
from uuid import UUID
from app.database import get_db
from app.models.workspace import Workspace, CapabilityProfileVersion
from app.models.user import User
from app.routers.auth import get_current_user
from app.services.profile_extractor import extract_capability_profile
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

    # Deactivate previous active version
    await db.execute(
        update(CapabilityProfileVersion)
        .where(CapabilityProfileVersion.workspace_id == current_user.workspace_id)
        .where(CapabilityProfileVersion.is_active == True)
        .values(is_active=False)
    )

    # Count existing versions to determine next version number
    count_result = await db.execute(
        select(func.count()).select_from(CapabilityProfileVersion)
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
        is_active=True,
    )
    db.add(version)

    await db.execute(
        update(Workspace)
        .where(Workspace.id == current_user.workspace_id)
        .values(capability_profile=profile.capability_summary)
    )

    await db.flush()

    # Store pgvector embedding via parameterized raw SQL
    await db.execute(
        text("UPDATE capability_profile_versions SET embedding = :emb WHERE id = :id"),
        {"emb": str(embedding), "id": str(version.id)}
    )

    await db.commit()

    return ProfileExtractResponse(
        company_name=profile.company_name,
        capability_summary=profile.capability_summary,
        signal_keywords=profile.signal_keywords,
        version=version_number,
    )
