# Provider Setup Guides

Is your provider missing? Raise an [issue](https://github.com/tfindley/oidc-diagnositcs/issues) with instructions and I'll do my best to include it.

> **Callback URL:** When using single-provider mode the callback URL is `https://your-app/callback`. When using multi-provider mode (`providers.yml`) the callback URL is `https://your-app/callback/<id>` where `<id>` matches the `id` field in your provider entry. Register the correct URL in your provider before testing.

## Keycloak

1. In your realm go to **Clients** → **Create client**
2. Set **Client type** to `OpenID Connect`
3. Enable **Client authentication** (confidential)
4. Set **Valid redirect URIs**: `https://your-app/callback` (single-provider) or `https://your-app/callback/keycloak` (multi-provider)
5. Set **Web origins**: `https://your-app`
6. Under the **Credentials** tab, copy the client secret
7. Optional: under **Client scopes**, add `roles` if you want realm/resource role claims
8. For RP-initiated logout: add `https://your-app/` as a **Valid post-logout redirect URI**

**Single-provider `.env`:**

```env
OIDC_DISCOVERY_URL=http://keycloak:8080/realms/<realm>/.well-known/openid-configuration
OIDC_CLIENT_ID=oidc-diagnostic
OIDC_CLIENT_SECRET=<from credentials tab>
OIDC_SCOPE=openid email profile roles
OIDC_PKCE_METHOD=S256
OIDC_TOKEN_SIGNING_ALG=RS256
```

**Multi-provider `providers.yml`:**

```yaml
providers:
  - name: Keycloak
    id: keycloak          # callback URL: https://your-app/callback/keycloak
    discovery_url: http://keycloak:8080/realms/<realm>/.well-known/openid-configuration
    client_id: oidc-diagnostic
    client_secret: <from credentials tab>
    scope: openid email profile roles
    pkce_method: S256
    token_signing_alg: RS256
```

> Keycloak defaults to RS256 for token signing. ES256 can be enabled per-realm under **Realm settings → Tokens → Default signature algorithm**.

---

## Kanidm

1. As an admin, create an OAuth2 resource server:

```bash
kanidm system oauth2 create ssotest "OIDC Diagnostic" https://your-app/callback
kanidm system oauth2 update-scope-map ssotest <group> openid email profile
kanidm system oauth2 show-enable-pkce ssotest
```

For multi-provider, use the correct callback URL when creating the resource server:

```bash
kanidm system oauth2 create ssotest "OIDC Diagnostic" https://your-app/callback/kanidm
```

1. Get the client secret:

```bash
kanidm system oauth2 show-basic-secret ssotest
```

**Single-provider `.env`:**

```env
OIDC_DISCOVERY_URL=https://kanidm.example.com/oauth2/openid/ssotest/.well-known/openid-configuration
OIDC_CLIENT_ID=ssotest
OIDC_CLIENT_SECRET=<from show-basic-secret>
OIDC_SCOPE=openid email profile
OIDC_PKCE_METHOD=S256
OIDC_TOKEN_SIGNING_ALG=ES256
```

**Multi-provider `providers.yml`:**

```yaml
providers:
  - name: Kanidm
    id: kanidm            # callback URL: https://your-app/callback/kanidm
    discovery_url: https://kanidm.example.com/oauth2/openid/ssotest/.well-known/openid-configuration
    client_id: ssotest
    client_secret: <from show-basic-secret>
    scope: openid email profile
    pkce_method: S256
    token_signing_alg: ES256
```

> Kanidm **requires** PKCE S256 — `pkce_method: disabled` will be rejected.
> Kanidm uses ES256 by default and does not support RP-initiated logout.

---

## Authentik

1. Go to **Applications** → **Providers** → **Create** → **OAuth2/OpenID Provider**
2. Set **Redirect URIs**: `https://your-app/callback` (single-provider) or `https://your-app/callback/authentik` (multi-provider)
3. Under **Advanced settings**, set **Subject mode** and note the signing key
4. Create an **Application** and link it to the provider
5. Copy the **Client ID** and **Client Secret** from the provider page

**Single-provider `.env`:**

```env
OIDC_DISCOVERY_URL=https://authentik.example.com/application/o/<slug>/.well-known/openid-configuration
OIDC_CLIENT_ID=<client id>
OIDC_CLIENT_SECRET=<client secret>
OIDC_SCOPE=openid email profile
OIDC_PKCE_METHOD=S256
OIDC_TOKEN_SIGNING_ALG=RS256
```

**Multi-provider `providers.yml`:**

```yaml
providers:
  - name: Authentik
    id: authentik         # callback URL: https://your-app/callback/authentik
    discovery_url: https://authentik.example.com/application/o/<slug>/.well-known/openid-configuration
    client_id: <client id>
    client_secret: <client secret>
    scope: openid email profile
    pkce_method: S256
    token_signing_alg: RS256
```

---

## Microsoft Entra ID (Azure AD)

1. Go to **Azure Portal** → **App registrations** → **New registration**
2. Set **Redirect URI** (Web): `https://your-app/callback` (single-provider) or `https://your-app/callback/entra` (multi-provider)
3. Under **Certificates & secrets**, create a **Client secret**
4. Under **API permissions**, add `openid`, `email`, `profile`

**Single-provider `.env`:**

```env
OIDC_DISCOVERY_URL=https://login.microsoftonline.com/<tenant-id>/v2.0/.well-known/openid-configuration
OIDC_CLIENT_ID=<application/client id>
OIDC_CLIENT_SECRET=<client secret value>
OIDC_SCOPE=openid email profile
OIDC_PKCE_METHOD=S256
OIDC_TOKEN_SIGNING_ALG=RS256
```

**Multi-provider `providers.yml`:**

```yaml
providers:
  - name: Microsoft Entra ID
    id: entra             # callback URL: https://your-app/callback/entra
    discovery_url: https://login.microsoftonline.com/<tenant-id>/v2.0/.well-known/openid-configuration
    client_id: <application/client id>
    client_secret: <client secret value>
    scope: openid email profile
    pkce_method: S256
    token_signing_alg: RS256
```

> Entra uses RS256. The `roles` claim requires app roles to be defined and assigned in the manifest.

---

## Okta

1. Go to **Applications** → **Create App Integration** → **OIDC - OpenID Connect** → **Web Application**
2. Set **Sign-in redirect URIs**: `https://your-app/callback` (single-provider) or `https://your-app/callback/okta` (multi-provider)
3. Copy the **Client ID** and **Client secret**

**Single-provider `.env`:**

```env
OIDC_DISCOVERY_URL=https://<your-okta-domain>/oauth2/default/.well-known/openid-configuration
OIDC_CLIENT_ID=<client id>
OIDC_CLIENT_SECRET=<client secret>
OIDC_SCOPE=openid email profile groups
OIDC_PKCE_METHOD=S256
OIDC_TOKEN_SIGNING_ALG=RS256
```

**Multi-provider `providers.yml`:**

```yaml
providers:
  - name: Okta
    id: okta              # callback URL: https://your-app/callback/okta
    discovery_url: https://<your-okta-domain>/oauth2/default/.well-known/openid-configuration
    client_id: <client id>
    client_secret: <client secret>
    scope: openid email profile groups
    pkce_method: S256
    token_signing_alg: RS256
```

---

## Using GitHub as an OIDC provider

GitHub's public OAuth service is **not a full OIDC provider** — it does not publish a `/.well-known/openid-configuration` discovery document for regular web-app login. You have a few options:

| Approach | Notes |
| --- | --- |
| **Google** | The simplest option. Create an OAuth2 client in [Google Cloud Console](https://console.cloud.google.com) (free). Discovery URL: `https://accounts.google.com/.well-known/openid-configuration`. Every visitor already has a Google account. |
| **Microsoft Entra ID** | Free personal Microsoft account tenant. Discovery URL: `https://login.microsoftonline.com/common/v2.0/.well-known/openid-configuration`. Also widely owned. |
| **Dex** (identity broker) | Self-hostable. Dex speaks full OIDC and can delegate authentication upstream to GitHub OAuth, Google, LDAP, etc. Run it in Docker Compose alongside this app. Good if you specifically want to show GitHub-branded login. |
| **Keycloak with GitHub social login** | Keycloak issues the OIDC tokens; GitHub is just the authentication backend. More moving parts but mirrors real enterprise deployments. |
| **Authentik** | Has a free cloud tier. GitHub social login built in. Issues full OIDC tokens. |
| **Auth0** | Free developer tier (up to 7,500 MAU). Full OIDC. Zero infrastructure to manage. |
| **Zitadel** | Open source with a free cloud tier. Full OIDC. GitHub social login supported. |