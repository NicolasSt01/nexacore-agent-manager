"""Messenger and Instagram channels.

The webhook is a public, unauthenticated surface that Meta calls directly, so
the signature check, the platform check and the echo guard are covered here
rather than left to the end-to-end suite.
"""

import hashlib
import hmac
import json
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.routers import meta_channels as meta_router
from app.routers import meta_webhook as webhook_router
from app.services import ai as ai_service
from app.services import whatsapp_inbound as whatsapp_inbound_service


APP_SECRET = "meta-app-secret"
ACCESS_TOKEN = "meta-page-token"
WEBHOOK_OBJECT = {"messenger": "page", "instagram": "instagram"}


def _sign(raw: bytes, secret: str = APP_SECRET) -> str:
    return "sha256=" + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()


def _payload(events: list[dict], platform: str = "messenger") -> dict:
    return {
        "object": WEBHOOK_OBJECT[platform],
        "entry": [{"id": "acct-1", "time": 1, "messaging": events}],
    }


def _text_event(mid: str, sender: str, text: str) -> dict:
    return {"sender": {"id": sender}, "recipient": {"id": "acct-1"}, "message": {"mid": mid, "text": text}}


def _post_signed(client: TestClient, channel_id: str, payload: dict, secret: str = APP_SECRET):
    raw = json.dumps(payload).encode()
    return client.post(
        f"/api/public/meta/channels/{channel_id}/webhook",
        content=raw,
        headers={"Content-Type": "application/json", "X-Hub-Signature-256": _sign(raw, secret)},
    )


def _setup_channel(client: TestClient, platform: str = "messenger") -> tuple[dict, dict, dict]:
    customer = client.post("/api/clients", json={"name": "Bistro"}).json()
    client.put("/api/providers/openai", json={"api_key": "secret"})
    agent = client.post(
        "/api/agents",
        json={"client_id": customer["id"], "provider": "openai", "model": "gpt-4.1-mini", "name": "Host"},
    ).json()
    channel = client.put(
        f"/api/meta/{platform}/channels/{customer['id']}",
        json={
            "agent_id": agent["id"],
            "account_id": "acct-1",
            "access_token": ACCESS_TOKEN,
            "app_secret": APP_SECRET,
        },
    ).json()
    return customer, agent, channel


@pytest.mark.parametrize("platform", ["messenger", "instagram"])
def test_configure_channel_hides_secrets(authenticated_client: TestClient, platform):
    _, _, channel = _setup_channel(authenticated_client, platform)
    assert channel["platform"] == platform
    assert channel["has_access_token"] is True
    assert channel["has_app_secret"] is True
    assert "access_token" not in channel
    assert "app_secret" not in channel
    assert channel["webhook_url"].endswith(f"/api/public/meta/channels/{channel['id']}/webhook")
    assert channel["webhook_verify_token"]


def test_unknown_platform_is_404(authenticated_client: TestClient):
    customer = authenticated_client.post("/api/clients", json={"name": "Bistro"}).json()
    assert authenticated_client.get(f"/api/meta/tiktok/channels/{customer['id']}").status_code == 404


def test_a_client_can_have_both_platforms(authenticated_client: TestClient):
    client = authenticated_client
    customer, agent, messenger = _setup_channel(client, "messenger")
    instagram = client.put(
        f"/api/meta/instagram/channels/{customer['id']}",
        json={"agent_id": agent["id"], "account_id": "ig-1", "access_token": "t", "app_secret": APP_SECRET},
    ).json()
    assert messenger["id"] != instagram["id"]
    assert instagram["account_id"] == "ig-1"


def test_webhook_verify_handshake(authenticated_client: TestClient):
    _, _, channel = _setup_channel(authenticated_client)
    base = f"/api/public/meta/channels/{channel['id']}/webhook"
    ok = authenticated_client.get(
        base,
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": channel["webhook_verify_token"],
            "hub.challenge": "challenge-123",
        },
    )
    assert ok.status_code == 200 and ok.text == "challenge-123"

    bad = authenticated_client.get(
        base,
        params={"hub.mode": "subscribe", "hub.verify_token": "wrong", "hub.challenge": "x"},
    )
    assert bad.status_code == 403


def test_webhook_rejects_bad_signature(authenticated_client: TestClient, monkeypatch):
    client = authenticated_client
    _, _, channel = _setup_channel(client)
    fake_completion = AsyncMock(return_value=ai_service.Completion(text="Hello!"))
    monkeypatch.setattr(whatsapp_inbound_service, "run_completion", fake_completion)

    response = _post_signed(client, channel["id"], _payload([_text_event("m1", "psid-1", "hi")]), secret="wrong")
    assert response.status_code == 403
    assert fake_completion.await_count == 0


