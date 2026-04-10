# OIDC Diagnostic Tool

A lightweight web application that acts as an OIDC client for diagnosing SSO systems. Log in via your provider (Keycloak, Kanidm, Authentik, Entra ID, Okta, etc.) and inspect every claim from the ID token, access token, and UserInfo endpoint side by side.

## Features

- **Five-tab claims view** — ID Token · Access Token · UserInfo · Compare · Raw JWT
- **Compare tab** — shows every unique claim key across all three sources and flags ⚠ where the same claim has different values
- **Live search** — filter claims by name or value instantly
- **Mask sensitive values** — blur `sub`, `email`, `name`, etc. for safe screenshotting
- **Token expiry countdown** — live timer showing how long the session token remains valid
- **Token refresh** — refresh the access token without signing out (if provider issues refresh tokens)
- **Copy buttons** — per-claim copy and full JSON export
- **Standalone JWT decoder** — paste any token and decode it without logging in
- **Connectivity checker** — checks both the app server and your browser can reach the OIDC provider
- **Provider discovery viewer** — fetches and displays the `.well-known/openid-configuration`, with your current PKCE method and signing algorithm highlighted
- **RP-initiated logout** — redirects to the provider's `end_session_endpoint` where supported (Keycloak)
- **PKCE S256** — enabled by default; required by Kanidm, recommended everywhere
- **ES256 / RS256** — configurable token signing algorithm enforcement
- **Help menu** — connectivity guide, scope reference, and OIDC flow diagram

---

## Quickstart with Docker

The fastest way to run the tool is with the pre-built image from GitHub Container Registry.

**1. Create a `.env` file:**

```bash
curl -o .env https://raw.githubusercontent.com/tfindley/sso_oidc_client_tool/main/.env.example
# Edit .env with your provider details
```

**2. Run with Docker Compose:**

```bash
docker compose up
```

