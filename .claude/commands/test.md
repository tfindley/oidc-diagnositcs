Run the pytest suite from the project root and report results.

```bash
pytest tests/ -q
```

If any test fails:
1. Read the failure output carefully — pytest's default output identifies the specific assertion that failed and the values that didn't match.
2. Look at the relevant code under test (most often [app.py](app.py) or [templates/](templates/)).
3. Fix the bug, not the test — unless the test itself encodes a stale assumption about the UI/API.
4. Re-run with `pytest tests/ -q` to confirm.

Don't add `--no-cov`, `-x`, or other flags unless explicitly asked. Don't skip tests.
