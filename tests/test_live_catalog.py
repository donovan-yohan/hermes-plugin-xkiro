"""Opt-in, keyless catalog parity check; never sends inference requests."""
import json
import os
from urllib.request import Request

import pytest


@pytest.mark.skipif(os.getenv("XKIRO_LIVE_TEST") != "1", reason="set XKIRO_LIVE_TEST=1 for public HTTP")
def test_live_catalog_parity(profiles):
    from hermes_cli.urllib_security import open_credentialed_url
    from providers.base import _profile_user_agent

    request = Request("https://api.xkiro.com/v1/models", headers={
        "Accept": "application/json", "User-Agent": _profile_user_agent(),
    })
    with open_credentialed_url(request, timeout=20) as response:
        rows = json.load(response)["data"]
    expected = {}
    for row in rows:
        model_id = row.get("id")
        if row.get("modality") in (None, "chat") and isinstance(model_id, str) and model_id.strip():
            expected.setdefault(model_id.strip(), row)
    assert expected, "Public catalog must contain chat models"
    chat, anthropic = profiles
    actual = chat.fetch_models(timeout=20)
    assert actual is not None
    assert set(actual) == set(expected)
    assert len(actual) == len(expected)
    # Independent grouping check against the published ownership in the raw response.
    groups = []
    for model_id in actual:
        owner = expected[model_id].get("owned_by")
        owner = owner.strip() if isinstance(owner, str) else ""
        if not owner or owner.casefold() == "api":
            owner = model_id.split("/", 1)[0] if "/" in model_id else ""
        groups.append((owner.casefold(), model_id.casefold(), model_id))
    assert groups == sorted(groups)
    claude = anthropic.fetch_models(timeout=20)
    assert claude == [model for model in actual if model.startswith("anthropic/claude-")]
    pricing = chat.fetch_model_pricing(timeout=20)
    assert pricing is not None
    assert set(pricing) <= set(expected)
    print(f"Live parity: {len(actual)} chat IDs, {len(claude)} Anthropic IDs, {len(pricing)} price rows")
    print("OpenAI IDs:", [model for model in actual if model.startswith("openai/")])
