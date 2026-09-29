"""OpenCode GO request headers (no database needed).

OpenCode GO's gateway rejects requests that do not identify with a real user
agent and a stable per-conversation session id. These tests pin the helper and
the wire shape — pure unit tests, so they run without Postgres.
"""

import asyncio

from app.services.ai import OPENCODE_GO_UA, _openai_chat_completions, opencode_go_headers


def test_opencode_go_headers_only_for_the_go_provider():
    assert opencode_go_headers("opencode_go", "conv-1") == {
        "x-opencode-session": "conv-1",
        "User-Agent": OPENCODE_GO_UA,
    }
    # No session yet: a stable fallback value rather than an omitted header.
    assert opencode_go_headers("opencode_go", None)["x-opencode-session"] == "global"
    # Any other provider must stay untouched.
    assert opencode_go_headers("openai", "conv-1") == {}
    assert opencode_go_headers("opencode", "conv-1") == {}


def test_go_chat_completion_sends_the_session_header(monkeypatch):
    captured: dict = {}

    async def fake_post_json(url, headers, base_payload, sampling):
        captured.update(headers)
        return {
            "choices": [{"message": {"content": "ok"}}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1},
        }

    monkeypatch.setattr("app.services.ai._post_json", fake_post_json)
    result = asyncio.run(
        _openai_chat_completions(
            "https://opencode.ai/zen/go/v1",
            "key",
            "glm-5.2",
            [{"role": "user", "content": "hi"}],
            None,
            None,
            extra_headers=opencode_go_headers("opencode_go", "conv-1"),
        )
    )
    assert result.text == "ok"
    assert captured["x-opencode-session"] == "conv-1"
    assert captured["User-Agent"] == OPENCODE_GO_UA
    assert captured["Authorization"] == "Bearer key"