def test_webhook_text_message_creates_conversation_and_replies(authenticated_client: TestClient, monkeypatch):
    client = authenticated_client
    customer, agent, channel = _setup_channel(client)
    fake_completion = AsyncMock(return_value=ai_service.Completion(text="We open at 9."))
    monkeypatch.setattr(whatsapp_inbound_service, "run_completion", fake_completion)
    fake_send = AsyncMock(return_value="mid.out-1")
    monkeypatch.setattr(webhook_router, "send_text", fake_send)
    monkeypatch.setattr(webhook_router, "fetch_contact_name", AsyncMock(return_value="Ana"))

    response = _post_signed(client, channel["id"], _payload([_text_event("m1", "psid-1", "what time do you open?")]))
    assert response.status_code == 200
    fake_send.assert_awaited_once_with(ACCESS_TOKEN, "acct-1", "psid-1", "We open at 9.")

    conversations = client.get("/api/conversations").json()
    conversation = next(row for row in conversations if row["channel"] == "messenger")
    assert conversation["contact_name"] == "Ana"
    detail = client.get(f"/api/conversations/{conversation['id']}").json()
    assert [message["content"] for message in detail["messages"]] == [
        "what time do you open?",
        "We open at 9.",
    ]


def test_webhook_ignores_echoes(authenticated_client: TestClient, monkeypatch):
    """Our own outbound messages come back as echoes; replying to them would
    make the agent talk to itself in a loop."""
    client = authenticated_client
    _, _, channel = _setup_channel(client)
    fake_completion = AsyncMock(return_value=ai_service.Completion(text="Hi"))
    monkeypatch.setattr(whatsapp_inbound_service, "run_completion", fake_completion)
    monkeypatch.setattr(webhook_router, "send_text", AsyncMock(return_value="x"))

    echo = {
        "sender": {"id": "acct-1"},
        "recipient": {"id": "psid-1"},
        "message": {"mid": "m-echo", "text": "We open at 9.", "is_echo": True},
    }
    assert _post_signed(client, channel["id"], _payload([echo])).status_code == 200
    assert fake_completion.await_count == 0


def test_webhook_ignores_events_from_the_other_platform(authenticated_client: TestClient, monkeypatch):
    """A Page event must not be processed by an Instagram channel."""
    client = authenticated_client
    _, _, channel = _setup_channel(client, "instagram")
    fake_completion = AsyncMock(return_value=ai_service.Completion(text="Hi"))
    monkeypatch.setattr(whatsapp_inbound_service, "run_completion", fake_completion)
    monkeypatch.setattr(webhook_router, "send_text", AsyncMock(return_value="x"))

    wrong = _payload([_text_event("m1", "psid-1", "hola")], platform="messenger")
    assert _post_signed(client, channel["id"], wrong).status_code == 200
    assert fake_completion.await_count == 0


def test_webhook_deduplicates_retried_messages(authenticated_client: TestClient, monkeypatch):
    """Meta retries on any non-2xx, so the same mid can arrive twice."""
    client = authenticated_client
    _, _, channel = _setup_channel(client)
    fake_completion = AsyncMock(return_value=ai_service.Completion(text="Hi"))
    monkeypatch.setattr(whatsapp_inbound_service, "run_completion", fake_completion)
    monkeypatch.setattr(webhook_router, "send_text", AsyncMock(return_value="x"))
    monkeypatch.setattr(webhook_router, "fetch_contact_name", AsyncMock(return_value=None))

    payload = _payload([_text_event("m-dup", "psid-1", "hola")])
    _post_signed(client, channel["id"], payload)
    _post_signed(client, channel["id"], payload)
    assert fake_completion.await_count == 1


def test_disabled_channel_does_not_reply(authenticated_client: TestClient, monkeypatch):
    client = authenticated_client
    customer, _, channel = _setup_channel(client)
    fake_completion = AsyncMock(return_value=ai_service.Completion(text="Hi"))
    monkeypatch.setattr(whatsapp_inbound_service, "run_completion", fake_completion)
    monkeypatch.setattr(webhook_router, "send_text", AsyncMock(return_value="x"))

    client.post(f"/api/meta/messenger/channels/{customer['id']}/disconnect")
    assert _post_signed(client, channel["id"], _payload([_text_event("m1", "psid-1", "hola")])).status_code == 200
    assert fake_completion.await_count == 0


def test_connect_verifies_credentials(authenticated_client: TestClient, monkeypatch):
    client = authenticated_client
    customer, _, _ = _setup_channel(client)
    monkeypatch.setattr(meta_router, "verify_account", AsyncMock(return_value={"name": "Bistro MX"}))

    connected = client.post(f"/api/meta/messenger/channels/{customer['id']}/connect").json()
    assert connected["status"] == "connected"
    assert connected["account_name"] == "Bistro MX"
    assert connected["last_error"] is None


def test_usage_is_attributed_to_the_client(authenticated_client: TestClient, monkeypatch, db_session):
    """Messenger traffic must land on the client's quota like any other channel."""
    from app.models import UsageRecord

    client = authenticated_client
    customer, _, channel = _setup_channel(client)
    monkeypatch.setattr(
        whatsapp_inbound_service,
        "run_completion",
        AsyncMock(return_value=ai_service.Completion(text="Hi", input_tokens=30, output_tokens=12)),
    )
    monkeypatch.setattr(webhook_router, "send_text", AsyncMock(return_value="x"))
    monkeypatch.setattr(webhook_router, "fetch_contact_name", AsyncMock(return_value=None))

    _post_signed(client, channel["id"], _payload([_text_event("m1", "psid-1", "hola")]))

    record = db_session.query(UsageRecord).one()
    assert str(record.client_id) == customer["id"]
    assert record.source == "messenger"
    assert (record.input_tokens, record.output_tokens) == (30, 12)

    detail = client.get(f"/api/clients/{customer['id']}").json()
    assert detail["used_tokens_current_cycle"] == 42
