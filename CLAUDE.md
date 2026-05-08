# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Purpose

A Flask web application that acts as an OIDC client for diagnosing SSO systems (primarily Keycloak). The user logs in via SSO, then sees all claims from the ID token, access token, and UserInfo endpoint in a diagnostic UI. There is also a standalone JWT decoder that works without logging in.

## Setup & Running

```bash
# Install dependencies
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env with your Keycloak discovery URL, client ID, and client secret

# Run
python app.py

# Run in debug mode
FLASK_DEBUG=true python app.py
```

The app runs on port 5000 by default (`PORT` env var overrides this).

## Tests

```bash
pip install -r requirements-dev.txt
pytest tests/ -q
```

Tests live in [tests/](tests/) — `test_helpers.py` covers pure functions (`_detect_token_type`, `decode_jwt`, `_update_decoder_history`), `test_routes.py` smoke-tests the Flask routes (`/decode`, `/reference`, `/about`, `/decode/history/*`). They don't exercise the OIDC callback flow or anything making outbound HTTP. Fixtures in [tests/conftest.py](tests/conftest.py) set the env vars the app reads at import time before importing it.

## Keycloak Client Setup

In Keycloak, create a **confidential** OpenID Connect client with:

- Valid redirect URI: `http://localhost:5000/callback`
- The client secret goes in `OIDC_CLIENT_SECRET`
- Discovery URL pattern: `http://<host>:8080/realms/<realm>/.well-known/openid-configuration`

## Architecture

Single-file Flask app ([app.py](app.py)) with Jinja2 templates:

**Routes:**

- `/` — landing page, shows config status and provider cards
- `/login` → `/callback` — single-provider OIDC Authorization Code flow via Authlib
- `/login/<provider_id>` → `/callback/<provider_id>` — multi-provider flow
- `/claims` — main diagnostic view (requires session)
- `/claims.json` — JSON export of all decoded claims
- `/decode` — standalone JWT paste-and-decode tool (no login required); also accepts `?from_session=1&token_type=id_token|access_token|refresh_token` to pre-load a live session token
- `/decode/history/clear` (POST) — empties `session['decoder_history']`
- `/decode/history/delete` (POST, `hash` form param) — removes a single history entry
- `/conformance` — OIDC conformance and security analysis (pass `?provider=<id>&run=1`)
- `/refresh` — exchange refresh token for new access token
- `/logout` — RP-initiated logout then session clear (also `unlink()`s the encrypted `.sess` file)
- `/api/connectivity` — server-side reachability check for a discovery URL
- `/api/discovery` — fetches and returns a provider's discovery document
- `/reference` — reference documentation page (pass `?tab=connectivity|scopes|flow|brokering|jwt`)
- `/about` — technology stack, version badge, instance configuration, data & privacy

**Key helpers in `app.py`** (line numbers approximate, grep to confirm):

| Function | Purpose |
|---|---|
| `decode_jwt(token)` | base64url-decodes a JWT without signature verification; returns `{header, payload, error?, jwe?}` for 3-part vs 5-part input |
| `_detect_token_type(header, payload)` | Classifies as ID / Access / Refresh / Unknown. Explicit `typ` first (Keycloak `ID`/`Bearer`/`Refresh`, RFC 9068 `at+jwt`), then payload-claim fallback (`nonce` → ID, `scope`/`scp` → Access) |
| `_update_decoder_history(session_obj, token_raw, decoded, known_type=None)` | Prepends to `session['decoder_history']` (max 10, dedup by SHA256(payload)). `known_type` overrides detection — used when the token came from a known session slot |
| `prepare_claims(claims_dict)` | Converts a raw claims dict into typed display entries (timestamps, booleans, arrays, nested objects) |
| `build_compare_table(...)` | Merges claims from ID / Access / UserInfo and flags mismatches with ⚠ |
| `run_conformance_checks(provider_id)` | Fetches the discovery doc and runs ~30 conformance and security checks |
| `_get_provider(provider_id)` | Looks up a provider dict from `PROVIDERS` by ID |
| `_is_localhost(url)` | True for localhost/127.0.0.1/::1/.local URLs (used by conformance HTTPS checks) |
| `_register_provider_extension_headers()` | Module-load hook that adds `client_id` to joserfc's `JWS_HEADER_REGISTRY` so Kanidm-style JWT headers are accepted (Authlib delegates JWT decoding to joserfc) |
| `_PermissiveIDToken` (removed v0.2.2) | Don't add this back — header validation happens in joserfc *before* claims classes are constructed; subclassing `CodeIDToken` doesn't help. Patch the joserfc registry instead |

