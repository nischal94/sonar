import pytest
import jwt
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from app.config import get_settings

ALGORITHM = "HS256"


@pytest.mark.asyncio
async def test_register_and_login(client):
    resp = await client.post(
        "/workspace/register",
        json={
            "workspace_name": "Test Agency",
            "email": "owner@test.com",
            "password": "testpassword123",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert "workspace_id" in data

    resp = await client.post(
        "/auth/token",
        data={"username": "owner@test.com", "password": "testpassword123"},
    )
    assert resp.status_code == 200
    assert "access_token" in resp.json()


@pytest.mark.asyncio
async def test_get_current_user_rejects_token_missing_sub(client):
    """Regression test for issue #7: JWT decode must explicitly require
    `sub` via options={"require": [...]} so missing claims fail loudly
    with a PyJWTError instead of sneaking through as a silent KeyError."""
    secret = get_settings().secret_key
    token_without_sub = jwt.encode(
        {
            # No "sub" claim on purpose
            "workspace_id": str(uuid4()),
            "exp": datetime.now(timezone.utc) + timedelta(minutes=60),
        },
        secret,
        algorithm=ALGORITHM,
    )
    resp = await client.patch(
        "/workspace/channels",
        headers={"Authorization": f"Bearer {token_without_sub}"},
        json={"delivery_channels": {}},
    )
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid token"


@pytest.mark.asyncio
async def test_get_current_user_rejects_token_missing_exp(client):
    """Regression test for issue #7: JWT decode must explicitly require
    `exp` so tokens without an expiry are rejected at decode time."""
    secret = get_settings().secret_key
    token_without_exp = jwt.encode(
        {
            "sub": str(uuid4()),
            "workspace_id": str(uuid4()),
            # No "exp" claim on purpose
        },
        secret,
        algorithm=ALGORITHM,
    )
    resp = await client.patch(
        "/workspace/channels",
        headers={"Authorization": f"Bearer {token_without_exp}"},
        json={"delivery_channels": {}},
    )
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid token"


@pytest.mark.asyncio
async def test_register_endpoint_rate_limited_to_3_per_minute(client):
    """Per sonar/CLAUDE.md Security + issue #63: /workspace/register is
    rate-limited to prevent email-enumeration scraping. Per-IP limit is
    3/minute. The 4th request within a minute returns 429 regardless of
    whether the email is unique.

    Enumeration hardening (generic 201-response-on-duplicate) is NOT part
    of this test — it's a separate, bigger follow-up in #63 Piece 2."""
    for i in range(3):
        resp = await client.post(
            "/workspace/register",
            json={
                "workspace_name": f"Reg RL Test {i}",
                "email": f"rl{i}@test.com",
                "password": "testpassword123",
            },
        )
        assert (
            resp.status_code == 201
        ), f"request {i + 1} of 3 should succeed, got {resp.status_code}"

    resp = await client.post(
        "/workspace/register",
        json={
            "workspace_name": "Reg RL Test 4",
            "email": "rl4@test.com",
            "password": "testpassword123",
        },
    )
    assert (
        resp.status_code == 429
    ), f"4th request should be rate-limited (429), got {resp.status_code}"
    assert resp.json() == {"detail": "Too many requests"}
    assert resp.headers.get("Retry-After") == "60"


@pytest.mark.asyncio
async def test_login_endpoint_rate_limited_to_5_per_minute(client):
    """Per sonar/CLAUDE.md Security: /auth/token is rate-limited to prevent
    credential-stuffing and brute-force attacks. Per-IP limit is 5/minute.
    The 6th request within a minute returns 429 Too Many Requests
    regardless of whether the credentials are valid.

    NOTE: ASGITransport makes every test appear as the same client IP, so
    this test exercises the '5-then-429' counter behavior only — it does NOT
    prove per-IP isolation. Per-IP keying is a property of
    slowapi.util.get_remote_address and is validated by inspection, not here.
    """
    await client.post(
        "/workspace/register",
        json={
            "workspace_name": "Rate Limit Test",
            "email": "rl@test.com",
            "password": "testpassword123",
        },
    )

    for i in range(5):
        resp = await client.post(
            "/auth/token",
            data={
                "username": "rl@test.com",
                "password": "testpassword123",
            },
        )
        assert (
            resp.status_code == 200
        ), f"request {i + 1} of 5 should succeed, got {resp.status_code}"

    resp = await client.post(
        "/auth/token",
        data={
            "username": "rl@test.com",
            "password": "testpassword123",
        },
    )
    assert (
        resp.status_code == 429
    ), f"6th request should be rate-limited (429), got {resp.status_code}"
    # Body must NOT echo slowapi's default policy string; the custom handler
    # returns a generic message so attackers can't calibrate the window.
    assert resp.json() == {"detail": "Too many requests"}
    assert resp.headers.get("Retry-After") == "60"
