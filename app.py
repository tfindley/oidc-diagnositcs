import base64
import json
import os
import secrets
import time
import yaml
from collections import Counter
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode, urlparse

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

# ── Session cookie security ───────────────────────────────────────────────────
# HttpOnly: blocks JavaScript from reading the session cookie (XSS protection).
# SameSite=Lax: blocks the cookie being sent on cross-site POST requests (CSRF).
# Secure: only send the cookie over HTTPS — enabled automatically when
#   PREFERRED_URL_SCHEME=https is set, or can be forced with SESSION_COOKIE_SECURE=true.
_force_secure = (
    os.environ.get('PREFERRED_URL_SCHEME', '').lower() == 'https'
    or os.environ.get('SESSION_COOKIE_SECURE', 'false').lower() == 'true'
)
app.config.update(
    SESSION_COOKIE_HTTPONLY  = True,
    SESSION_COOKIE_SAMESITE  = 'Lax',
    SESSION_COOKIE_SECURE    = _force_secure,
    # Sessions are non-permanent (expire on browser close) unless PERMANENT_SESSION_LIFETIME
    # is set AND session.permanent is set to True in a route — neither happens in this app,
    # so all sessions die when the browser tab/window is closed.
    PERMANENT_SESSION_LIFETIME = timedelta(
        minutes=int(os.environ.get('SESSION_LIFETIME_MINUTES', '120'))
    ),
)

# ── OIDC config (single-provider env var fallback) ────────────────────────────
OIDC_DISCOVERY_URL     = os.environ.get('OIDC_DISCOVERY_URL', '')
OIDC_CLIENT_ID         = os.environ.get('OIDC_CLIENT_ID', '')
OIDC_CLIENT_SECRET     = os.environ.get('OIDC_CLIENT_SECRET', '')
OIDC_SCOPE             = os.environ.get('OIDC_SCOPE', 'openid email profile')
OIDC_PKCE_METHOD       = os.environ.get('OIDC_PKCE_METHOD', 'S256').strip()
OIDC_TOKEN_SIGNING_ALG = os.environ.get('OIDC_TOKEN_SIGNING_ALG', '').strip()

# ── UI config ─────────────────────────────────────────────────────────────────
SHOW_CONFIG     = os.environ.get('SHOW_CONFIG', 'false').lower() == 'true'
# Show a prominent privacy/data-handling notice on the landing page.
# Recommended for any public or shared deployment.
PRIVACY_NOTICE  = os.environ.get('PRIVACY_NOTICE', 'false').lower() == 'true'
# Optional custom message shown on the landing page before the login button.
# BANNER_TYPE controls the style: info (default), warning, error, success.
BANNER_TEXT     = os.environ.get('BANNER_TEXT', '').strip()
BANNER_TYPE     = os.environ.get('BANNER_TYPE', 'info').strip().lower()
if BANNER_TYPE not in {'info', 'warning', 'error', 'success'}:
    BANNER_TYPE = 'info'
GITHUB_URL      = 'https://github.com/tfindley/oidc-diagnositcs'
KOFI_URL        = 'https://ko-fi.com/tfindley'

# ── Multi-provider configuration ──────────────────────────────────────────────
# If providers.yml is present it overrides the single-provider env var config.
# Each entry must have: name, id, discovery_url, client_id, client_secret.
# Optional per-provider: scope, pkce_method, token_signing_alg.
MULTI_PROVIDER: bool = False
PROVIDERS: list = []

_providers_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'providers.yml')
if os.path.exists(_providers_file):
    try:
        with open(_providers_file) as _f:
            _yml = yaml.safe_load(_f)
        if _yml and _yml.get('providers'):
            PROVIDERS = _yml['providers']
            MULTI_PROVIDER = True
            print(f"Loaded {len(PROVIDERS)} provider(s) from providers.yml")
    except Exception as _exc:
        print(f"WARNING: Failed to load providers.yml: {_exc}")

if not MULTI_PROVIDER and OIDC_DISCOVERY_URL and OIDC_CLIENT_ID:
    PROVIDERS = [{
        'name':              'Sign in via SSO',
        'id':                'oidc',
        'discovery_url':     OIDC_DISCOVERY_URL,
        'client_id':         OIDC_CLIENT_ID,
        'client_secret':     OIDC_CLIENT_SECRET,
        'scope':             OIDC_SCOPE,
        'pkce_method':       OIDC_PKCE_METHOD,
        'token_signing_alg': OIDC_TOKEN_SIGNING_ALG,
    }]