**Key state in the Flask session:**

| Key | Type | Purpose |
|---|---|---|
| `session['user']` | str | Display username; presence of this key = "logged in" |
| `session['provider_id']` | str | Active multi-provider id |
| `session['raw_tokens']` | dict | `id_token`, `access_token`, `refresh_token`, `token_type`, `expires_at`, `scope` |
| `session['userinfo']` | dict | UserInfo endpoint response |
| `session['decoder_history']` | list[dict] | Last 10 decodes — `hash`, `ts`, `label`, `token_type`, `token_raw` |
| `session['session_expires_at']` | int | Unix ts when the encrypted blob TTL kicks in |

**Templates** ([templates/](templates/)):

- `base.html` — layout, all CSS (CSS variables, full dark mode overrides), shared JS utilities (`copyText`, `initTabs`, `initSearch`, `toggleTheme`)
- `index.html` — login landing; multi-provider cards with connectivity check and Conformance link; signed-in state; Provider Details tabbed panel (Configuration + Provider Metadata) below the grid
- `claims.html` — five-tab view: ID Token / Access Token / UserInfo / Compare / Raw JWT; scope filter bar; Copy as curl button
- `decode.html` — standalone decoder. Layout (top to bottom): paste form (with Help button → `/reference?tab=jwt`), Load-from-session panel (JWE entries are static badges), always-expanded Recent decodes table with A/B toggle + Recall + ✕ Delete + inline diff renderer below the table, decoded payload (Token Visualised / Lifetime / Header / Payload Claims), and Verify Signature inline (only after a JWS is decoded — not collapsible)
- `conformance.html` — conformance and security check results grouped by category with status badges
- `reference.html` — five-tab reference docs: Connectivity, Scopes & Claims, OIDC Flow, Identity Brokering, JWT (anatomy, JWS vs JWE, how to obtain one)
- `about.html` — technology stack, build info, instance configuration, data & privacy section; links to source and issues tracker
- `macros.html` — `claim_value` and `claims_table` macros shared between claims.html and decode.html

**Interactive features:**

- Dark mode toggle (nav bar `◑`/`☀` button); theme persisted in `localStorage`; anti-flash script in `<head>`
- Tab switching with `sessionStorage` persistence across token refresh redirects
- Live search/filter and per-scope filter pills on claims page
- "Mask sensitive" toggle blurs `sub`, `email`, `name`, etc. (useful for screenshots)
- Live expiry countdown in nav bar and claims page header
- Compare tab highlights claims present in multiple sources with differing values (⚠ badge)
- Raw JWT tab: colour-coded header · payload · signature with Copy buttons
- Decoder: live-updating token timeline bar (`iat`→now→`exp`); expiry warning banner; type detection (ID / Access / Refresh — Keycloak `typ` values `"ID"`/`"Bearer"`/`"Refresh"`, RFC 9068 `"at+jwt"`, plus `nonce`/`scope` payload-claim fallback for `typ`-less providers like Kanidm); decoder history with A/B toggle compare, Recall, and per-row ✕ Delete; inline JWKS signature verification via Web Crypto API (RS/PS/ES families) appearing only when a JWS is decoded; JWE refresh tokens shown as a static "(encrypted JWE)" badge in load-from-session panel
- Claims page: claim description tooltips on hover; Copy as curl button fetches UserInfo endpoint from discovery doc and builds a ready-to-paste `curl` command
- Multi-provider: signed-in provider card highlighted with green border and action buttons; Provider Details panel below grid with Configuration and Metadata tabs, auto-selects signed-in provider; Conformance quick-launch link on every provider card
- Connectivity checker: displays `✓ reachable` + latency or `✗ unreachable` + full error text (word-wrapped, selectable) per card

**No frontend build step** — pure server-rendered Jinja2, vanilla CSS, and vanilla JS. No npm, no webpack.
