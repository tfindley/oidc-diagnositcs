"""Unit tests for pure helpers in app.py.

Focused on the functions that have actually broken or have non-trivial logic:
type detection (with the v0.2.4 nonce/scope fallback), decode_jwt's three-vs-
five-part branching, and decoder-history dedup/cap/known_type-override.
"""
import base64
import json

from app import _detect_token_type, _update_decoder_history, decode_jwt


def _b64url(d: dict) -> str:
    return base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b'=').decode()


def _make_jwt(header: dict, payload: dict, sig: str = 'sig') -> str:
    return _b64url(header) + '.' + _b64url(payload) + '.' + sig


# ── _detect_token_type ────────────────────────────────────────────────

def test_detect_keycloak_id():
    assert _detect_token_type({'typ': 'ID'}, {}) == 'ID'


def test_detect_keycloak_refresh():
    assert _detect_token_type({'typ': 'Refresh'}, {}) == 'Refresh'


def test_detect_keycloak_bearer_access():
    assert _detect_token_type({'typ': 'Bearer'}, {'typ': 'Bearer'}) == 'Access'


def test_detect_rfc9068_at_jwt():
    assert _detect_token_type({'typ': 'at+JWT'}, {}) == 'Access'


def test_detect_rfc9068_application_at_jwt():
    assert _detect_token_type({'typ': 'application/at+jwt'}, {}) == 'Access'


def test_fallback_nonce_means_id():
    """Kanidm-style ID token: no typ, but has nonce."""
    assert _detect_token_type({}, {'nonce': 'abc', 'sub': 'u'}) == 'ID'


def test_fallback_scope_means_access():
    """Kanidm-style access token: no typ, but has scope."""
    assert _detect_token_type({}, {'scope': 'openid email', 'sub': 'u'}) == 'Access'


def test_fallback_scp_means_access():
    """EntraID v2.0 access tokens use 'scp' instead of 'scope'."""
    assert _detect_token_type({}, {'scp': 'User.Read'}) == 'Access'


def test_unknown_when_no_signal():
    assert _detect_token_type({}, {'sub': 'u'}) == 'Unknown'


def test_explicit_typ_wins_over_heuristic():
    """Explicit typ should not be overridden by the scope-claim heuristic."""
    assert _detect_token_type({'typ': 'ID'}, {'scope': 'openid'}) == 'ID'


# ── decode_jwt ────────────────────────────────────────────────────────

def test_decode_jwt_three_part():
    tok = _make_jwt({'alg': 'RS256', 'typ': 'JWT'}, {'sub': 'u', 'iss': 'http://i'})
    out = decode_jwt(tok)
    assert out['header'] == {'alg': 'RS256', 'typ': 'JWT'}
    assert out['payload'] == {'sub': 'u', 'iss': 'http://i'}
    assert not out.get('error')
    assert not out.get('jwe')


def test_decode_jwt_five_part_jwe():
    tok = _b64url({'alg': 'A128KW', 'enc': 'A128GCM'}) + '.x.y.z.w'
    out = decode_jwt(tok)
    assert out.get('jwe') is True
    assert out.get('error')
    assert out['header']['alg'] == 'A128KW'


def test_decode_jwt_invalid_string():
    out = decode_jwt('not.a.valid.jwt')
    assert out.get('error')


def test_decode_jwt_handles_missing_padding():
    """Base64url payloads commonly drop trailing '=' padding — decode_jwt must restore it."""
    h = base64.urlsafe_b64encode(b'{"alg":"RS256"}').rstrip(b'=').decode()
    p = base64.urlsafe_b64encode(b'{"sub":"u"}').rstrip(b'=').decode()
    out = decode_jwt(f'{h}.{p}.sig')
    assert out['payload'] == {'sub': 'u'}


# ── _update_decoder_history ───────────────────────────────────────────

def _basic_decoded(sub: str = 'u') -> dict:
    return {
        'header': {'alg': 'RS256', 'typ': 'JWT'},
        'payload': {'sub': sub, 'iss': 'http://idp/realms/test'},
    }


def test_history_appends_new_entry():
    sess: dict = {}
    _update_decoder_history(sess, 'tok1', _basic_decoded('alice'))
    assert len(sess['decoder_history']) == 1
    assert sess['decoder_history'][0]['token_raw'] == 'tok1'


def test_history_dedup_by_payload_hash():
    sess: dict = {}
    _update_decoder_history(sess, 'tok', _basic_decoded('alice'))
    _update_decoder_history(sess, 'tok', _basic_decoded('alice'))
    assert len(sess['decoder_history']) == 1


def test_history_caps_at_ten():
    sess: dict = {}
    for i in range(15):
        _update_decoder_history(sess, f'tok{i}', _basic_decoded(f'user{i}'))
    assert len(sess['decoder_history']) == 10


def test_history_newest_first():
    sess: dict = {}
    _update_decoder_history(sess, 'first', _basic_decoded('alice'))
    _update_decoder_history(sess, 'second', _basic_decoded('bob'))
    assert sess['decoder_history'][0]['token_raw'] == 'second'


def test_history_known_type_overrides_detection():
    """known_type should bypass _detect_token_type (used for from-session loads)."""
    sess: dict = {}
    # Has nonce → detection would label 'ID'. known_type forces 'Access'.
    _update_decoder_history(
        sess, 'tok',
        {'header': {}, 'payload': {'nonce': 'abc', 'sub': 'u'}},
        known_type='Access',
    )
    assert sess['decoder_history'][0]['token_type'] == 'Access'


def test_history_label_uses_preferred_username_and_realm():
    sess: dict = {}
    _update_decoder_history(sess, 'tok', {
        'header': {},
        'payload': {'preferred_username': 'alice', 'iss': 'http://idp/realms/test'},
    })
    assert sess['decoder_history'][0]['label'] == 'alice — test'