Then open [http://localhost:5000](http://localhost:5000).

---

## Provider Setup Guides

### Keycloak

1. In your realm go to **Clients** → **Create client**
2. Set **Client type** to `OpenID Connect`
3. Enable **Client authentication** (confidential)
4. Set **Valid redirect URIs**: `https://your-app/callback`
5. Set **Web origins**: `https://your-app`
6. Under the **Credentials** tab, copy the client secret
7. Optional: under **Client scopes**, add `roles` if you want realm/resource role claims

```env
OIDC_DISCOVERY_URL=http://keycloak:8080/realms/<realm>/.well-known/openid-configuration
OIDC_CLIENT_ID=oidc-diagnostic
OIDC_CLIENT_SECRET=<from credentials tab>
OIDC_SCOPE=openid email profile roles
OIDC_PKCE_METHOD=S256
OIDC_TOKEN_SIGNING_ALG=RS256
```

> Keycloak defaults to RS256 for token signing. ES256 can be enabled per-realm under **Realm settings → Tokens → Default signature algorithm**.

---

### Kanidm

1. As an admin, create an OAuth2 resource server:

```bash
kanidm system oauth2 create ssotest "OIDC Diagnostic" https://your-app/callback
kanidm system oauth2 update-scope-map ssotest <group> openid email profile
kanidm system oauth2 show-enable-pkce ssotest
```

1. Get the client secret:

```bash
kanidm system oauth2 show-basic-secret ssotest
```

```env
OIDC_DISCOVERY_URL=https://kanidm.example.com/oauth2/openid/ssotest/.well-known/openid-configuration
OIDC_CLIENT_ID=ssotest
OIDC_CLIENT_SECRET=<from show-basic-secret>
OIDC_SCOPE=openid email profile
OIDC_PKCE_METHOD=S256
OIDC_TOKEN_SIGNING_ALG=ES256
```

> Kanidm **requires** PKCE S256 — `OIDC_PKCE_METHOD=disabled` will be rejected.
> Kanidm uses ES256 by default and does not support RP-initiated logout.

---

### Authentik

1. Go to **Applications** → **Providers** → **Create** → **OAuth2/OpenID Provider**
2. Set **Redirect URIs**: `https://your-app/callback`
3. Under **Advanced settings**, set **Subject mode** and note the signing key
4. Create an **Application** and link it to the provider
5. Copy the **Client ID** and **Client Secret** from the provider page

```env
OIDC_DISCOVERY_URL=https://authentik.example.com/application/o/<slug>/.well-known/openid-configuration
OIDC_CLIENT_ID=<client id>
OIDC_CLIENT_SECRET=<client secret>
OIDC_SCOPE=openid email profile
OIDC_PKCE_METHOD=S256
OIDC_TOKEN_SIGNING_ALG=RS256
```

---

### Microsoft Entra ID (Azure AD)

1. Go to **Azure Portal** → **App registrations** → **New registration**
2. Set **Redirect URI** (Web): `https://your-app/callback`
3. Under **Certificates & secrets**, create a **Client secret**
4. Under **API permissions**, add `openid`, `email`, `profile`

```env
OIDC_DISCOVERY_URL=https://login.microsoftonline.com/<tenant-id>/v2.0/.well-known/openid-configuration
OIDC_CLIENT_ID=<application/client id>
OIDC_CLIENT_SECRET=<client secret value>
OIDC_SCOPE=openid email profile
OIDC_PKCE_METHOD=S256
OIDC_TOKEN_SIGNING_ALG=RS256
```

> Entra uses RS256. The `roles` claim requires app roles to be defined and assigned in the manifest.

---

### Okta

1. Go to **Applications** → **Create App Integration** → **OIDC - OpenID Connect** → **Web Application**
2. Set **Sign-in redirect URIs**: `https://your-app/callback`
3. Copy the **Client ID** and **Client secret**

```env
OIDC_DISCOVERY_URL=https://<your-okta-domain>/oauth2/default/.well-known/openid-configuration
OIDC_CLIENT_ID=<client id>
OIDC_CLIENT_SECRET=<client secret>
OIDC_SCOPE=openid email profile groups
OIDC_PKCE_METHOD=S256
OIDC_TOKEN_SIGNING_ALG=RS256
```

---

## Configuration Reference

All configuration is via environment variables in a `.env` file.

### OIDC Provider

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `OIDC_DISCOVERY_URL` | Yes | — | Provider's `/.well-known/openid-configuration` URL |
| `OIDC_CLIENT_ID` | Yes | — | OAuth2 client ID |
| `OIDC_CLIENT_SECRET` | Yes | — | OAuth2 client secret |
| `OIDC_SCOPE` | No | `openid email profile` | Space-separated scopes to request |
| `OIDC_PKCE_METHOD` | No | `S256` | PKCE method: `S256`, `plain`, or `disabled` |
| `OIDC_TOKEN_SIGNING_ALG` | No | *(auto)* | Enforce a signing algorithm: `ES256` or `RS256`. Unset = accept server's default |

### Flask / Server

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `SECRET_KEY` | Yes | *(random, ephemeral)* | Flask session key — set a fixed value or sessions won't survive restarts |
| `PORT` | No | `5000` | Port to listen on |
| `FLASK_DEBUG` | No | `false` | Enable Flask debug mode — never use in production |
| `PREFERRED_URL_SCHEME` | No | *(auto)* | Force `https` in callback URLs if your proxy doesn't send `X-Forwarded-Proto` |

### UI

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `SHOW_CONFIG` | No | `false` | Show the configuration card (discovery URL, client ID, etc.) on the landing page |
| `GITHUB_URL` | No | *(repo)* | URL shown in the Help → Source code link |
| `KOFI_URL` | No | *(hidden)* | Ko-fi URL shown in the Help menu; hidden if unset |

---

## Scopes Reference

| Scope | Claims provided | Standard? |
| --- | --- | --- |
| `openid` | `sub`, `iss`, `aud`, `exp`, `iat` | Required |
| `email` | `email`, `email_verified` | OIDC |
| `profile` | `name`, `given_name`, `family_name`, `preferred_username`, `picture`, `locale`, `zoneinfo`, `updated_at` | OIDC |
| `address` | `address` | OIDC |
| `phone` | `phone_number`, `phone_number_verified` | OIDC |
| `offline_access` | *(no new claims — requests a refresh token)* | OIDC |
| `roles` | `realm_access`, `resource_access` | Keycloak-specific |
| `groups` | `groups` | Provider-specific |

Additional claims beyond these are typically available via **custom scopes** configured in your provider. The **Provider Metadata** panel on the home page lists `claims_supported` — every claim the server can return. If a claim you expect isn't appearing, check whether the required scope is in `OIDC_SCOPE` and is granted in your client's scope configuration.

---

## Logout

The **Sign out** button attempts RP-initiated logout: it redirects the browser to the provider's `end_session_endpoint` with the current ID token, which terminates the SSO session server-side. If the provider doesn't support this (e.g. Kanidm), a local-only session clear happens instead.

To enable RP-initiated logout in Keycloak, register `https://your-app/` as a **Valid post-logout redirect URI** in your client settings.

---

## Reverse Proxy (Traefik, nginx, etc.)

The app automatically reads `X-Forwarded-Proto` and `X-Forwarded-Host` headers, so HTTPS callback URLs generate correctly behind a TLS-terminating proxy with no extra configuration. Traefik forwards these headers by default.

If your proxy does not forward `X-Forwarded-Proto`, set `PREFERRED_URL_SCHEME=https` in `.env`.

Ensure the callback URL registered in your OIDC provider matches what the app generates — use the **Configuration** card (enable `SHOW_CONFIG=true`) or the home page to verify the exact callback URL being used.

---

## Building Locally

```bash
# Without Docker
pip install -r requirements.txt
cp .env.example .env
# Edit .env
python app.py

# With Docker (build from source)
docker compose -f docker-compose.build.yml up --build
```

---

## Docker Image Tags

Images are published to `ghcr.io/tfindley/sso_oidc_client_tool` on every push to `main` and on version tags.

| Tag           | When                         |
| ------------- | ---------------------------- |
| `latest`      | Every push to `main`         |
| `main`        | Every push to `main`         |
| `v1.2.3`      | On a `v1.2.3` git tag        |
| `1.2`         | On a `v1.2.x` git tag        |
| `sha-abc1234` | Every commit (immutable ref) |

Multi-arch: `linux/amd64` on every build; `linux/amd64` + `linux/arm64` on version tags.

---

## Security Note

This tool is intended for **internal diagnostic use only**. It stores raw token strings in a server-side session and decodes JWTs **without signature verification**. Do not expose it to the public internet. Use `SHOW_CONFIG=false` (the default) when the landing page may be seen by users who should not see your client credentials or discovery URL.
