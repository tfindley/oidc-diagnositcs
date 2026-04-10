# OIDC Diagnostic Tool

A lightweight web application that acts as an OIDC client for diagnosing SSO systems. Log in via your provider (Keycloak, Entra ID, Okta, etc.) and inspect every claim from the ID token, access token, and UserInfo endpoint side by side.

## Features

- **Five-tab claims view** — ID Token · Access Token · UserInfo · Compare · Raw JWT
- **Compare tab** — shows every unique claim key across all three sources and flags ⚠ where the same claim has different values
- **Live search** — filter claims by name or value instantly
- **Mask sensitive values** — blur `sub`, `email`, `name`, etc. for safe screenshotting
- **Token expiry countdown** — live timer showing how long the session token remains valid
- **Copy buttons** — per-claim copy and full JSON export
- **Standalone JWT decoder** — paste any token and decode it without logging in

---

## Quickstart with Docker

The fastest way to run the tool is with the pre-built image from GitHub Container Registry.

**1. Create a `.env` file** (copy from the example):

```bash
curl -o .env https://raw.githubusercontent.com/tfindley/sso_oidc_client_tool/main/.env.example
# then edit .env with your provider details
```

Or create it manually:

```env
OIDC_DISCOVERY_URL=http://your-keycloak:8080/realms/your-realm/.well-known/openid-configuration
OIDC_CLIENT_ID=oidc-diagnostic-client
OIDC_CLIENT_SECRET=your-client-secret
OIDC_SCOPE=openid email profile roles
SECRET_KEY=change-this-to-a-random-secret
PORT=5000
```

**2. Run with Docker Compose:**

```bash
docker compose up
```

Then open [http://localhost:5000](http://localhost:5000).

---

## Keycloak Setup

In your Keycloak realm, create a new **OpenID Connect** client:

| Setting              | Value                           |
| -------------------- | ------------------------------- |
| Client type          | OpenID Connect                  |
| Client authentication| On (confidential)               |
| Valid redirect URIs  | `http://localhost:5000/callback`|
| Web origins          | `http://localhost:5000`         |

After saving, go to the **Credentials** tab to get the client secret.

Your discovery URL will be:

```text
http://<keycloak-host>:8080/realms/<realm-name>/.well-known/openid-configuration
```

---

## Building and Running Locally (without Docker)

```bash
# Install Python 3.11+
pip install -r requirements.txt

cp .env.example .env
# Edit .env

python app.py
```

---

## Building the Docker Image Locally

Use the build compose file to build and run from source:

```bash
docker compose -f docker-compose.build.yml up --build
```

To build the image without running:

```bash
docker build -t oidc-diagnostic-tool:local .
```

---

## Docker Image Tags

Images are published to GitHub Container Registry on every push to `main` and on version tags:

| Tag            | When                          |
| -------------- | ----------------------------- |
| `latest`       | Every push to `main`          |
| `main`         | Every push to `main`          |
| `v1.2.3`       | On a `v1.2.3` git tag         |
| `1.2`          | On a `v1.2.x` git tag         |
| `sha-abc1234`  | Every commit (immutable ref)  |

Pull the latest:

```bash
docker pull ghcr.io/YOUR_ORG/YOUR_REPO:latest
```

---

## Configuration Reference

All configuration is via environment variables (or a `.env` file):

| Variable              | Required | Description                                                                                              |
| --------------------- | -------- | -------------------------------------------------------------------------------------------------------- |
| `OIDC_DISCOVERY_URL`  | Yes      | Provider's `/.well-known/openid-configuration` URL                                                       |
| `OIDC_CLIENT_ID`      | Yes      | OAuth client ID                                                                                          |
| `OIDC_CLIENT_SECRET`  | Yes      | OAuth client secret                                                                                      |
| `OIDC_SCOPE`          | No       | Scopes to request (default: `openid email profile`)                                                      |
| `SECRET_KEY`          | Yes      | Flask session secret — generate with `python -c "import secrets; print(secrets.token_hex(32))"`          |
| `PORT`                | No       | Port to listen on (default: `5000`)                                                                      |
| `FLASK_DEBUG`         | No       | Set to `true` for debug mode (never in production)                                                       |

---

## Security Note

This tool is intended for **internal diagnostic use only**. It stores raw token strings in a server-side session and decodes JWTs **without signature verification**. Do not expose it to the public internet.
