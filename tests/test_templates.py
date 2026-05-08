"""Direct Jinja2 render smoke tests.

Most templates are exercised through route tests in test_routes.py — these
catch the few that aren't (or aren't fully) covered there: the macros file,
and edge-case render contexts (e.g. /decode with all four states: empty,
decoded JWS, decoded JWE, errored).

A render that doesn't raise = pass. We're catching syntax errors and missing-
context-var bugs, not asserting on the output shape (route tests do that).
"""
import time

import pytest


def _ctx(**overrides):
    """Minimal-but-complete template context that satisfies decode.html, reference.html, and about.html."""
    base = dict(
        decoder_history=[], session_token_types=[], session_token_jwes=[],
        token_input='', decoded=None, claims_list=None,
        now=int(time.time()), claim_descriptions={}, jwks_uri='',
        # base.html context_processor vars
        github_url='https://example.com', kofi_url='', show_config=False,
        privacy_notice=False, banner_text='', banner_type='info',
        flask_debug=False, nav_expires_at=None, nav_has_refresh=False,
        nav_providers=[], nav_multi_provider=False, nav_session_expires_at=None,
        app_version='dev', active_tab='connectivity',
    )
    base.update(overrides)
    return base


def _render(app, name, **ctx_overrides):
    with app.app_context(), app.test_request_context('/'):
        return app.jinja_env.get_template(name).render(**_ctx(**ctx_overrides))


# ── Templates ────────────────────────────────────────────────────────

@pytest.mark.parametrize('template_name', [
    'base.html',
    'index.html',
    'decode.html',
    'reference.html',
    'about.html',
    'conformance.html',
])
def test_template_renders_with_minimal_context(app, template_name):
    """Each top-level template should at least render without raising."""
    out = _render(app, template_name)
    assert '<html' in out or '<!DOCTYPE' in out  # full HTML doc, since they all extend base.html


def test_decode_html_with_history_and_jwe(app):
    """The most state-heavy combination: history present, refresh-as-JWE."""
    history = [
        {'hash': 'a', 'ts': int(time.time()) - 60, 'label': 'alice', 'token_type': 'ID',     'token_raw': 'eyJ.eyJ.s'},
        {'hash': 'b', 'ts': int(time.time()) - 30, 'label': 'bob',   'token_type': 'Access', 'token_raw': 'eyJ.eyJ.s'},
    ]
    out = _render(
        app, 'decode.html',
        decoder_history=history,
        session_token_types=['id_token', 'access_token', 'refresh_token'],
        session_token_jwes=['refresh_token'],
    )
    # History block markers
    assert 'Recent decodes (2)' in out
    assert 'hist-toggle-a' in out
    assert 'hist-delete' in out
    # JWE refresh slot rendered as static badge
    assert '(encrypted JWE)' in out
    # ID + access still clickable links
    assert 'token_type=id_token' in out
    assert 'token_type=access_token' in out


def test_reference_jwt_tab_renders(app):
    out = _render(app, 'reference.html', active_tab='jwt')
    assert 'data-panel="jwt"' in out
    assert 'What is a JWT?' in out
    assert 'How to get a JWT' in out
