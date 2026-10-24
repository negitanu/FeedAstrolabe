"""Origin behavior when Access enforcement is delegated to cloudflared."""
import pytest

from feedastrolabe import create_app
from feedastrolabe.keys import issue_key


@pytest.fixture
def tunnel_app(tmp_path, monkeypatch):
    monkeypatch.setenv('FEEDASTROLABE_ACCESS_MODE', 'tunnel')
    for key in ('CF_ACCESS_TEAM_DOMAIN', 'CF_ACCESS_AUD', 'FEEDASTROLABE_PUBLIC_HOSTS'):
        monkeypatch.setenv(key, '')
    return create_app({'TESTING': True, 'DATA_DIR': str(tmp_path)})


def test_tunnel_public_hostname_and_secure_cookie(tunnel_app):
    assert tunnel_app.config['ACCESS_MODE'] == 'tunnel'
    assert 'access_jwks' not in tunnel_app.extensions
    response = tunnel_app.test_client().get('/settings', base_url='https://reader.example.com')
    assert response.status_code == 200
    assert 'Secure' in response.headers['Set-Cookie']
    assert 'HttpOnly' in response.headers['Set-Cookie']
    assert tunnel_app.test_client().get('/healthz').status_code == 200


def test_tunnel_keeps_csrf(tunnel_app):
    client = tunnel_app.test_client()
    base_url = 'https://reader.example.com'
    assert client.post('/settings/keys', data={'name': 'no csrf'}, base_url=base_url).status_code == 400
    client.get('/settings', base_url=base_url)
    with client.session_transaction(base_url=base_url) as session:
        csrf = session['csrf']
    response = client.post('/settings/keys', base_url=base_url,
                           data={'csrf': csrf, 'name': 'valid csrf', 'scope': 'read', 'days': '30'})
    assert response.status_code == 200


def test_tunnel_keeps_api_key_scope_and_revocation(tunnel_app):
    client = tunnel_app.test_client()
    base_url = 'https://reader.example.com'
    assert client.get('/api/v1/feeds', base_url=base_url).status_code == 401
    with tunnel_app.app_context():
        key_id, token = issue_key('tunnel fixture', 'read', 30)
    headers = {'Authorization': 'Bearer '+token}
    assert client.get('/api/v1/feeds', headers=headers, base_url=base_url).status_code == 200
    assert client.post('/api/v1/feeds', json={}, headers=headers, base_url=base_url).status_code == 403
    from feedastrolabe.db import get_db
    with tunnel_app.app_context():
        db = get_db()
        with db:
            db.execute('UPDATE api_keys SET revoked_at=CURRENT_TIMESTAMP WHERE id=?', (key_id,))
    assert client.get('/api/v1/feeds', headers=headers, base_url=base_url).status_code == 401


@pytest.mark.parametrize('missing', ['CF_ACCESS_TEAM_DOMAIN', 'CF_ACCESS_AUD', 'FEEDASTROLABE_PUBLIC_HOSTS'])
def test_strict_mode_never_falls_back_with_incomplete_inputs(tmp_path, monkeypatch, missing):
    inputs = {'CF_ACCESS_TEAM_DOMAIN': 'https://fixture.cloudflareaccess.com',
              'CF_ACCESS_AUD': 'fixture-audience', 'FEEDASTROLABE_PUBLIC_HOSTS': 'reader.example.com'}
    monkeypatch.setenv('FEEDASTROLABE_ACCESS_MODE', 'cloudflare')
    for key, value in inputs.items():
        monkeypatch.setenv(key, '' if key == missing else value)
    with pytest.raises(ValueError, match='requires'):
        create_app({'TESTING': True, 'DATA_DIR': str(tmp_path)})


def test_native_default_still_rejects_public_host(tmp_path, monkeypatch):
    monkeypatch.delenv('FEEDASTROLABE_ACCESS_MODE', raising=False)
    app = create_app({'TESTING': True, 'DATA_DIR': str(tmp_path)})
    assert app.config['ACCESS_MODE'] == 'local'
    assert app.test_client().get('/', base_url='https://reader.example.com').status_code == 400
