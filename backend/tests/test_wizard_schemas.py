import pytest
from pydantic import ValidationError
from app.schemas.wizard import (
    ProposeSignalsRequest,
    ProposedSignal,
    ProposeSignalsResponse,
    ConfirmSignalsRequest,
    ConfirmedSignal,
    ConfirmSignalsResponse,
)


def test_propose_request_requires_what_you_sell():
    with pytest.raises(ValidationError):
        ProposeSignalsRequest(icp="x")


def test_propose_request_icp_is_optional():
    req = ProposeSignalsRequest(what_you_sell="Fractional CTO services")
    assert req.icp is None


def test_proposed_signal_intent_strength_bounds():
    valid_phrase = "hiring a fractional CTO"
    valid_post = "We are looking for a fractional CTO to help us scale."
    with pytest.raises(ValidationError):
        ProposedSignal(
            phrase=valid_phrase, example_post=valid_post, intent_strength=1.5
        )
    with pytest.raises(ValidationError):
        ProposedSignal(
            phrase=valid_phrase, example_post=valid_post, intent_strength=-0.1
        )
    # 0 and 1 inclusive should work
    ProposedSignal(phrase=valid_phrase, example_post=valid_post, intent_strength=0)
    ProposedSignal(phrase=valid_phrase, example_post=valid_post, intent_strength=1)


def test_confirm_request_accepts_empty_lists():
    req = ConfirmSignalsRequest(
        proposal_event_id="00000000-0000-0000-0000-000000000000",
        accepted=[],
        edited=[],
        rejected=[],
        user_added=[],
    )
    assert req.accepted == []


def test_confirmed_signal_shape():
    sig = ConfirmedSignal(
        phrase="hiring a fractional CTO",
        example_post="We are looking for a fractional CTO to help us scale.",
        intent_strength=0.5,
    )
    assert sig.phrase == "hiring a fractional CTO"


def test_response_models_exported():
    # Smoke test: ensure response schemas are importable and constructible
    uuid_val = "00000000-0000-0000-0000-000000000000"
    propose_resp = ProposeSignalsResponse(
        proposal_event_id=uuid_val, prompt_version="v1", signals=[]
    )
    assert propose_resp.prompt_version == "v1"
    confirm_resp = ConfirmSignalsResponse(signal_ids=[], profile_active=True)
    assert confirm_resp.profile_active is True
