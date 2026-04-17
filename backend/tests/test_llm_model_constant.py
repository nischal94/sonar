from app.config import OPENAI_MODEL_EXPENSIVE


def test_expensive_tier_is_gpt_5_4_mini():
    """Project-wide LLM expensive tier is gpt-5.4-mini as of the Phase 2
    Wizard slice. Context: sonar/CLAUDE.md routing rule + wizard-decisions.md
    §2. If you're changing this, update the routing rule in CLAUDE.md and
    every caller that imports the constant."""
    assert OPENAI_MODEL_EXPENSIVE == "gpt-5.4-mini"


def test_context_generator_uses_constant():
    """context_generator must not hardcode model names — use the constant
    so a single edit updates every caller at once."""
    import app.services.context_generator as cg
    import inspect
    source = inspect.getsource(cg)
    assert "gpt-4o" not in source, (
        "context_generator.py still hardcodes 'gpt-4o' — migrate to "
        "OPENAI_MODEL_EXPENSIVE from app.config"
    )
