# Scopes & Claims

The claims you receive depend entirely on which scopes you request. Add scopes to `OIDC_SCOPE` in your `.env` file (or the `scope` field in `providers.yml`). You must also grant the scopes in your provider's client configuration.

## Standard OIDC scopes

| Scope | Claims provided | Notes |
| --- | --- | --- |
| `openid` | `sub`, `iss`, `aud`, `exp`, `iat` | **Required** — activates OIDC mode |
| `email` | `email`, `email_verified` | Standard OIDC |
| `profile` | `name`, `given_name`, `family_name`, `preferred_username`, `picture`, `locale`, `zoneinfo`, `updated_at` | Standard OIDC |
| `address` | `address` | Standard OIDC — rarely used |
| `phone` | `phone_number`, `phone_number_verified` | Standard OIDC — rarely used |
| `offline_access` | *(no new claims)* | Requests a refresh token; provider must allow it |

## Provider-specific scopes

| Scope | Claims provided | Provider |
| --- | --- | --- |
| `roles` | `realm_access`, `resource_access` | Keycloak |
| `groups` | `groups` | Provider-specific — varies by server |

Additional claims beyond these are available via **custom scopes** configured in your provider. The **Provider Metadata** panel on the home page lists `claims_supported` — every claim the server can return.

## Adding scopes

You cannot add scopes mid-session — OIDC scopes are negotiated at login time. To get additional claims:

1. Add the scopes to `OIDC_SCOPE` in `.env` (or `scope` in `providers.yml`).
2. Ensure the scopes are granted in your provider's client or consent settings.
3. Sign out and sign back in. The new claims will appear on the next login.

## Provider-specific guides

See [PROVIDERS.md](../PROVIDERS.md) for scope configuration instructions for Keycloak, Kanidm, Authentik, Entra ID, and Okta.
