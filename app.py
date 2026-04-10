import base64
import json
import os
import secrets
import time
from datetime import datetime, timezone
from urllib.parse import urlencode

import requests as http_requests
from authlib.integrations.flask_client import OAuth
from dotenv import load_dotenv
from flask import (Flask, flash, jsonify, redirect, render_template,
                   request, session, url_for)
from werkzeug.middleware.proxy_fix import ProxyFix

load_dotenv()

app = Flask(__name__)
# Trust X-Forwarded-Proto/Host from a single reverse proxy (e.g. Traefik)
# so url_for(_external=True) generates https:// when TLS is terminated upstream.
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

if os.environ.get('PREFERRED_URL_SCHEME'):
    app.config['PREFERRED_URL_SCHEME'] = os.environ['PREFERRED_URL_SCHEME']

_secret = os.environ.get('SECRET_KEY')
if not _secret:
    _secret = secrets.token_hex(32)
    print("WARNING: SECRET_KEY not set — sessions will be lost on restart. Set it in .env")
app.secret_key = _secret

# ── OIDC config ───────────────────────────────────────────────────────────────
OIDC_DISCOVERY_URL  = os.environ.get('OIDC_DISCOVERY_URL', '')
OIDC_CLIENT_ID      = os.environ.get('OIDC_CLIENT_ID', '')
OIDC_CLIENT_SECRET  = os.environ.get('OIDC_CLIENT_SECRET', '')
OIDC_SCOPE          = os.environ.get('OIDC_SCOPE', 'openid email profile')
OIDC_PKCE_METHOD    = os.environ.get('OIDC_PKCE_METHOD', 'S256').strip()
OIDC_TOKEN_SIGNING_ALG = os.environ.get('OIDC_TOKEN_SIGNING_ALG', '').strip()

# ── UI config ─────────────────────────────────────────────────────────────────
# SHOW_CONFIG=true reveals the full config card on the landing page.
# Defaults to false (hidden) — recommended for shared/internal deployments.
SHOW_CONFIG = os.environ.get('SHOW_CONFIG', 'false').lower() == 'true'
GITHUB_URL  = os.environ.get('GITHUB_URL', 'https://github.com/tfindley/sso_oidc_client_tool')
KOFI_URL    = os.environ.get('KOFI_URL', '')

# ── Claims metadata ───────────────────────────────────────────────────────────
TIMESTAMP_CLAIMS = frozenset({'exp', 'iat', 'nbf', 'auth_time', 'updated_at'})
SENSITIVE_CLAIMS = frozenset({
    'sub', 'email', 'name', 'given_name', 'family_name',
    'preferred_username', 'phone_number', 'address', 'picture',
    'profile', 'jti', 'sid', 'session_state',
})

