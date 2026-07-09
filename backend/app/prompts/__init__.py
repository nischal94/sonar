"""Shared utilities for prompt modules.

All LLM call sites that have a prompt module should call `log_prompt_call`
immediately after a successful LLM response so every real call is traceable
in structured logs.
"""

from __future__ import annotations

import logging
from typing import Any

_logger = logging.getLogger("app.prompts")


def log_prompt_call(
    feature: str,
    prompt_version: str,
    model: str,
    **extra: Any,
) -> None:
    """Emit a structured INFO log after a successful LLM call.

    Args:
        feature: Name of the feature / call site (e.g. "propose_signals").
        prompt_version: The PROMPT_VERSION constant from the prompt module.
        model: The model identifier used for this call.
        **extra: Optional context fields such as workspace_id.
    """
    payload: dict[str, Any] = {
        "feature": feature,
        "prompt_version": prompt_version,
        "model": model,
    }
    payload.update(extra)
    _logger.info("llm_call", extra={"prompt_log": payload})