# ── Claims metadata ───────────────────────────────────────────────────────────
TIMESTAMP_CLAIMS = frozenset({'exp', 'iat', 'nbf', 'auth_time', 'updated_at'})
SENSITIVE_CLAIMS = frozenset({
    'sub', 'email', 'name', 'given_name', 'family_name',
    'preferred_username', 'phone_number', 'address', 'picture',
    'profile', 'jti', 'sid', 'session_state',
})

# Maps each claim name to the OIDC scope that introduces it.
CLAIM_SCOPES: dict = {
    # openid (core JWT infrastructure claims)
    'sub': 'openid', 'iss': 'openid', 'aud': 'openid', 'exp': 'openid',
    'iat': 'openid', 'nbf': 'openid', 'jti': 'openid', 'nonce': 'openid',
    'at_hash': 'openid', 'c_hash': 'openid', 'acr': 'openid', 'amr': 'openid',
    'azp': 'openid', 'auth_time': 'openid', 'sid': 'openid',
    'session_state': 'openid', 'typ': 'openid', 'scope': 'openid', 'client_id': 'openid',
    # email scope
    'email': 'email', 'email_verified': 'email',
    # profile scope
    'name': 'profile', 'given_name': 'profile', 'family_name': 'profile',
    'middle_name': 'profile', 'nickname': 'profile', 'preferred_username': 'profile',
    'profile': 'profile', 'picture': 'profile', 'website': 'profile',
    'locale': 'profile', 'zoneinfo': 'profile', 'updated_at': 'profile',
    # phone scope
    'phone_number': 'phone', 'phone_number_verified': 'phone',
    # address scope
    'address': 'address',
    # groups / roles (provider-specific scopes with well-known names)
    'groups': 'groups',
    'roles': 'roles', 'realm_access': 'roles', 'resource_access': 'roles',
    # Azure AD-specific claims (no standard OIDC scope; labelled for clarity)
    'wids': 'azure', 'oid': 'azure', 'tid': 'azure', 'upn': 'azure',
    'ver': 'azure', 'appid': 'azure', 'unique_name': 'azure',
    # Keycloak-specific
    'allowed-origins': 'keycloak',
}

# Scopes that have a known set of claims — used to detect empty grants.
_SCOPE_KNOWN_CLAIMS: dict = {
    'openid':  frozenset({'sub', 'iss', 'aud', 'exp', 'iat', 'nbf', 'jti',
                          'nonce', 'at_hash', 'c_hash', 'acr', 'amr', 'azp',
                          'auth_time', 'sid', 'session_state', 'typ', 'scope', 'client_id'}),
    'email':   frozenset({'email', 'email_verified'}),
    'profile': frozenset({'name', 'given_name', 'family_name', 'middle_name',
                          'nickname', 'preferred_username', 'profile', 'picture',
                          'website', 'locale', 'zoneinfo', 'updated_at'}),
    'phone':   frozenset({'phone_number', 'phone_number_verified'}),
    'address': frozenset({'address'}),
    'groups':  frozenset({'groups'}),
    'roles':   frozenset({'realm_access', 'resource_access', 'roles'}),
}