CLAIM_DESCRIPTIONS = {
    'sub': 'Subject — Unique, stable identifier for this user at this issuer',
    'iss': 'Issuer — URL of the authorization server that issued the token',
    'aud': 'Audience — Intended recipient(s); must include the client_id',
    'exp': 'Expiration Time — Token is invalid after this Unix timestamp',
    'iat': 'Issued At — When this token was created (Unix timestamp)',
    'nbf': 'Not Before — Token must not be accepted before this Unix timestamp',
    'jti': 'JWT ID — Unique token identifier; used to prevent replay attacks',
    'email': 'Email Address',
    'email_verified': 'Email Verified — Whether the provider has verified this address',
    'name': 'Full Name',
    'given_name': 'Given / First Name',
    'family_name': 'Family / Last Name',
    'middle_name': 'Middle Name',
    'nickname': 'Nickname',
    'preferred_username': 'Preferred Username — The login name',
    'profile': 'Profile URL',
    'picture': 'Picture URL — Link to profile photo',
    'website': 'Website URL',
    'locale': 'Locale — Language/region preference (e.g. en-US)',
    'zoneinfo': 'Timezone — IANA timezone identifier (e.g. Europe/London)',
    'phone_number': 'Phone Number',
    'phone_number_verified': 'Phone Number Verified',
    'address': 'Postal Address',
    'updated_at': 'Updated At — When the user profile was last changed (Unix timestamp)',
    'nonce': 'Nonce — Replay-prevention value; must match what was sent in the auth request',
    'at_hash': 'Access Token Hash — Cryptographically binds the ID token to the access token',
    'c_hash': 'Code Hash — Binds the ID token to the authorization code',
    'acr': 'Authentication Context Class Reference — Assurance level (e.g. 0 = SSO cookie, 1 = password)',
    'amr': 'Authentication Methods References — How the user authenticated (e.g. pwd, otp, mfa)',
    'azp': 'Authorized Party — client_id this token was issued to',
    'auth_time': 'Authentication Time — When the user last authenticated interactively (Unix timestamp)',
    'sid': 'Session ID — SSO session identifier; used for backchannel logout',
    'session_state': 'Session State — Keycloak session state identifier',
    'typ': 'Token Type — Token format indicator (e.g. Bearer, ID, Refresh)',
    'realm_access': 'Realm Access — Keycloak: roles granted at the realm level',
    'resource_access': 'Resource Access — Keycloak: per-client role assignments',
    'scope': 'Scope — Space-separated OAuth 2.0 scopes granted',
    'allowed-origins': 'Allowed Origins — Keycloak: permitted CORS origins for this client',
    'client_id': 'Client ID — The OAuth 2.0 client that requested this token',
    'groups': 'Groups — Group memberships',
    'roles': 'Roles — Role assignments',
    'wids': 'Directory Role IDs — Azure AD directory role identifiers',
    'oid': 'Object ID — Azure AD immutable user identifier',
    'tid': 'Tenant ID — Azure AD tenant/directory identifier',
    'upn': 'User Principal Name — Azure AD user principal name',
    'ver': 'Version — Token schema version',
    'appid': 'Application ID — Azure AD client application identifier',
    'unique_name': 'Unique Name — Azure AD display name',
}

# ── OAuth registration ────────────────────────────────────────────────────────
oauth = OAuth(app)
if OIDC_DISCOVERY_URL and OIDC_CLIENT_ID:
    _client_kwargs = {'scope': OIDC_SCOPE}
    if OIDC_PKCE_METHOD != 'disabled':
        _client_kwargs['code_challenge_method'] = OIDC_PKCE_METHOD
    oauth.register(
        name='oidc',
        server_metadata_url=OIDC_DISCOVERY_URL,
        client_id=OIDC_CLIENT_ID,
        client_secret=OIDC_CLIENT_SECRET,
        client_kwargs=_client_kwargs,
    )


# ── Template context processor ────────────────────────────────────────────────
@app.context_processor
def inject_globals():
    """Make site-wide config available in all templates without explicit passing."""
    return {
        'github_url': GITHUB_URL,
        'kofi_url': KOFI_URL,
        'show_config': SHOW_CONFIG,
    }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _b64_decode(s: str) -> bytes:
    s += '=' * (-len(s) % 4)
    return base64.urlsafe_b64decode(s)


def decode_jwt(token: str) -> dict:
    """Decode a JWT without signature verification (display only)."""
    if not token:
        return {}
    parts = token.split('.')
    if len(parts) != 3:
        return {'error': 'Not a JWT (opaque token)', 'raw': token}
    try:
        header = json.loads(_b64_decode(parts[0]))
        payload = json.loads(_b64_decode(parts[1]))
        return {'header': header, 'payload': payload, 'raw': token, 'error': None}
    except Exception as exc:
        return {'error': str(exc), 'raw': token}


