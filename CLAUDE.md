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
- `/decode` — standalone JWT paste-and-decode tool (no login required)
- `/conformance` — OIDC conformance and security analysis (pass `?provider=<id>&run=1`)
- `/refresh` — exchange refresh token for new access token
- `/logout` — RP-initiated logout then session clear
- `/api/connectivity` — server-side reachability check for a discovery URL
- `/api/discovery` — fetches and returns a provider's discovery document

**Key helpers in `app.py`:**

- `decode_jwt(token)` — base64url-decodes a JWT without signature verification
- `prepare_claims(claims_dict)` — converts a raw claims dict into typed display entries (handles timestamps, booleans, arrays, nested objects)
- `build_compare_table(...)` — merges claims from all three sources and flags mismatches
- `run_conformance_checks(provider_id)` — fetches the discovery document and runs ~30 conformance and security checks; returns `{provider, checks, counts, latency_ms}`
- `_get_provider(provider_id)` — looks up a provider dict from `PROVIDERS` by ID
- `_is_localhost(url)` — returns True for localhost/127.0.0.1/::1/.local URLs (used by conformance HTTPS checks)

**Templates** ([templates/](templates/)):

- `base.html` — layout, all CSS (CSS variables, full dark mode overrides), shared JS utilities (`copyText`, `initTabs`, `initSearch`, `toggleTheme`)
- `index.html` — login landing; multi-provider cards with connectivity check, signed-in state, optional config section
- `claims.html` — five-tab view: ID Token / Access Token / UserInfo / Compare / Raw JWT; scope filter bar
- `decode.html` — standalone decoder with expiry warning, token timeline, decode history, and two-token diff
- `conformance.html` — conformance and security check results grouped by category with status badges
- `macros.html` — `claim_value` and `claims_table` macros shared between claims.html and decode.html

**Interactive features:**

- Dark mode toggle (nav bar `◑`/`☀` button); theme persisted in `localStorage`; anti-flash script in `<head>`
- Tab switching with `sessionStorage` persistence across token refresh redirects
- Live search/filter and per-scope filter pills on claims page
- "Mask sensitive" toggle blurs `sub`, `email`, `name`, etc. (useful for screenshots)
- Live expiry countdown in nav bar and claims page header
- Compare tab highlights claims present in multiple sources with differing values (⚠ badge)
- Raw JWT tab: colour-coded header · payload · signature with Copy buttons
- Decoder: token timeline bar (`iat`→now→`exp`), expiry warning banner, decode history, two-token diff table
- Multi-provider: signed-in provider card highlighted with green border and action buttons

**No frontend build step** — pure server-rendered Jinja2, vanilla CSS, and vanilla JS. No npm, no webpack.
