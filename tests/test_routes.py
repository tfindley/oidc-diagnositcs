"""Smoke tests for the HTTP routes.

These verify that each route renders without raising and that key markers
appear in the response body. They don't exercise the OIDC callback flow
(needs a real provider) or anything that makes outbound HTTP.
"""
import base64
import json


def _b64url(d: dict) -> str:
    return base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b'=').decode()


# ── / (landing) ──────────────────────────────────────────────────────

def test_index_renders(client):
    r = client.get('/')
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert 'OIDC Diagnostic' in body or 'Sign in' in body


# ── /claims unauthenticated ──────────────────────────────────────────

def test_claims_redirects_when_not_signed_in(client):
    """Hitting /claims without a session should redirect to landing, not 500."""
    r = client.get('/claims')
    assert r.status_code in (302, 401, 403)


# ── /decode ──────────────────────────────────────────────────────────

def test_decode_get_empty(client):
    r = client.get('/decode')
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert 'JWT Decoder' in body
    # Verify section is conditional on a decoded token — should be hidden here.
    assert 'Verify signature (JWKS)' not in body
    # Help button (added v0.2.4) links to the JWT reference tab.
    assert 'tab=jwt' in body


def test_decode_post_valid_jws_shows_verify(client):
    tok = (
        _b64url({'alg': 'RS256', 'typ': 'JWT'}) + '.'
        + _b64url({'sub': 'u', 'nonce': 'n', 'iss': 'http://i'}) + '.sig'
    )
    r = client.post('/decode', data={'token': tok})
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert 'Verify signature (JWKS)' in body  # JWS decoded → Verify section appears


def test_decode_post_jwe_shows_alert(client):
    """Pasting a 5-part JWE should land on the encrypted-JWT alert path."""
    tok = _b64url({'alg': 'A128KW', 'enc': 'A128GCM'}) + '.a.b.c.d'
    r = client.post('/decode', data={'token': tok})
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert 'Encrypted JWT (JWE)' in body
    # JWEs must NOT show the Verify section (no signature to verify).
    assert 'Verify signature (JWKS)' not in body


def test_decode_post_garbage_warns(client):
    r = client.post('/decode', data={'token': 'this is not a jwt'})
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert 'Not a valid JWT' in body or 'Decode error' in body


# ── /decode/history/* ────────────────────────────────────────────────

def test_history_clear_redirects(client):
    r = client.post('/decode/history/clear')
    assert r.status_code == 302
    assert '/decode' in r.headers.get('Location', '')


def test_history_delete_redirects(client):
    r = client.post('/decode/history/delete', data={'hash': 'nonexistent'})
    assert r.status_code == 302


def test_history_delete_only_removes_target(client):
    """Decode two distinct tokens, delete one by hash, the other survives."""
    t1 = _b64url({'alg': 'RS256'}) + '.' + _b64url({'sub': 'alice', 'iss': 'http://i'}) + '.s'
    t2 = _b64url({'alg': 'RS256'}) + '.' + _b64url({'sub': 'bob',   'iss': 'http://i'}) + '.s'
    client.post('/decode', data={'token': t1})
    client.post('/decode', data={'token': t2})

    with client.session_transaction() as sess:
        history = sess.get('decoder_history', [])
        assert len(history) == 2
        target_hash = history[0]['hash']  # the bob entry (newest first)
        survivor_hash = history[1]['hash']

    client.post('/decode/history/delete', data={'hash': target_hash})

    with client.session_transaction() as sess:
        remaining = sess.get('decoder_history', [])
        assert len(remaining) == 1
        assert remaining[0]['hash'] == survivor_hash


# ── /reference ───────────────────────────────────────────────────────

def test_reference_jwt_tab(client):
    r = client.get('/reference?tab=jwt')
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert 'data-panel="jwt"' in body
    assert 'What is a JWT?' in body
    assert 'How to get a JWT' in body


def test_reference_unknown_tab_falls_back(client):
    r = client.get('/reference?tab=bogus')
    assert r.status_code == 200  # falls back to default tab, doesn't 404


# ── /about ───────────────────────────────────────────────────────────

def test_about_shows_version(client):
    r = client.get('/about')
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert 'About' in body
    # Version badge: APP_VERSION env-var or 'dev' fallback. Badge wraps in 'v…'.
    assert 'vdev' in body or 'v0.' in body


# ── /decode pre-load from session ────────────────────────────────────

def test_decode_from_session_marks_known_type(client):
    """Loading a token via ?from_session=…&token_type=… should label it
    according to the slot, even when payload heuristics disagree."""
    # Build a token whose payload would heuristically look like 'ID' (has nonce).
    tok = (
        _b64url({'alg': 'RS256'}) + '.'
        + _b64url({'sub': 'u', 'nonce': 'n', 'iss': 'http://i'}) + '.s'
    )
    with client.session_transaction() as sess:
        sess['raw_tokens'] = {'access_token': tok}

    client.get('/decode?from_session=1&token_type=access_token')

    with client.session_transaction() as sess:
        history = sess.get('decoder_history', [])
        assert len(history) == 1
        # Slot says access_token → must label 'Access' regardless of nonce-heuristic.
        assert history[0]['token_type'] == 'Access'
