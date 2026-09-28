"""Catalog ordering uses published ownership, not inferred model families."""
import json
from unittest.mock import patch

import pytest


class Response:
    def __init__(self, rows):
        self.rows = rows

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def read(self):
        return json.dumps({"data": self.rows}).encode()


def test_fallback_floor_is_alphabetical_too(profiles):
    for profile in profiles:
        assert list(profile.fallback_models) == sorted(profile.fallback_models, key=str.casefold)


def test_groups_by_vendor_then_sorts_exact_ids_alphabetically(profiles):
    chat, _ = profiles
    rows = [
        {"id": "z-route/Zebra", "owned_by": "Alpha"},
        {"id": "openai/zeta", "owned_by": "api"},
        {"id": "anthropic/claude-z", "owned_by": "api"},
        {"id": "openai/Alpha", "owned_by": "api", "created": 1},
        {"id": "z-route/alpha", "owned_by": "Alpha", "created": 999},
        {"id": "anthropic/claude-a", "owned_by": "api"},
        {"id": "openai/Alpha", "owned_by": "api"},
    ]
    with patch("hermes_cli.urllib_security.open_credentialed_url", return_value=Response(rows)):
        assert chat.fetch_models() == [
            "z-route/alpha", "z-route/Zebra", "anthropic/claude-a",
            "anthropic/claude-z", "openai/Alpha", "openai/zeta",
        ]


@pytest.mark.parametrize("owner", [None, "", "  ", "API", " api ", 42, {}])
def test_generic_or_invalid_owners_use_exact_namespace(profiles, owner):
    chat, _ = profiles
    rows = [
        {"id": "z-vendor/model", "owned_by": owner},
        {"id": "a-vendor/model", "owned_by": owner},
    ]
    with patch("hermes_cli.urllib_security.open_credentialed_url", return_value=Response(rows)):
        assert chat.fetch_models() == ["a-vendor/model", "z-vendor/model"]


def test_unqualified_ids_ties_and_duplicate_owners_are_deterministic(profiles):
    chat, _ = profiles
    rows = [
        {"id": "vendor/alpha", "owned_by": "api"},
        {"id": "vendor/Alpha", "owned_by": "api"},
        {"id": "unknown", "owned_by": "api"},
        {"id": "vendor/Alpha", "owned_by": "aaa"},
        {"id": ""}, {"id": None}, "malformed",
    ]
    with patch("hermes_cli.urllib_security.open_credentialed_url", return_value=Response(rows)):
        assert chat.fetch_models() == ["unknown", "vendor/Alpha", "vendor/alpha"]


def test_each_fetch_refreshes_ids_and_ownership_without_source_changes(profiles):
    chat, _ = profiles
    responses = [
        Response([{"id": "z/model", "owned_by": "a"}, {"id": "b/model"}]),
        Response([{"id": "z/model", "owned_by": "z"}, {"id": "b/model"},
                  {"id": "new/model"}]),
    ]
    with patch("hermes_cli.urllib_security.open_credentialed_url", side_effect=responses):
        assert chat.fetch_models() == ["z/model", "b/model"]
        assert chat.fetch_models() == ["b/model", "new/model", "z/model"]


def test_anthropic_route_keeps_sorted_full_ids_only(profiles):
    _, anthropic = profiles
    rows = [
        {"id": "anthropic/claude-z.1"}, {"id": "openai/new-model"},
        {"id": "anthropic/claude-a.2:variant"}, {"id": "anthropic/not-claude"},
        {"id": "anthropic/claude-image", "modality": "image"},
    ]
    with patch("hermes_cli.urllib_security.open_credentialed_url", return_value=Response(rows)):
        assert anthropic.fetch_models() == ["anthropic/claude-a.2:variant", "anthropic/claude-z.1"]


def test_empty_catalog_is_not_replaced_by_static_floor(profiles):
    with patch("hermes_cli.urllib_security.open_credentialed_url", return_value=Response([])):
        for profile in profiles:
            assert profile.fetch_models() == []


def test_public_requests_are_keyless_and_have_hermes_user_agent(profiles):
    chat, _ = profiles
    with patch("hermes_cli.urllib_security.open_credentialed_url", return_value=Response([])) as request:
        chat.fetch_models()
    sent = request.call_args.args[0]
    assert sent.get_header("Authorization") is None
    assert "hermes" in sent.get_header("User-agent").lower()


def test_pricing_metadata_is_refetched_not_pinned(profiles):
    chat, _ = profiles
    def row(price):
        return {"id": "vendor/new-model", "pricing": {
            "currency": "USD", "unit": "per_1m_tokens", "input": price, "output": 0,
        }}
    with patch("hermes_cli.urllib_security.open_credentialed_url", side_effect=[
        Response([row("0.125")]), Response([row("0.25")]),
    ]):
        assert chat.fetch_model_pricing()["vendor/new-model"]["prompt"] == "0.000000125"
        assert chat.fetch_model_pricing()["vendor/new-model"]["prompt"] == "0.00000025"
