from __future__ import annotations
import json
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.signal import Signal
from app.models.signal_proposal_event import SignalProposalEvent
from app.models.user import User
from app.routers.auth import get_current_user
from app.rate_limit import limiter
from app.schemas.wizard import (
    ConfirmSignalsRequest,
    ConfirmSignalsResponse,
    ProposeSignalsRequest,
    ProposedSignal,
    ProposeSignalsResponse,
)
from app.services.embedding import get_embedding_provider, EmbeddingProvider
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
    # Send system + user as separate messages at the API boundary so user input
    # (in user_msg) cannot spoof the system role via `<|system|>`-style delimiter
    # strings. Per sonar/CLAUDE.md 'Prompt injection defense is mandatory' —
    # topological separation at the role level, not inline via text markers.
    # max_tokens=4096 accommodates worst-case 10-signal output with long
    # example_post bodies (up to 500 chars each × 10 + phrase + JSON structure
    # can exceed the default 2048 cap and cause truncated output → 502 parse fail).
    raw = await llm.complete(
        user_msg,
        model=OPENAI_MODEL_EXPENSIVE,
        system=SYSTEM_PROMPT,
        max_tokens=4096,
    )
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


@router.post("/confirm", response_model=ConfirmSignalsResponse)
async def confirm_signals(
    body: ConfirmSignalsRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    embed: EmbeddingProvider = Depends(get_embedding_provider),
):
    # Look up the telemetry event — must belong to the caller's workspace.
    result = await db.execute(
        select(SignalProposalEvent).where(
            SignalProposalEvent.id == body.proposal_event_id,
            SignalProposalEvent.workspace_id == current_user.workspace_id,
        )
    )
    event = result.scalar_one_or_none()
    if event is None:
        raise HTTPException(
            status_code=404, detail="Proposal event not found for this workspace"
        )
    # Idempotency guard: reject retries to prevent duplicate Signal rows and
    # clobbering of the telemetry breakdown. If the client genuinely wants to
    # re-wizard, they start a fresh /propose call (new proposal_event_id).
    if event.completed_at is not None:
        raise HTTPException(status_code=409, detail="Proposal event already confirmed")

    # Resolve final signal list from the three buckets (accepted / edited / user_added).
    # Rejected are just recorded; they don't produce signal rows.
    final_signals: list[dict] = []
    proposed = event.proposed  # list[dict] with the original LLM output

    for idx in body.accepted:
        if 0 <= idx < len(proposed):
            final_signals.append(proposed[idx])

    for pair in body.edited:
        final_signals.append(
            {
                "phrase": pair.final_phrase,
                "example_post": pair.final_example_post,
                "intent_strength": pair.final_intent_strength,
            }
        )

    for sig in body.user_added:
        final_signals.append(sig.model_dump())

    # Embed each confirmed signal's phrase and persist.
    signal_ids: list = []
    for s in final_signals:
        vector = await embed.embed(s["phrase"])
        row = Signal(
            workspace_id=current_user.workspace_id,
            phrase=s["phrase"],
            example_post=s["example_post"],
            intent_strength=s["intent_strength"],
            embedding=vector,
            enabled=True,
        )
        db.add(row)
        await db.flush()
        signal_ids.append(row.id)

    # Mark the telemetry event complete.
    event.accepted_ids = [str(i) for i in body.accepted]
    event.edited_pairs = [p.model_dump() for p in body.edited]
    event.rejected_ids = [str(i) for i in body.rejected]
    event.user_added = [s.model_dump() for s in body.user_added]
    event.completed_at = datetime.now(timezone.utc)

    await db.commit()

    # NOTE: marking the capability profile active is a placeholder until the
    # capability-profile-versions flow is extended. For the wizard-only scope,
    # profile_active=True is returned unconditionally once signals are persisted.
    return ConfirmSignalsResponse(signal_ids=signal_ids, profile_active=True)
