# hermes-plugin-xkiro

Standalone Hermes model-provider plugin for [xKiro](https://xkiro.com/).

It registers two profiles:

- `xkiro` — OpenAI-compatible Chat Completions
- `xkiro-anthropic` — Anthropic Messages, same key and base URL

Model IDs stay in xKiro's full `vendor/model` form (for example `openai/gpt-5.6-luna`). Catalog pricing is parsed in this plugin; Hermes core currently has no picker hook for `fetch_model_pricing`, so that method is ready when core grows one.

Anthropic Messages still needs a tiny in-tree allowlist so Hermes uses Bearer auth and does not strip the vendor prefix. That change is a separate Hermes PR, not this plugin.

## Install

```bash
hermes plugins install donovan-yohan/hermes-plugin-xkiro --enable
```

Put the key in the active profile `.env`:

```bash
XKIRO_API_KEY=...
# optional
# XKIRO_BASE_URL=https://api.xkiro.com/v1
```

Then:

```bash
hermes --profile ebi model
# or
hermes --profile ebi --provider xkiro -m x-ai/grok-4.6
hermes --profile ebi --provider xkiro-anthropic -m anthropic/claude-sonnet-4.6
```

Restart the session or gateway after install so discovery reloads.

## Catalog

xKiro's `/v1/models` endpoint is public. Every call to the plugin's `fetch_models()` reads the current catalog (key optional); there is no plugin catalog cache or curated live-model list to update. Newly published IDs appear on the next successful fetch without a commit or reinstall. Rows with `modality: chat` or no modality are kept; image/other modalities are dropped. Full IDs, including vendor prefixes, version dots and suffixes, are preserved, with surrounding whitespace removed and duplicates collapsed.

The live list is grouped by the catalog's `owned_by` provider and ordered alphabetically within each group by full model ID (case-insensitive, exact ID as a deterministic tie-break). When ownership is missing, malformed or the generic `api`, the exact `vendor/` namespace supplies the provider. Unqualified IDs with no usable owner have no provider and sort first. Ownership is read again on every fetch; no vendor table, model-family heuristic or release-recency inference is involved. Placeholder `created` values are not used. `xkiro-anthropic` retains this ordering while selecting only `anthropic/claude-*` IDs.

Hermes may cache these results independently. Current Desktop builds normally open the picker from a cache-only read; the core catalog cache has a one-hour freshness window and stale-while-revalidate behavior. Use **Refresh Models** to request a fresh catalog immediately. This plugin does not bypass or patch the core cache. Ordering gives contiguous vendor groups inside each xKiro route; visual vendor headings are a picker responsibility, not a new routing provider per vendor.

Both routes retain the existing small static `fallback_models` floor, now alphabetically ordered. It keeps the routes visible on cache-cold/offline picker opens; it is not a complete or guaranteed-current catalog. Successful live plugin fetches return only endpoint IDs, never merge the floor. Refresh to obtain the current selection. A failed plugin fetch returns `None`; a valid empty catalog returns `[]`.

### Host compatibility

Both profiles set `live_catalog_mode="authoritative"` (the API proposed in
[Hermes PR121149](https://github.com/NousResearch/hermes-agent/pull/121149)) and
`public_model_catalog=True` after construction, keeping older hosts importable.
[Hermes PR126899](https://github.com/NousResearch/hermes-agent/pull/126899) carries
the compatible public-discovery and setup/cache/GUI propagation needed here.
Older hosts, including `ec243785e41e7a12d47b099d9f747c781687f57a`, ignore
these attributes: the plugin still imports, but core can prepend stale fallback
IDs, skip keyless discovery, and replace a successful empty list with static rows.
Plugin ordering alone cannot correct those host behaviors. Do not remove the
offline floor or claim the full picker contract works on those hosts.

CI pins the real host source at
`donovan-yohan/hermes-agent@c9230af278d050f89be1894aa14fabadf5b2c486`
until the complete contract lands upstream; this is a pre-merge integration pin,
not a claim that upstream main already supports it. No running host is upgraded
by this plugin change.

### Metadata and core support

The plugin already reads fresh pricing metadata through `fetch_model_pricing()` and now uses fresh ownership metadata to order `fetch_models()`. Prices are normalized from documented USD per million tokens with `Decimal`; free prices stay zero. The current `ProviderProfile` has no generic HTTP catalog-metadata/picker-pricing hook, so this change does not introduce an unused `fetch_model_metadata()` method or pretend price, capability, context-length or vendor-heading metadata reaches the picker. The existing pricing method remains available to direct callers but is not consumed by core. Rich dynamic picker metadata needs a separate generic core contract. Keyless pricing parsing does not claim account entitlements or inference access.

## Anthropic route

`xkiro-anthropic` uses `api_mode=anthropic_messages`. xKiro itself accepts both `x-api-key` and Bearer auth with full `anthropic/claude-*` ids (verified against `/v1/messages`). However, Hermes core strips the `anthropic/` prefix and version dots on the Anthropic Messages path (`normalize_model_name`), and does not yet read this plugin's `preserve_anthropic_model_id` attribute, so main-turn requests send a bare Claude id that xKiro 404s. Until a Hermes core PR honors that flag (or allowlists `api.xkiro.com`), picks via this route fall back to the configured fallback chain. The chat route (`xkiro`) is unaffected and fully working.

## Tests

From this plugin checkout, using a Python environment with `pytest`, `pyyaml`, `ruamel.yaml`, `python-dotenv`, `requests`, `pydantic` and `httpx` and an actual Hermes source checkout:

```bash
PYTHONPATH=/path/to/hermes-agent python -m pytest tests -ra
# Optional public-network check: no API key or paid inference, includes both routes.
XKIRO_LIVE_TEST=1 PYTHONPATH=/path/to/hermes-agent python -m pytest tests/test_live_catalog.py -s -ra
```

The fixture copies this checkout's plugin into a temporary `HERMES_HOME`, loads it through real Hermes provider discovery, and verifies the loaded class's source path and bytes. It does not import `model_tools`, use an installed xKiro plugin, mock `ProviderProfile`, or modify your profiles. Deterministic tests mock only catalog HTTP responses. The end-to-end contract tests call actual `provider_model_ids`, disk caching and the GUI catalog helper for both routes, keyed/keyless, live/empty/offline. CI checks out the explicitly pinned Hermes revision above and exercises the same integration; the opt-in live test is excluded from required CI to avoid making upstream availability a merge gate.