# Scopes worth surfacing as "available but not configured"
_INTERESTING_SCOPES = frozenset({
    'email', 'profile', 'phone', 'address', 'offline_access', 'groups', 'roles',
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

def _get_provider(provider_id: str, default=None):
    """Return the provider config dict matching provider_id, or default."""
    return next((p for p in PROVIDERS if p['id'] == provider_id), default)


# ── OAuth registration ────────────────────────────────────────────────────────
oauth = OAuth(app)
for _p in PROVIDERS:
    _pkce = _p.get('pkce_method', 'S256').strip()
    _kw   = {'scope': _p.get('scope', 'openid email profile')}
    if _pkce != 'disabled':
        _kw['code_challenge_method'] = _pkce
    oauth.register(
        name=_p['id'],
        server_metadata_url=_p['discovery_url'],
        client_id=_p['client_id'],
        client_secret=_p['client_secret'],
        client_kwargs=_kw,
    )


# ── Template context processor ────────────────────────────────────────────────
@app.context_processor
def inject_globals():
    """Make site-wide config available in all templates without explicit passing."""
    raw = session.get('raw_tokens') if session.get('user') else None
    return {
        'github_url':      GITHUB_URL,
        'kofi_url':        KOFI_URL,
        'show_config':     SHOW_CONFIG,
        'privacy_notice':  PRIVACY_NOTICE,
        'banner_text':     BANNER_TEXT,
        'banner_type':     BANNER_TYPE,
        'flask_debug':     app.debug,
        'nav_expires_at':  raw.get('expires_at') if raw else None,
        'nav_has_refresh': bool(raw.get('refresh_token')) if raw else False,
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
            'scope': CLAIM_SCOPES.get(key, ''),
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
    # In multi-provider mode, use the first provider's discovery URL for the
    # connectivity and discovery panels; config card is hidden (single-provider only).
    first = PROVIDERS[0] if PROVIDERS else {}
    return render_template('index.html',
        user=session.get('user'),
        providers=PROVIDERS,
        multi_provider=MULTI_PROVIDER,
        signed_in_provider=session.get('provider_id'),
        signed_in_user=session.get('user'),
        config={
            'discovery_url':    first.get('discovery_url', OIDC_DISCOVERY_URL),
            'client_id':        first.get('client_id', OIDC_CLIENT_ID),
            'scope':            first.get('scope', OIDC_SCOPE),
            'pkce_method':      first.get('pkce_method', OIDC_PKCE_METHOD),
            'token_signing_alg': (first.get('token_signing_alg') or OIDC_TOKEN_SIGNING_ALG or 'auto (from server)'),
            'configured':       bool(PROVIDERS),
        },
    )


@app.route('/login')
def login():
    """Single-provider mode: initiate OIDC login."""
    if not PROVIDERS:
        flash('OIDC provider not configured — set OIDC_DISCOVERY_URL and OIDC_CLIENT_ID in .env', 'error')
        return redirect(url_for('index'))
    if MULTI_PROVIDER:
        # Multi-provider mode: the index page shows per-provider buttons; /login is unused.
        return redirect(url_for('index'))
    try:
        # Clear any existing session before starting a new login flow.
        # Flask sessions are stored in a single signed cookie; JWT tokens stored from
        # a previous login can fill the cookie to the 4 KB browser limit, preventing
        # the OAuth state from being stored and causing CSRF mismatches on the callback.
        session.clear()
        session['login_start'] = time.time()
        session['provider_id'] = PROVIDERS[0]['id']
        return oauth.create_client(PROVIDERS[0]['id']).authorize_redirect(
            url_for('auth_callback', _external=True)
        )
    except Exception as exc:
        flash(f'Could not reach the OIDC provider: {exc}', 'error')
        return redirect(url_for('index'))


@app.route('/login/<provider_id>')
def login_provider(provider_id):
    """Multi-provider mode: initiate OIDC login for a specific provider."""
    provider = _get_provider(provider_id)
    if not provider:
        flash(f'Unknown provider: {provider_id}', 'error')
        return redirect(url_for('index'))
    try:
        # Clear any existing session before starting a new login flow.
        # Flask sessions are stored in a single signed cookie; JWT tokens from a
        # previous login can fill the cookie to the 4 KB browser limit, preventing
        # the OAuth state from being stored and causing CSRF mismatches on the callback.
        session.clear()
        session['login_start'] = time.time()
        session['provider_id'] = provider_id
        return oauth.create_client(provider_id).authorize_redirect(
            url_for('auth_callback_provider', provider_id=provider_id, _external=True)
        )
    except Exception as exc:
        flash(f'Could not reach provider "{provider["name"]}": {exc}', 'error')
        return redirect(url_for('index'))


def _handle_callback(provider_id: str):
    """Shared login callback logic for both single- and multi-provider routes."""
    provider = _get_provider(provider_id)
    if not provider:
        flash(f'Unknown provider: {provider_id}', 'error')
        return redirect(url_for('index'))

    alg = provider.get('token_signing_alg', '').strip()
    claims_options = {'alg': {'values': [alg]}} if alg else {}
    try:
        token = oauth.create_client(provider_id).authorize_access_token(
            **({"claims_options": claims_options} if claims_options else {})
        )
    except Exception as exc:
        flash(f'Authentication failed: {exc}', 'error')
        return redirect(url_for('index'))

    login_duration = None
    if 'login_start' in session:
        login_duration = round(time.time() - session.pop('login_start'), 2)

    # Store scope info for analysis on the claims page.
    # load_server_metadata() uses Authlib's cached metadata — no extra HTTP request.
    # Store only the filtered unconfigured list rather than the full scopes_supported
    # to keep session cookie size small.
    configured_scope = provider.get('scope', 'openid email profile')
    session['configured_scope'] = configured_scope
    configured_scope_set = set(configured_scope.split())
    try:
        meta = oauth.create_client(provider_id).load_server_metadata()
        scopes_supported = meta.get('scopes_supported') or []
        session['unconfigured_scopes'] = sorted(
            s for s in scopes_supported
            if s not in configured_scope_set and s in _INTERESTING_SCOPES
        )
    except Exception:
        session['unconfigured_scopes'] = []

    session['provider_id'] = provider_id
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


@app.route('/callback')
def auth_callback():
    """Single-provider callback."""
    provider_id = session.get('provider_id', PROVIDERS[0]['id'] if PROVIDERS else 'oidc')
    return _handle_callback(provider_id)


@app.route('/callback/<provider_id>')
def auth_callback_provider(provider_id):
    """Multi-provider callback."""
    return _handle_callback(provider_id)


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
                'expires_at_str':    exp_dt.strftime('%Y-%m-%d %H:%M:%S UTC'),
                'seconds_remaining': max(0, remaining),
                'expired':           remaining < 0,
            }
        except Exception:
            pass

    has_refresh_token = bool(raw_tokens.get('refresh_token'))

    # Scope analysis: use the scope string the server echoed back, fall back to configured.
    # offline_access intentionally yields no claims (it's a refresh token grant, not a claims scope).
    granted_scope_str = raw_tokens.get('scope', '') or session.get('configured_scope', '')
    all_claim_keys = set(id_payload) | set(access_payload) | set(userinfo)
    scope_analysis = []
    for scope in sorted(set(granted_scope_str.split())):
        known = _SCOPE_KNOWN_CLAIMS.get(scope, frozenset())
        found = len(known & all_claim_keys) if known else 0
        scope_analysis.append({
            'scope': scope,
            'found': found,
            'empty': bool(known) and found == 0,
        })

    unconfigured_scopes = session.get('unconfigured_scopes', [])

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
        scope_analysis=scope_analysis,
        unconfigured_scopes=unconfigured_scopes,
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

    provider_id = session.get('provider_id', PROVIDERS[0]['id'] if PROVIDERS else 'oidc')
    try:
        token = oauth.create_client(provider_id).fetch_access_token(
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
        now=int(time.time()),
    )


@app.route('/logout')
def logout():
    """Clear the local session. If the provider supports RP-initiated logout
    (end_session_endpoint in discovery metadata), redirect there first."""
    id_token    = session.get('raw_tokens', {}).get('id_token')
    provider_id = session.get('provider_id', PROVIDERS[0]['id'] if PROVIDERS else 'oidc')
    session.clear()

    if id_token:
        try:
            meta = oauth.create_client(provider_id).load_server_metadata()
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


# ── Conformance checks ────────────────────────────────────────────────────────

def _is_localhost(url: str) -> bool:
    h = (urlparse(url).hostname or '').lower()
    return h in ('localhost', '127.0.0.1', '::1') or h.endswith('.local')


def run_conformance_checks(provider_id: str) -> dict:
    """Run OIDC conformance and security checks for a provider.
    Returns a dict with keys: provider, checks, counts, latency_ms, error (optional)."""
    provider = _get_provider(provider_id)
    if not provider:
        return {'error': 'Provider not found', 'checks': [], 'counts': {}}
    discovery_url = provider.get('discovery_url', '')
    if not discovery_url:
        return {'error': 'No discovery URL configured', 'checks': [], 'counts': {}}

    try:
        t0 = time.time()
        resp = http_requests.get(discovery_url, timeout=10)
        resp.raise_for_status()
        meta = resp.json()
        latency_ms = int((time.time() - t0) * 1000)
    except Exception as exc:
        return {'error': f'Could not fetch discovery document: {exc}', 'checks': [], 'counts': {}}

    checks = []

    def add(category, name, status, detail, ref=''):
        checks.append({'category': category, 'name': name, 'status': status,
                       'detail': detail, 'ref': ref})

    # ── Discovery document required/recommended fields (OIDC Core 1.0 §4) ──────
    CAT = 'Discovery Document'
    for field, label, required in [
        ('issuer',                                'Issuer',                               True),
        ('authorization_endpoint',                'Authorization endpoint',                True),
        ('token_endpoint',                        'Token endpoint',                        True),
        ('jwks_uri',                              'JWKS URI',                              True),
        ('response_types_supported',              'Response types supported',              True),
        ('subject_types_supported',               'Subject types supported',               True),
        ('id_token_signing_alg_values_supported', 'ID token signing algorithms',           True),
        ('userinfo_endpoint',                     'UserInfo endpoint',                     False),
        ('scopes_supported',                      'Scopes supported',                      False),
        ('claims_supported',                      'Claims supported',                      False),
        ('token_endpoint_auth_methods_supported', 'Token endpoint auth methods supported', False),
    ]:
        level = 'REQUIRED' if required else 'RECOMMENDED'
        ref   = f'OIDC Core 1.0 §4 ({level})'
        if meta.get(field):
            add(CAT, f'{label} present', 'pass',
                f'`{field}` is present in the discovery document.', ref)
        else:
            add(CAT, f'{label} present', 'fail' if required else 'warn',
                f'`{field}` is {level} by OIDC Core but is missing.', ref)

    # ── Security: HTTPS endpoints ──────────────────────────────────────────────
    CAT = 'Security'
    for field, label, critical in [
        ('issuer',                 'Issuer',                True),
        ('authorization_endpoint', 'Authorization endpoint', True),
        ('token_endpoint',         'Token endpoint',         True),
        ('jwks_uri',               'JWKS URI',               True),
        ('userinfo_endpoint',      'UserInfo endpoint',      False),
        ('end_session_endpoint',   'End session endpoint',   False),
    ]:
        url = meta.get(field, '')
        if not url:
            continue
        if url.startswith('https://'):
            add(CAT, f'{label} uses HTTPS', 'pass',
                f'{label} is served over HTTPS.', 'RFC 6749 §10.9')
        elif _is_localhost(url):
            add(CAT, f'{label} uses HTTPS', 'info',
                f'{label} is on localhost — HTTP is acceptable for local development only.',
                'RFC 6749 §10.9')
        else:
            add(CAT, f'{label} uses HTTPS', 'fail' if critical else 'warn',
                f'{label} is not HTTPS (`{url}`). Tokens could be intercepted in transit.',
                'RFC 6749 §10.9')

    # ── Security: ID token signing algorithms ──────────────────────────────────
    algs = meta.get('id_token_signing_alg_values_supported', [])
    if 'none' in algs:
        add(CAT, 'Unsigned tokens (`none`) not advertised', 'fail',
            'The `none` algorithm is listed in `id_token_signing_alg_values_supported`. '
            'This permits completely unsigned tokens — a critical security risk.',
            'RFC 8725 §2.1')
    elif algs:
        add(CAT, 'Unsigned tokens (`none`) not advertised', 'pass',
            'The `none` algorithm is not advertised — unsigned tokens will be rejected.',
            'RFC 8725 §2.1')

    hmac_algs = [a for a in algs if a.startswith('HS')]
    if hmac_algs:
        add(CAT, 'No symmetric HMAC algorithms for ID tokens', 'warn',
            f'Symmetric HMAC algorithms ({", ".join(hmac_algs)}) are listed. '
            'These require the client secret to be shared for token verification and '
            'are inappropriate for most deployments.',
            'RFC 8725 §2.7')
    elif algs:
        add(CAT, 'No symmetric HMAC algorithms for ID tokens', 'pass',
            'No symmetric HMAC algorithms advertised for ID token signing.',
            'RFC 8725 §2.7')

    ec_algs = [a for a in algs if a.startswith('ES')]
    ps_algs = [a for a in algs if a.startswith('PS')]
    rs_algs = [a for a in algs if a.startswith('RS')]
    if ec_algs or ps_algs:
        preferred = ec_algs + ps_algs
        add(CAT, 'Modern asymmetric algorithm available', 'pass',
            f'EC or RSA-PSS algorithms supported: {", ".join(preferred)}. '
            'These are preferred over RSA PKCS#1 v1.5 (RS256).',
            'RFC 8725 §3.2')
    elif rs_algs:
        add(CAT, 'Modern asymmetric algorithm available', 'warn',
            f'Only RSA PKCS#1 v1.5 ({", ".join(rs_algs)}) is available. '
            'Consider enabling ES256 or PS256.',
            'RFC 8725 §3.2')
    elif algs:
        add(CAT, 'Modern asymmetric algorithm available', 'fail',
            f'Unrecognised algorithms only: {", ".join(algs)}.', 'RFC 8725 §3.2')

    # ── Security: PKCE ─────────────────────────────────────────────────────────
    pkce = meta.get('code_challenge_methods_supported', [])
    if 'S256' in pkce:
        add(CAT, 'PKCE S256 supported', 'pass',
            'S256 PKCE is supported — authorization codes are protected against interception.',
            'RFC 7636, RFC 9700 §7.5.2')
    elif pkce:
        add(CAT, 'PKCE S256 supported', 'warn',
            f'PKCE supported but only with: {", ".join(pkce)}. S256 is required; plain is insecure.',
            'RFC 7636 §4.2')
    else:
        add(CAT, 'PKCE S256 supported', 'warn',
            'PKCE code challenge methods are not advertised. Public clients may be vulnerable '
            'to authorization code interception.',
            'RFC 7636, RFC 9700 §7.5.2')

    if pkce and 'plain' in pkce:
        add(CAT, '`plain` PKCE method not advertised', 'warn',
            'The `plain` code challenge method is advertised. This provides no hashing of the '
            'code verifier and offers less protection than S256.',
            'RFC 7636 §4.2')
    elif pkce:
        add(CAT, '`plain` PKCE method not advertised', 'pass',
            'The insecure `plain` PKCE method is not advertised.')

    # ── Optional features ──────────────────────────────────────────────────────
    CAT = 'Optional Features'
    for field, label, ok_detail, info_detail, ref in [
        ('end_session_endpoint', 'RP-initiated logout (end_session_endpoint)',
         'Users can be signed out at the IdP level when they sign out of this application.',
         'No `end_session_endpoint` — local session cleared on sign-out but the IdP session remains active.',
         'OIDC RP-Initiated Logout 1.0'),
        ('backchannel_logout_supported', 'Back-channel logout',
         'Server-to-server logout notifications are supported.',
         'Back-channel logout not advertised — users will not be automatically signed out if '
         'their IdP session ends externally.',
         'OIDC Back-Channel Logout 1.0'),
        ('claims_parameter_supported', 'Claims request parameter',
         'The `claims` parameter is supported — clients can request specific claims per-request.',
         'Not advertised — clients cannot fine-tune which claims are returned per-request.',
         'OIDC Core 1.0 §5.5'),
        ('request_parameter_supported', 'Signed request objects (JAR)',
         'Signed request objects are supported for tamper-proof authorization requests.',
         'Not advertised.',
         'RFC 9101'),
    ]:
        if meta.get(field):
            add(CAT, label, 'pass', ok_detail, ref)
        else:
            add(CAT, label, 'info', info_detail, ref)

    # ── Token validation (current session for this provider) ──────────────────
    CAT = 'Token Validation'
    if session.get('provider_id') != provider_id:
        add(CAT, 'Session available for validation', 'skip',
            'Not signed in to this provider — sign in to validate actual token claims.')
    else:
        raw_tokens = session.get('raw_tokens', {})
        tok = decode_jwt(raw_tokens.get('id_token', ''))

        if tok.get('error'):
            add(CAT, 'ID token decodable', 'warn', f'Could not decode ID token: {tok["error"]}')
        else:
            payload = tok.get('payload', {})
            header  = tok.get('header',  {})
            add(CAT, 'ID token decodable', 'pass',
                'ID token is a structurally valid JWT (header.payload.signature).')

            for claim in ('sub', 'iss', 'aud', 'exp', 'iat'):
                if claim in payload:
                    add(CAT, f'`{claim}` claim present', 'pass',
                        f'ID token contains the required `{claim}` claim.', 'OIDC Core §2')
                else:
                    add(CAT, f'`{claim}` claim present', 'fail',
                        f'Required `{claim}` claim is missing from the ID token.', 'OIDC Core §2')

            token_iss = payload.get('iss', '')
            expected_iss = meta.get('issuer', '')
            if token_iss and expected_iss:
                if token_iss == expected_iss:
                    add(CAT, 'Issuer matches discovery document', 'pass',
                        f'Token `iss` matches: `{token_iss}`.', 'OIDC Core §3.1.3.7')
                else:
                    add(CAT, 'Issuer matches discovery document', 'fail',
                        f'Token `iss` (`{token_iss}`) ≠ discovery issuer (`{expected_iss}`). '
                        'This token must be rejected.', 'OIDC Core §3.1.3.7')

            client_id = provider.get('client_id', '')
            aud = payload.get('aud')
            if aud is not None and client_id:
                aud_list = [aud] if isinstance(aud, str) else list(aud)
                if client_id in aud_list:
                    add(CAT, 'Audience contains client ID', 'pass',
                        'Token `aud` includes the configured client ID.',
                        'OIDC Core §3.1.3.7')
                else:
                    add(CAT, 'Audience contains client ID', 'fail',
                        f'Token `aud` (`{aud}`) does not contain client ID `{client_id}`. '
                        'This token was not issued for this application.',
                        'OIDC Core §3.1.3.7')

            now_ts = int(time.time())
            exp = payload.get('exp')
            if exp:
                if exp > now_ts:
                    add(CAT, 'Token not expired', 'pass',
                        f'Expires in {exp - now_ts}s '
                        f'({datetime.fromtimestamp(exp, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")}).',
                        'OIDC Core §2')
                else:
                    add(CAT, 'Token not expired', 'fail',
                        f'Expired {now_ts - exp}s ago '
                        f'({datetime.fromtimestamp(exp, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")}).',
                        'OIDC Core §2')

            token_alg = header.get('alg', '')
            if token_alg == 'none':
                add(CAT, 'ID token signing algorithm', 'fail',
                    'ID token header has `alg: none` — this token is unsigned.',
                    'RFC 8725 §2.1')
            elif token_alg.startswith('HS'):
                add(CAT, 'ID token signing algorithm', 'warn',
                    f'ID token is signed with symmetric HMAC ({token_alg}).',
                    'RFC 8725 §2.7')
            elif token_alg:
                add(CAT, 'ID token signing algorithm', 'pass',
                    f'ID token is signed with `{token_alg}`.')

    counts = dict(Counter(c['status'] for c in checks))

    return {'provider': provider, 'checks': checks, 'counts': counts, 'latency_ms': latency_ms}


@app.route('/conformance')
def conformance():
    """OIDC conformance and security analysis page."""
    provider_id = request.args.get('provider') or (PROVIDERS[0]['id'] if PROVIDERS else None)
    result = None
    if provider_id and 'run' in request.args:
        result = run_conformance_checks(provider_id)
    return render_template('conformance.html',
        providers=PROVIDERS,
        multi_provider=MULTI_PROVIDER,
        provider_id=provider_id,
        result=result,
    )


# ── API endpoints ─────────────────────────────────────────────────────────────

@app.route('/api/connectivity')
def api_connectivity():
    """Server-side check: can the app reach an OIDC discovery URL?
    Accepts optional ?url= to check a specific provider's URL (used in multi-provider mode).
    Falls back to OIDC_DISCOVERY_URL when ?url is not supplied."""
    url = request.args.get('url') or OIDC_DISCOVERY_URL
    if not url:
        return jsonify({'status': 'unconfigured', 'message': 'No discovery URL configured'})
    try:
        resp = http_requests.get(url, timeout=5)
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
    which algorithms/methods are currently configured in this app.
    Accepts optional ?url=, ?pkce=, ?alg= for per-provider use in multi-provider mode."""
    url  = request.args.get('url')  or OIDC_DISCOVERY_URL
    pkce = request.args.get('pkce') or OIDC_PKCE_METHOD
    alg  = request.args.get('alg')  or OIDC_TOKEN_SIGNING_ALG or None
    if not url:
        return jsonify({'error': 'No discovery URL configured'})
    try:
        resp = http_requests.get(url, timeout=5)
        resp.raise_for_status()
        data = resp.json()
        data['_app_config'] = {
            'pkce_method':       pkce,
            'token_signing_alg': alg,
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
