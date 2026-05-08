"""Pytest fixtures.

Sets the minimum env vars the app reads at import time before importing it,
so module-level OIDC config doesn't end up empty (which would render some
routes uninteresting to test).
"""
import os
import sys

os.environ.setdefault('SECRET_KEY', 'pytest-secret-key-do-not-use-anywhere-real')
os.environ.setdefault('OIDC_DISCOVERY_URL', 'http://test.invalid/.well-known/openid-configuration')
os.environ.setdefault('OIDC_CLIENT_ID', 'test-client-id')
os.environ.setdefault('OIDC_CLIENT_SECRET', 'test-client-secret')
os.environ.setdefault('SESSION_ENCRYPTION_PEPPER', 'pytest-pepper-' + 'x' * 40)

# Project root onto sys.path so `import app` works when pytest is invoked
# from the project root.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import app as app_module


@pytest.fixture
def app():
    app_module.app.config['TESTING'] = True
    return app_module.app


@pytest.fixture
def client(app):
    return app.test_client()
