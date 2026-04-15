# Identity Brokering

**Identity brokering** is when your SSO server (e.g. Keycloak) does not authenticate the user directly — instead it delegates to an *upstream identity provider* such as Microsoft Entra ID, Google, GitHub, or another OIDC/SAML server. Keycloak acts as the *broker*: it handles the upstream authentication, maps the upstream claims to its own local claims, then issues its own tokens to this application.

From this app's perspective the flow looks like a normal OIDC login; the upstream hops happen entirely behind Keycloak.

## Sequence diagram

```
Browser             This App            Keycloak (Broker)   Upstream IdP
  │                   │                   │                   │
  │  GET /login       │                   │                   │
  │ ─────────────────►│                   │                   │
  │                   │ Generate PKCE     │                   │
  │  302 → /authorize │                   │                   │
  │◄──────────────────│                   │                   │
  │                   │                   │                   │
  │  GET /authorize   │                   │                   │
  │ ──────────────────────────────────────►│                   │
  │                   │                   │ 302 → upstream    │
  │                   │                   │ /authorize        │
  │◄──────────────────────────────────────│                   │
  │                   │                   │                   │
  │  GET /authorize   │                   │                   │
  │  (upstream IdP)   │                   │                   │
  │ ──────────────────────────────────────────────────────────►│
  │                   │                   │                   │  Show login UI
  │  User logs in     │                   │                   │
  │◄──────────────────────────────────────────────────────────│
  │                   │                   │                   │
  │  302 → Keycloak   │                   │                   │
  │  /callback+code   │                   │                   │
  │ ──────────────────────────────────────►│                   │
  │                   │                   │ POST /token       │
  │                   │                   │──────────────────►│
  │                   │                   │  id_token,        │
  │                   │                   │  access_token     │
  │                   │                   │◄──────────────────│
  │                   │                   │ Map claims        │
  │                   │                   │ Issue tokens      │
  │  302 → /callback  │                   │                   │
  │◄──────────────────────────────────────│                   │
  │                   │                   │                   │
  │  GET /callback    │                   │                   │
  │  ?code=...        │                   │                   │
  │ ─────────────────►│                   │                   │
  │                   │ POST /token       │                   │
  │                   │──────────────────►│                   │
  │                   │  access_token,    │                   │
  │                   │  id_token,        │                   │
  │                   │  refresh_token    │                   │
  │                   │◄──────────────────│                   │
  │                   │ GET /userinfo     │                   │
  │                   │──────────────────►│                   │
  │                   │◄──────────────────│                   │
  │  302 → /claims    │                   │                   │
  │◄──────────────────│                   │                   │
```

> If multiple upstream IdPs are configured in Keycloak, an IdP selection screen is shown to the user between the `GET /authorize` and `302 → upstream /authorize` steps.

## What this means for your tokens

| Claim | Behaviour with identity brokering |
| --- | --- |
| `iss` | Always **Keycloak's issuer URL** — never the upstream IdP. The broker rewrites the issuer before issuing tokens to this app. |
| `sub` | A Keycloak-assigned identifier for the brokered user — not the upstream IdP's subject. Keycloak may create a local account linked to the upstream identity, or use a derived persistent ID depending on broker configuration. |
| `email`, `name` | Sourced from the upstream IdP via Keycloak's claim mappers. May be absent if the upstream IdP does not release them or the mapper is not configured. |
| `acr` | Authentication context as reported by Keycloak. May reflect the upstream IdP's MFA level if Keycloak is configured to pass it through. |
| Upstream attributes | Any upstream IdP claims you want visible here must be explicitly mapped in Keycloak's identity provider mapper configuration. Unmapped claims are silently discarded. |

## Common diagnostic issues

### Missing claims after brokered login

Check two places:

1. Whether the upstream IdP is releasing the claim to Keycloak.
2. Whether Keycloak has an identity provider mapper configured to forward it into the local token.

Both must be in place — a claim released by the upstream IdP but not mapped in Keycloak will not appear here.

### Unexpected `sub` value

Keycloak assigns its own local subject identifier to brokered users. The upstream IdP's subject is not directly exposed unless you explicitly add an identity provider attribute mapper for it in Keycloak.

### Callback URL registration

Keycloak's OIDC client for this app must include the app's `/callback` URL as a valid redirect URI. For multi-provider deployments, each provider has its own path: `/callback/<provider_id>`. See the [OIDC Flow](oidc-flow.md) document for the full callback sequence.

## Keycloak configuration

To configure identity brokering in Keycloak:

1. Go to your realm → **Identity Providers** → **Add provider**
2. Select the upstream protocol (OIDC, SAML, or a social provider like GitHub, Google, etc.)
3. Configure the upstream IdP's credentials and endpoints
4. Under **Mappers**, add attribute mappers to forward the upstream claims you need into Keycloak's local token

See the [Keycloak Identity Brokering documentation](https://www.keycloak.org/docs/latest/server_admin/#_identity_broker) for full details.
