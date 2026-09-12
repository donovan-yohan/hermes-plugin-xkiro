"""Tests for the standalone xKiro model-provider plugin."""

from __future__ import annotations

import json
from unittest.mock import patch
from urllib.error import URLError

import pytest


class _Response:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


def _catalog(*items):
    return {"object": "list", "data": list(items)}


@pytest.fixture
def profiles():
    import model_tools  # noqa: F401 — triggers discovery
    from providers import get_provider_profile

    chat = get_provider_profile("xkiro")
    anthropic = get_provider_profile("xkiro-anthropic")
    assert chat is not None
    assert anthropic is not None
    return chat, anthropic


def test_xkiro_profiles_are_registered_with_shared_credentials(profiles):
    profile, anthropic = profiles

    assert profile.name == "xkiro"
    assert profile.display_name == "xKiro"
    assert profile.api_mode == "chat_completions"
    assert profile.base_url == "https://api.xkiro.com/v1"
    assert profile.env_vars == ("XKIRO_API_KEY", "XKIRO_BASE_URL")
    assert profile.default_aux_model == "qwen/qwen3.5-flash:free"
    assert profile.fallback_models == ()

    assert anthropic.name == "xkiro-anthropic"
    assert anthropic.display_name == "xKiro (Anthropic)"
    assert anthropic.api_mode == "anthropic_messages"
    assert anthropic.base_url == profile.base_url
    assert anthropic.env_vars == ("XKIRO_API_KEY", "XKIRO_ANTHROPIC_BASE_URL")
    assert anthropic.default_aux_model == ""


def test_xkiro_aliases(profiles):
    from providers import get_provider_profile

    assert get_provider_profile("xkiro-ai").name == "xkiro"
    assert get_provider_profile("xkiro-claude").name == "xkiro-anthropic"


def test_xkiro_fetch_models_parses_chat_catalog_and_custom_base(profiles):
    profile, _ = profiles
    requests = []

    def fake_open(request, timeout):
        requests.append((request, timeout))
        return _Response(
            _catalog(
                {"id": "openai/gpt-5.6-luna"},
                {"id": "x-ai/grok-4.6"},
                {"id": "stability/image-model", "modality": "image"},
                {"id": 123},
                {"name": "missing-id"},
            )
        )

    with patch("hermes_cli.urllib_security.open_credentialed_url", side_effect=fake_open):
        models = profile.fetch_models(api_key="test-key", base_url="https://proxy.example/v1", timeout=3)

    assert models == ["openai/gpt-5.6-luna", "x-ai/grok-4.6"]
    request, timeout = requests[0]
    assert request.full_url == "https://proxy.example/v1/models"
    assert request.get_header("Authorization") == "Bearer test-key"
    assert timeout == 3


def test_xkiro_catalog_normalizes_vendor_origin_without_v1(profiles):
    _, anthropic = profiles
    requests = []

    def fake_open(request, timeout):
        requests.append(request)
        return _Response(_catalog({"id": "anthropic/claude-sonnet-4.6"}))

    with patch("hermes_cli.urllib_security.open_credentialed_url", side_effect=fake_open):
        assert anthropic.fetch_models(base_url="https://api.xkiro.com") == ["anthropic/claude-sonnet-4.6"]

    assert requests[0].full_url == "https://api.xkiro.com/v1/models"


def test_xkiro_anthropic_filters_catalog_to_claude_models(profiles):
    _, anthropic = profiles
    payload = _catalog(
        {"id": "anthropic/claude-sonnet-5"},
        {"id": "qwen/qwen3.5-flash:free"},
        {"id": "openai/gpt-5.6-luna"},
        {"id": "anthropic/claude-opus-5"},
    )

    with patch("hermes_cli.urllib_security.open_credentialed_url", return_value=_Response(payload)):
        models = anthropic.fetch_models(api_key="test-key")

    assert models == ["anthropic/claude-sonnet-5", "anthropic/claude-opus-5"]


def test_xkiro_fetch_models_returns_none_on_failure_or_malformed_payload(profiles):
    profile, _ = profiles

    with patch("hermes_cli.urllib_security.open_credentialed_url", side_effect=URLError("blocked")):
        assert profile.fetch_models(timeout=1) is None
    with patch(
        "hermes_cli.urllib_security.open_credentialed_url",
        return_value=_Response({"object": "list", "data": "not-a-list"}),
    ):
        assert profile.fetch_models(timeout=1) is None


def test_xkiro_pricing_normalizes_documented_per_million_units(profiles):
    profile, _ = profiles
    payload = _catalog(
        {
            "id": "openai/gpt-5.6-luna",
            "pricing": {
                "currency": "USD",
                "unit": "per_1m_tokens",
                "input": 0.1,
                "output": 0.6,
                "cache_read": 0.05,
            },
        },
        {
            "id": "qwen/qwen3.5-flash:free",
            "pricing": {"currency": "USD", "unit": "per_1m_tokens", "input": 0, "output": 0},
        },
        {
            "id": "wrong-unit",
            "pricing": {"currency": "USD", "unit": "per_token", "input": 1, "output": 1},
        },
        {
            "id": "wrong-currency",
            "pricing": {"currency": "EUR", "unit": "per_1m_tokens", "input": 1, "output": 1},
        },
    )

    with patch("hermes_cli.urllib_security.open_credentialed_url", return_value=_Response(payload)):
        pricing = profile.fetch_model_pricing()

    assert pricing == {
        "openai/gpt-5.6-luna": {
            "prompt": "0.0000001",
            "completion": "0.0000006",
            "input_cache_read": "0.00000005",
        },
        "qwen/qwen3.5-flash:free": {"prompt": "0", "completion": "0"},
    }


def test_xkiro_hostname(profiles):
    profile, _ = profiles
    assert profile.get_hostname() == "api.xkiro.com"
