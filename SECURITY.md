# Security

## Intended use

This tool is intended for **diagnostic use only**. It decodes JWTs **without signature verification** — do not use decoded claims to make security decisions about token validity. Use the built-in JWKS signature verification feature (JWT Decoder page) when you need to cryptographically verify a token.

## Deployment hardening

- Do not expose this tool to the public internet without HTTPS.
- Set `PRIVACY_NOTICE=true` so users understand the data-handling model.
- Keep `SHOW_CONFIG=false` (the default) to avoid exposing client credentials or discovery URLs on the landing page.
- **Keep `FLASK_DEBUG=false` (the default).** Debug mode is incompatible with the zero-knowledge session design: the Werkzeug debugger and tracebacks can surface `SESSION_ENCRYPTION_PEPPER`, `SECRET_KEY`, and in-flight plaintext session data (decrypted tokens and userinfo) to anyone who can trigger an exception. Never enable debug mode on a network-reachable instance.
- Use a strong, random `SECRET_KEY` — this signs the session-ID cookie and is also used by Flask for other internal signing.
- Use a strong, random `SESSION_ENCRYPTION_PEPPER` — this is the server-held half of the session-encryption key. Treat it as critically as `SECRET_KEY`. Rotating it invalidates **all** active sessions immediately (which is intended behaviour and useful for emergency revocation).
- Mount `SESSION_FILE_DIR` (default `/tmp/flask_session`) as a tmpfs if you want session ciphertext to be unrecoverable across container restarts even before its TTL expires.
- Request the minimum scopes you need (`openid email profile` is sufficient for most diagnostic purposes).

See [Data Handling & Privacy](README.md#data-handling--privacy) in the README for the full trust model.

## Vulnerability tracking

Known CVEs in the dependency chain are tracked and triaged in [docs/RISK_REGISTER.md](docs/RISK_REGISTER.md).

## Reporting a vulnerability

Please report security vulnerabilities via the [GitHub Issues tracker](https://github.com/tfindley/oidc-diagnositcs/issues). For sensitive disclosures, contact the maintainer directly via the profile linked in the README.
