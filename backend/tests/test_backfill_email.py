import pytest
from app.models.workspace import Workspace
from app.workers.day_one_backfill import run_day_one_backfill
from tests.test_apify_service import FakeApify
from tests.test_day_one_backfill import _seed_workspace_with_connections


class FakeEmailSender:
    def __init__(self):
        self.calls: list[dict] = []

    async def send_backfill_complete(
        self, workspace: Workspace, profile_count: int
    ) -> None:
        self.calls.append(
            {
                "workspace_id": workspace.id,
                "profile_count": profile_count,
                "email": workspace.delivery_channels.get("email", {}).get("address"),
            }
        )


@pytest.mark.asyncio
async def test_backfill_sends_completion_email(db_session):
    ws = await _seed_workspace_with_connections(db_session, n_connections=2)
    ws.delivery_channels = {"email": {"address": "ops@example.com"}}
    await db_session.commit()

    apify = FakeApify(posts_per_profile=1)
    email = FakeEmailSender()

    await run_day_one_backfill(db_session, workspace_id=ws.id, apify=apify, email=email)
    await db_session.commit()

    assert len(email.calls) == 1
    assert email.calls[0]["email"] == "ops@example.com"
    assert email.calls[0]["profile_count"] == 2
