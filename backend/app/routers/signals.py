from __future__ import annotations
import json
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.signal_proposal_event import SignalProposalEvent
from app.models.user import User
from app.routers.auth import get_current_user
from app.rate_limit import limiter
from app.schemas.wizard import (
    ProposeSignalsRequest,
    ProposedSignal,
    ProposeSignalsResponse,
)
from app.services.llm import get_llm_client, LLMProvider
from app.config import OPENAI_MODEL_EXPENSIVE
from app.prompts.propose_signals import (
    PROMPT_VERSION,
    SYSTEM_PROMPT,
    build_user_message,
)

router = APIRouter(prefix="/workspace/signals", tags=["signals"])


def _strip_markdown_fence(raw: str) -> str:
    """Reuse the fence-strip pattern from context_generator.py — some models
    wrap JSON output in ```json ... ``` despite Structured Outputs."""
    s = raw.strip()
    if s.startswith("```"):
        s = s.split("\n", 1)[1] if "\n" in s else s[3:]
        if s.endswith("```"):
            s = s[:-3]
    return s.strip()


@router.post("/propose", response_model=ProposeSignalsResponse)
@limiter.limit("3/minute")
async def propose_signals(
    request: Request,  # required by @limiter.limit
    body: ProposeSignalsRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    llm: LLMProvider = Depends(get_llm_client),
):
    user_msg = build_user_message(body.what_you_sell, body.icp)
    # Compose the prompt for the existing `complete(prompt, model)` signature.
    # Two-part prompt delimited by role markers so the system/user separation is preserved.
    prompt = f"<|system|>\n{SYSTEM_PROMPT}\n<|user|>\n{user_msg}"
    raw = await llm.complete(prompt, model=OPENAI_MODEL_EXPENSIVE)
    try:
        payload = json.loads(_strip_markdown_fence(raw))
        signals_raw = payload["signals"]
        signals = [ProposedSignal(**s) for s in signals_raw]
    except (json.JSONDecodeError, KeyError, ValueError, TypeError) as exc:
        raise HTTPException(status_code=502, detail=f"LLM output parse failed: {exc}")

    event = SignalProposalEvent(
        workspace_id=current_user.workspace_id,
        prompt_version=PROMPT_VERSION,
        what_you_sell=body.what_you_sell,
        icp=body.icp,
        proposed=[s.model_dump() for s in signals],
    )
    db.add(event)
    await db.commit()
    await db.refresh(event)

    return ProposeSignalsResponse(
        proposal_event_id=event.id,
        prompt_version=PROMPT_VERSION,
        signals=signals,
    )
