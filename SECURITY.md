# Security Note

This tool is intended for **diagnostic use**. It decodes JWTs **without signature verification** — do not use it to make security decisions about token validity. Do not expose it to the public internet without HTTPS, `PRIVACY_NOTICE=true`, and an understanding of the data-handling properties described above. Use `SHOW_CONFIG=false` (the default) to avoid exposing client credentials or discovery URLs on the landing page.