def prepare_claims(claims_dict: dict) -> list:
    """Convert a claims dict into a sorted list of typed display entries."""
    if not claims_dict:
        return []
    result = []
    for key, value in sorted(claims_dict.items()):
        entry = {
            'key': key,
            'value': value,
            'description': CLAIM_DESCRIPTIONS.get(key, ''),
            'is_sensitive': key in SENSITIVE_CLAIMS,
            'value_type': 'string',
            'formatted': None,
            'is_expired': False,
            'copy_value': '',
        }
        if isinstance(value, bool):
            entry['value_type'] = 'boolean'
            entry['copy_value'] = 'true' if value else 'false'
        elif isinstance(value, (int, float)):
            if key in TIMESTAMP_CLAIMS:
                entry['value_type'] = 'timestamp'
                try:
                    dt = datetime.fromtimestamp(value, tz=timezone.utc)
                    entry['formatted'] = dt.strftime('%Y-%m-%d %H:%M:%S UTC')
                    if key == 'exp':
                        entry['is_expired'] = datetime.now(tz=timezone.utc).timestamp() > value
                except (ValueError, OSError):
                    pass
            else:
                entry['value_type'] = 'number'
            entry['copy_value'] = str(value)
        elif isinstance(value, list):
            entry['value_type'] = 'array'
            entry['copy_value'] = ', '.join(str(v) for v in value)
        elif isinstance(value, dict):
            entry['value_type'] = 'object'
            entry['copy_value'] = json.dumps(value, indent=2)
        else:
            entry['copy_value'] = str(value)
        result.append(entry)
    return result


def build_compare_table(id_payload: dict, access_payload: dict, userinfo: dict) -> list:
    all_keys = sorted(set(list(id_payload) + list(access_payload) + list(userinfo)))
    rows = []
    for key in all_keys:
        id_val  = id_payload.get(key)
        acc_val = access_payload.get(key)
        ui_val  = userinfo.get(key)
        present_vals = [v for v in (id_val, acc_val, ui_val) if v is not None]
        mismatch = len(set(json.dumps(v, sort_keys=True, default=str) for v in present_vals)) > 1
        rows.append({
            'key': key,
            'description': CLAIM_DESCRIPTIONS.get(key, ''),
            'is_sensitive': key in SENSITIVE_CLAIMS,
            'in_id': key in id_payload,
            'in_access': key in access_payload,
            'in_userinfo': key in userinfo,
            'id_val': id_val,
            'access_val': acc_val,
            'userinfo_val': ui_val,
            'mismatch': mismatch,
        })
    return rows


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html',
        user=session.get('user'),
        config={
            'discovery_url': OIDC_DISCOVERY_URL,
            'client_id': OIDC_CLIENT_ID,
            'scope': OIDC_SCOPE,
            'pkce_method': OIDC_PKCE_METHOD,
            'token_signing_alg': OIDC_TOKEN_SIGNING_ALG or 'auto (from server)',
            'configured': bool(OIDC_DISCOVERY_URL and OIDC_CLIENT_ID),
        },
    )


@app.route('/login')
def login():
    if not (OIDC_DISCOVERY_URL and OIDC_CLIENT_ID):
        flash('OIDC provider not configured — set OIDC_DISCOVERY_URL and OIDC_CLIENT_ID in .env', 'error')
        return redirect(url_for('index'))
    try:
        session['login_start'] = time.time()
        return oauth.oidc.authorize_redirect(url_for('auth_callback', _external=True))
    except Exception as exc:
        flash(f'Could not reach the OIDC provider: {exc}', 'error')
        return redirect(url_for('index'))


