Run all the cheap checks I'd want to pass before opening a PR or shipping. Stops at the first failure — fix it before continuing.

Run each step in order. Show the output of each. If any step fails, stop and report exactly which one and why.

## 1. Python syntax check

```bash
python3 -m py_compile app.py
```

Should produce no output. Any output = syntax error.

## 2. Pytest suite

```bash
pytest tests/ -q
```

All tests must pass. If a route smoke test fails, the most common causes are: a template variable was renamed without updating the route, a Jinja2 expression got auto-escape-surprised, or a route was added/removed without updating tests.

## 3. Template direct render check

The pytest suite already covers `base.html`, `index.html`, `decode.html`, `reference.html`, `about.html`, `conformance.html` under [tests/test_templates.py](tests/test_templates.py). If you've added a new top-level template, add it to the parametrized list there.

## 4. Quick git review

```bash
git status
git diff --stat
```

Sanity check: are the files changed the ones you expected? Anything untracked you forgot to stage? Any debug `print()` or `console.log()` left behind?

## What this doesn't catch

- Behaviour against a real OIDC provider (sign-in flow, JWKS verification, token refresh) — that needs a live Keycloak/Kanidm/EntraID.
- Visual regressions in the UI — open the dev server and click around for layout changes.
- Performance regressions.

If all four steps pass, the changes are reasonably safe to push. Use `/ship` next.
