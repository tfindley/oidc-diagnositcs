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

### Optional Keycloak scopes

| Scope | Claims returned | How to enable |
| --- | --- | --- |
| `roles` | `realm_access`, `resource_access` | Add the `roles` client scope to your client under **Client scopes** |
| `groups` | `groups` | Requires a custom group mapper; add a **Group Membership** mapper to your client's dedicated scope |
| `offline_access` | *(no claims — issues a refresh token)* | Allow `offline_access` in **Client scopes**; request it in `OIDC_SCOPE` |
| `microprofile-jwt` | `upn`, `groups` | Keycloak-specific; mirrors the MicroProfile JWT spec |

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

### Optional Kanidm scopes

| Scope | Claims returned | How to enable |
| --- | --- | --- |
| `groups` | `groups` (array of group names) | Add `groups` to the `update-scope-map` command: `kanidm system oauth2 update-scope-map ssotest <group> openid email profile groups` |
| `offline_access` | *(no claims — issues a refresh token)* | Add `offline_access` to the scope map; request it in `OIDC_SCOPE` |

> The `groups` claim returns the names of Kanidm groups the user is a member of. Only groups explicitly added to the scope map are eligible — Kanidm uses this to control which group memberships are disclosed to each OAuth2 client.
> The `roles` scope is **not** supported by Kanidm; `realm_access` / `resource_access` claims will not appear.

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

### Optional Authentik scopes

| Scope | Claims returned | How to enable |
| --- | --- | --- |
| `groups` | `groups` (array of group names or UUIDs) | Add a **Group Membership** scope mapping in the provider's **Scope mappings** settings |
| `offline_access` | *(no claims — issues a refresh token)* | Enable **Include Refresh Token** in the provider's advanced settings |
| `roles` | `roles` or custom claim | Requires a custom Property Mapping that returns role data |

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

### Optional Entra ID scopes

| Scope | Claims returned | How to enable |
| --- | --- | --- |
| `offline_access` | *(no claims — issues a refresh token)* | Add `offline_access` to **API permissions** and to `OIDC_SCOPE` |
| `User.Read` | Graph profile data (not standard OIDC claims) | MS Graph permission, not surfaced as JWT claims by default |

> Entra exposes group membership via the `groups` claim, but it requires enabling **Group claims** in the **Token configuration** section of the app registration. For users in many groups, Entra may return a `hasgroups: true` claim instead and require a separate MS Graph call — this tool does not make that call.

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

### Optional Okta scopes

| Scope | Claims returned | How to enable |
| --- | --- | --- |
| `groups` | `groups` (array of group names) | In the **Sign-On Policy** or **Groups claim filter**, add a `groups` claim to the ID token or access token; configure it in the Okta authorization server's **Claims** settings |
| `offline_access` | *(no claims — issues a refresh token)* | Enable **Refresh Token** in the application's **Grant type** settings |

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