@app.route('/callback')
def auth_callback():
    try:
        claims_options = {}
        if OIDC_TOKEN_SIGNING_ALG:
            claims_options['alg'] = {'values': [OIDC_TOKEN_SIGNING_ALG]}
        token = oauth.oidc.authorize_access_token(
            **({"claims_options": claims_options} if claims_options else {})
        )
    except Exception as exc:
        flash(f'Authentication failed: {exc}', 'error')
        return redirect(url_for('index'))

    login_duration = None
    if 'login_start' in session:
        login_duration = round(time.time() - session.pop('login_start'), 2)

    session['raw_tokens'] = {
        'access_token':  token.get('access_token'),
        'id_token':      token.get('id_token'),
        'refresh_token': token.get('refresh_token'),
        'token_type':    token.get('token_type', 'Bearer'),
        'expires_at':    token.get('expires_at'),
        'scope':         token.get('scope', ''),
    }
    session['login_duration'] = login_duration
    userinfo = token.get('userinfo') or {}
    session['userinfo'] = userinfo
    session['user'] = (
        userinfo.get('preferred_username')
        or userinfo.get('email')
        or userinfo.get('sub', 'authenticated')
    )
    return redirect(url_for('claims'))


@app.route('/claims')
def claims():
    if not session.get('user'):
        return redirect(url_for('index'))

    raw_tokens = session.get('raw_tokens', {})
    userinfo   = session.get('userinfo', {})

    id_data     = decode_jwt(raw_tokens.get('id_token', ''))
    access_data = decode_jwt(raw_tokens.get('access_token', ''))

    id_payload     = id_data.get('payload', {}) if not id_data.get('error') else {}
    access_payload = access_data.get('payload', {}) if not access_data.get('error') else {}

    expiry_info = None
    expires_at  = raw_tokens.get('expires_at')
    if expires_at:
        try:
            exp_dt    = datetime.fromtimestamp(expires_at, tz=timezone.utc)
            remaining = int((exp_dt - datetime.now(tz=timezone.utc)).total_seconds())
            expiry_info = {
                'expires_at_str':   exp_dt.strftime('%Y-%m-%d %H:%M:%S UTC'),
                'seconds_remaining': max(0, remaining),
                'expired':           remaining < 0,
            }
        except Exception:
            pass

    has_refresh_token = bool(raw_tokens.get('refresh_token'))

    return render_template('claims.html',
        username=session.get('user'),
        id_token_claims=prepare_claims(id_payload),
        access_token_claims=prepare_claims(access_payload),
        userinfo_claims=prepare_claims(userinfo),
        id_token_header=id_data.get('header', {}),
        access_token_header=access_data.get('header', {}),
        id_token_error=id_data.get('error'),
        access_token_error=access_data.get('error'),
        compare_rows=build_compare_table(id_payload, access_payload, userinfo),
        raw_tokens=raw_tokens,
        expiry_info=expiry_info,
        has_refresh_token=has_refresh_token,
        login_duration=session.get('login_duration'),
    )


@app.route('/claims.json')
def claims_json():
    if not session.get('user'):
        return jsonify({'error': 'not authenticated'}), 401
    raw_tokens  = session.get('raw_tokens', {})
    userinfo    = session.get('userinfo', {})
    id_data     = decode_jwt(raw_tokens.get('id_token', ''))
    access_data = decode_jwt(raw_tokens.get('access_token', ''))
    return jsonify({
        'id_token':     id_data.get('payload', {}),
        'access_token': access_data.get('payload', {}),
        'userinfo':     userinfo,
    })


@app.route('/refresh')
def token_refresh():
    if not session.get('user'):
        return redirect(url_for('index'))

    refresh_token = session.get('raw_tokens', {}).get('refresh_token')
    if not refresh_token:
        flash('No refresh token in session — your provider may not issue refresh tokens, '
              'or the offline_access scope was not requested.', 'warning')
        return redirect(url_for('claims'))

    try:
        token = oauth.oidc.fetch_access_token(
            grant_type='refresh_token',
            refresh_token=refresh_token,
        )
    except Exception as exc:
        flash(f'Token refresh failed: {exc}', 'error')
        return redirect(url_for('claims'))

    # Preserve the id_token and refresh_token if the server doesn't re-issue them
    old_tokens = session.get('raw_tokens', {})
    session['raw_tokens'] = {
        'access_token':  token.get('access_token'),
        'id_token':      token.get('id_token') or old_tokens.get('id_token'),
        'refresh_token': token.get('refresh_token') or refresh_token,
        'token_type':    token.get('token_type', 'Bearer'),
        'expires_at':    token.get('expires_at'),
        'scope':         token.get('scope', ''),
    }
    if token.get('userinfo'):
        session['userinfo'] = token['userinfo']

    flash('Token refreshed successfully.', 'success')
    return redirect(url_for('claims'))


