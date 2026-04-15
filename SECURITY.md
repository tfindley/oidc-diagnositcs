# Security

## Intended use

This tool is intended for **diagnostic use only**. It decodes JWTs **without signature verification** — do not use decoded claims to make security decisions about token validity. Use the built-in JWKS signature verification feature (JWT Decoder page) when you need to cryptographically verify a token.

## Deployment hardening

- Do not expose this tool to the public internet without HTTPS.
- Set `PRIVACY_NOTICE=true` so users understand the data-handling model.
- Keep `SHOW_CONFIG=false` (the default) to avoid exposing client credentials or discovery URLs on the landing page.
- Set `FLASK_DEBUG=false` (the default). Debug mode can surface token values in error traces.
- Use a strong, random `SECRET_KEY` — this signs every session cookie.
- Request the minimum scopes you need (`openid email profile` is sufficient for most diagnostic purposes).

See [Data Handling & Privacy](README.md#data-handling--privacy) in the README for the full trust model.

## Vulnerability tracking

Known CVEs in the dependency chain are tracked and triaged in [docs/RISK_REGISTER.md](docs/RISK_REGISTER.md).

## Reporting a vulnerability

Please report security vulnerabilities via the [GitHub Issues tracker](https://github.com/tfindley/oidc-diagnositcs/issues). For sensitive disclosures, contact the maintainer directly via the profile linked in the README.
