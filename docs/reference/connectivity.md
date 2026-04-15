# Connectivity

An OIDC login involves three parties. All of the network paths below must be reachable for login to work.

## Required paths

### Browser
The user's browser must be able to reach:
- This app — to load `/`, `/login`, `/claims`, etc.
- The SSO server's `/authorize` endpoint — to display the login UI (the browser is redirected there).
- This app's `/callback` — to receive the auth code after login (the SSO server redirects back here).

### This app (server)
The app server must be able to reach the SSO server's back-channel endpoints:
- `/.well-known/openid-configuration` — fetched on startup and at login to discover all endpoint URLs.
- `token_endpoint` — to exchange the auth code for tokens (back-channel, never goes through the browser).
- `jwks_uri` — to fetch public keys for token signature verification.
- `userinfo_endpoint` — to fetch profile claims.

```
Browser                     This App (server)           SSO Server
  │                               │                          │
  ├── GET /, /login, /claims ────►│                          │
  │◄── HTML / redirects ──────────│                          │
  │                               │                          │
  ├── GET /authorize ─────────────────────────────────────► │
  │◄── Login UI ──────────────────────────────────────────── │
  │                               │                          │
  ├── GET /callback?code=... ────►│                          │
  │                               ├── POST /token ──────────►│
  │                               ├── GET /jwks_uri ────────►│
  │                               ├── GET /userinfo ────────►│
  │◄── 302 /claims ───────────────│                          │
```

## Common issue — Docker DNS

The browser can reach the SSO server's login page, but the app's back-channel token exchange fails. This happens when the app container cannot resolve the SSO server's hostname — DNS inside Docker differs from the host machine.

**Diagnosis:** Use the **Check connectivity** button on the home page. It tests both the browser-to-SSO path (via a `/api/connectivity` call proxied through the app server) and shows whether the hostname resolves correctly from inside the container.

**Fix:** Use the SSO server's Docker service name as the hostname in `OIDC_DISCOVERY_URL`, or add the hostname to the container's `/etc/hosts` via `extra_hosts` in your `docker-compose.yml`.

## Logout

RP-initiated logout sends the browser to the SSO server's `end_session_endpoint` with the `id_token_hint` and a `post_logout_redirect_uri`. Keycloak supports this; Kanidm currently does not — a local-only session clear happens instead.

Register the app's base URL (e.g. `https://your-app/`) as an allowed post-logout redirect URI in your OIDC client configuration.