@app.route('/decode', methods=['GET', 'POST'])
def decode_tool():
    decoded     = None
    claims_list = None
    token_input = request.form.get('token', '').strip()
    if token_input:
        decoded = decode_jwt(token_input)
        if decoded and not decoded.get('error'):
            claims_list = prepare_claims(decoded.get('payload', {}))
    return render_template('decode.html',
        token_input=token_input,
        decoded=decoded,
        claims_list=claims_list,
    )


@app.route('/logout')
def logout():
    """Clear the local session. If the provider supports RP-initiated logout
    (end_session_endpoint in discovery metadata), redirect there first."""
    id_token = session.get('raw_tokens', {}).get('id_token')
    session.clear()

    if id_token and OIDC_DISCOVERY_URL:
        try:
            meta = oauth.oidc.load_server_metadata()
            end_session_endpoint = meta.get('end_session_endpoint')
            if end_session_endpoint:
                params = {
                    'id_token_hint':            id_token,
                    'post_logout_redirect_uri': url_for('index', _external=True),
                }
                return redirect(f'{end_session_endpoint}?{urlencode(params)}')
        except Exception:
            pass  # Fall through to local-only logout

    return redirect(url_for('index'))


# ── API endpoints ─────────────────────────────────────────────────────────────

@app.route('/api/connectivity')
def api_connectivity():
    """Server-side check: can this app reach the OIDC discovery URL?"""
    if not OIDC_DISCOVERY_URL:
        return jsonify({'status': 'unconfigured', 'message': 'No OIDC_DISCOVERY_URL set'})
    try:
        resp = http_requests.get(OIDC_DISCOVERY_URL, timeout=5)
        resp.raise_for_status()
        data = resp.json()
        return jsonify({
            'status':     'ok',
            'issuer':     data.get('issuer', ''),
            'latency_ms': int(resp.elapsed.total_seconds() * 1000),
        })
    except http_requests.exceptions.ConnectionError as exc:
        return jsonify({'status': 'error', 'message': f'Connection refused or DNS failure: {exc}'})
    except http_requests.exceptions.Timeout:
        return jsonify({'status': 'error', 'message': 'Timed out after 5 seconds'})
    except Exception as exc:
        return jsonify({'status': 'error', 'message': str(exc)})


@app.route('/api/discovery')
def api_discovery():
    """Fetch and return the raw OIDC discovery document, augmented with
    which algorithms/methods are currently configured in this app."""
    if not OIDC_DISCOVERY_URL:
        return jsonify({'error': 'No OIDC_DISCOVERY_URL configured'})
    try:
        resp = http_requests.get(OIDC_DISCOVERY_URL, timeout=5)
        resp.raise_for_status()
        data = resp.json()
        data['_app_config'] = {
            'pkce_method':       OIDC_PKCE_METHOD,
            'token_signing_alg': OIDC_TOKEN_SIGNING_ALG or None,
            'scope':             OIDC_SCOPE,
            'latency_ms':        int(resp.elapsed.total_seconds() * 1000),
        }
        return jsonify(data)
    except Exception as exc:
        return jsonify({'error': str(exc)})


if __name__ == '__main__':
    app.run(
        host='0.0.0.0',
        port=int(os.environ.get('PORT', 5000)),
        debug=os.environ.get('FLASK_DEBUG', 'false').lower() == 'true',
    )
