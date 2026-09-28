"""Real discovery -> provider_model_ids -> disk cache; only HTTP is simulated."""
import io
import json

import pytest


@pytest.mark.parametrize("route", [0, 1])
@pytest.mark.parametrize("key", [None, "test-key"])
def test_core_catalog_contract(profiles, monkeypatch, route, key):
    from hermes_cli import models
    from hermes_cli.model_switch_providers import _live_or_curated_ids

    profile = profiles[route]
    monkeypatch.setattr(models, "_api_key_credentials", lambda *_: (key, profile.base_url))
    monkeypatch.setattr(models, "_configured_relay_base_url", lambda *_: "")
    monkeypatch.setitem(models._PROVIDER_MODELS, profile.name, ["retired/static"])
    state = {"rows": [
        {"id": "vendor/z-chat", "owned_by": "A"},
        {"id": "anthropic/claude-test", "owned_by": "B"},
    ], "offline": False}
    requests = []

    def http(request, **kwargs):
        requests.append(request.get_header("Authorization"))
        if state["offline"]:
            raise OSError("offline")
        return io.BytesIO(json.dumps({"data": state["rows"]}).encode())

    monkeypatch.setattr("hermes_cli.urllib_security.open_credentialed_url", http)
    expected = [row["id"] for row in state["rows"]]
    if route:
        expected = expected[1:]
    assert models.provider_model_ids(profile.name) == expected
    assert requests == ([f"Bearer {key}"] if key else [None])
    assert models.cached_provider_model_ids(profile.name, force_refresh=True) == expected
    assert _live_or_curated_ids(profile.name, {profile.name: ["retired/static"]}, non_blocking=True) == expected

    state["rows"] = []
    assert models.provider_model_ids(profile.name) == []
    assert models.cached_provider_model_ids(profile.name, force_refresh=True) == []
    assert _live_or_curated_ids(profile.name, {profile.name: ["retired/static"]}, non_blocking=True) == []

    state["offline"] = True
    assert models.provider_model_ids(profile.name) == list(profile.fallback_models)
    # Last successful empty catalog stays authoritative during an outage.
    assert models.cached_provider_model_ids(profile.name, force_refresh=True) == []
