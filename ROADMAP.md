# Roadmap

Ideas captured for future versions. Not committed to a release schedule. Items are listed roughly in the order they would be most useful to implement.

All items below depend on the encrypted server-side session store introduced for the EntraID large-claim fix — they would not have been practical with the previous client-side cookie design.

---

## JWT decoder history with comparison

Persist decoded JWTs in the session so the decoder page (`/decode`) can offer a recall list and side-by-side comparison.

- Each decode adds an entry to `session['decoder_history']` keyed by a content hash so duplicates collapse.
- The decoder page renders a small recall table on load, with checkboxes to pick two for comparison.
- Selecting two enters the existing diff UI without re-pasting tokens.
- History is per-session (cleared at logout / session expiry). Appropriate for sensitive token material.

This was attempted previously with client-side storage; that implementation was unreliable (the recall table populated only after a fresh decode). Server-side session storage makes it straightforward.

## Push current tokens to JWT decoder

Add a "Push to decoder" button on the `/claims` page that pre-loads the active session's ID, access, and refresh tokens into `/decode` so they can be inspected with the decoder's full feature set (signature verification, expiry banner, type detection) without copy-paste.

- Wire-up is small: link to `/decode?from_session=1` and have the decoder pull from `session['raw_tokens']`.
- Useful when investigating signature problems or wanting the decoder's UI affordances on a token you're actively using.

## Side-by-side OIDC profile comparison

Today the multi-provider design enforces a single signed-in user at a time. With server-side sessions it becomes practical to keep more than one provider session alive in parallel and compare them live.

- Allow simultaneous sessions for different providers, namespaced under separate session keys.
- New view that renders two providers' claim tables side-by-side with diff highlighting.
- Removes the "log into one, screenshot, log into the other, compare manually" loop that's currently the only way to compare claim shapes between providers.
- Likely the largest item on the roadmap — touches session-keying, the nav UI, and the claims page.

## CI: PR-validation workflow

The current CI builds and pushes only on version tags (intentionally). A separate PR-validation workflow that builds the image without pushing — and optionally runs lint / smoke tests — would catch breakage before tagging. Out of scope for the EntraID fix; worth a follow-up.
