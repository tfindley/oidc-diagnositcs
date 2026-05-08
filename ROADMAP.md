# Roadmap

Ideas captured for future versions. Not committed to a release schedule. Items are listed roughly in the order they would be most useful to implement.

All items below depend on the encrypted server-side session store introduced for the EntraID large-claim fix — they would not have been practical with the previous client-side cookie design.

---

## ~~JWT decoder history with comparison~~ ✓ shipped (v0.2.0–v0.2.4)

Every successful decode is stored in `session['decoder_history']` (max 10, deduped by payload hash). The decoder page shows an always-expanded "Recent decodes" table with **Recall**, **A**/**B** toggle, and **✕ Delete** per row. Toggling A on one row and B on another renders the claim-by-claim diff inline below the table; toggling the same button again deselects.

Type detection labels each row as ID / Access / Refresh / Unknown — explicit `typ` headers (Keycloak, RFC 9068) plus a `nonce` → ID and `scope`/`scp` → Access fallback for providers (Kanidm, Authentik, others) that emit no `typ`.

## ~~Push current tokens to JWT decoder~~ ✓ shipped (v0.2.0)

"Open in Decoder" button on each raw token in the Claims → Raw JWT tab. The decoder page also shows a "Load from active session" panel with one-click ID / Access / Refresh buttons when signed in. Tokens loaded via this path are labelled by slot (not by detection), so an Access token always reads "Access". Encrypted refresh tokens (5-part JWEs, common with Kanidm) render as a static badge instead of a clickable button — no dead-end JWE alert.

## ~~CI: PR-validation workflow~~ ✓ shipped (v0.2.5)

`.github/workflows/test.yml` runs the pytest suite on every pull request to `main`. The release workflow (`.github/workflows/release.yml`) still gates only on version tags, so PRs go through CI before they can produce an image.

## Side-by-side OIDC profile comparison

Today the multi-provider design enforces a single signed-in user at a time. With server-side sessions it becomes practical to keep more than one provider session alive in parallel and compare them live.

- Allow simultaneous sessions for different providers, namespaced under separate session keys (e.g. `session['providers']['<id>']['raw_tokens']`).
- New view that renders two providers' claim tables side-by-side with diff highlighting — re-using the inline-diff renderer from the decoder.
- Removes the "log into one, screenshot, log into the other, compare manually" loop that's currently the only way to compare claim shapes between providers.
- Likely the largest item on the roadmap — touches session-keying, the nav UI, and the claims page. Decoder history would also benefit (currently wiped by `session.clear()` on login/logout because it lives at the top level of the session dict).

## Decoder history persistence across login/logout

Decoder history is currently wiped whenever the user signs in or out, because both call `session.clear()`. This is more annoying now that the history table is always-expanded. Likely fixed as a side-effect of the session-namespacing redesign above (decoder history would move outside the per-provider namespace), but could also be patched in isolation by saving and restoring `decoder_history` around the `session.clear()` call.
