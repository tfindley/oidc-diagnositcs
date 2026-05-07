# Roadmap

Ideas captured for future versions. Not committed to a release schedule. Items are listed roughly in the order they would be most useful to implement.

All items below depend on the encrypted server-side session store introduced for the EntraID large-claim fix — they would not have been practical with the previous client-side cookie design.

---

## ~~JWT decoder history with comparison~~ ✓ shipped

~~Persist decoded JWTs in the session so the decoder page (`/decode`) can offer a recall list and side-by-side comparison.~~

Implemented: every successful decode is stored in `session['decoder_history']` (max 10, deduped by payload hash). The decoder page shows a "Recent decodes" collapsible with recall, → A / → B diff-slot loading, and a "Compare selected" button for one-click two-token comparison.

## ~~Push current tokens to JWT decoder~~ ✓ shipped

~~Add a "Push to decoder" button on the `/claims` page that pre-loads the active session's ID, access, and refresh tokens into `/decode`.~~

Implemented: "Open in Decoder" button on each raw token in the Claims → Raw JWT tab. The decoder page also shows a "Load from active session" panel with per-token-type buttons when the user is signed in.

## Side-by-side OIDC profile comparison

Today the multi-provider design enforces a single signed-in user at a time. With server-side sessions it becomes practical to keep more than one provider session alive in parallel and compare them live.

- Allow simultaneous sessions for different providers, namespaced under separate session keys.
- New view that renders two providers' claim tables side-by-side with diff highlighting.
- Removes the "log into one, screenshot, log into the other, compare manually" loop that's currently the only way to compare claim shapes between providers.
- Likely the largest item on the roadmap — touches session-keying, the nav UI, and the claims page.

## CI: PR-validation workflow

The current CI builds and pushes only on version tags (intentionally). A separate PR-validation workflow that builds the image without pushing — and optionally runs lint / smoke tests — would catch breakage before tagging. Out of scope for the EntraID fix; worth a follow-up.
