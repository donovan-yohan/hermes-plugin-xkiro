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

xKiro's `/v1/models` endpoint is public. This plugin fetches it live (key optional). Chat-only rows are kept; image/other modalities are dropped.

Both routes also carry a small static `fallback_models` list. Hermes only uses it when the live catalog is unavailable, so it never masks real results. It exists because the Desktop and GUI pickers open from a cache-only read: on a cold catalog cache the provider row would otherwise report zero models and the menu drops the whole provider group. The static list keeps both entries selectable and lets the background refresh fill in the full catalog.

## Anthropic route

`xkiro-anthropic` uses `api_mode=anthropic_messages`. xKiro itself accepts both `x-api-key` and Bearer auth with full `anthropic/claude-*` ids (verified against `/v1/messages`). However, Hermes core strips the `anthropic/` prefix and version dots on the Anthropic Messages path (`normalize_model_name`), and does not yet read this plugin's `preserve_anthropic_model_id` attribute, so main-turn requests send a bare Claude id that xKiro 404s. Until a Hermes core PR honors that flag (or allowlists `api.xkiro.com`), picks via this route fall back to the configured fallback chain. The chat route (`xkiro`) is unaffected and fully working.

## Tests

From a Hermes checkout that can import `providers` and `hermes_cli`:

```bash
PYTHONPATH=/path/to/hermes-agent pytest tests/test_xkiro_provider.py -q
```
