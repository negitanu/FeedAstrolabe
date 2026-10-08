import os
import re
import jwt
from flask import abort, current_app, request


def configure_access(app):
    mode = app.config.get('ACCESS_MODE', os.environ.get('FEEDASTROLABE_ACCESS_MODE', 'local'))
    if mode not in ('local', 'cloudflare'):
        raise ValueError('FEEDASTROLABE_ACCESS_MODE must be local or cloudflare')
    app.config['ACCESS_MODE'] = mode
    if mode == 'local':
        return
    issuer = app.config.get('ACCESS_TEAM_DOMAIN', os.environ.get('CF_ACCESS_TEAM_DOMAIN', '')).rstrip('/')
    audience = app.config.get('ACCESS_AUD', os.environ.get('CF_ACCESS_AUD', ''))
    hosts = app.config.get('PUBLIC_HOSTS', os.environ.get('FEEDASTROLABE_PUBLIC_HOSTS', ''))
    if not re.fullmatch(r'https://[a-zA-Z0-9-]+\.cloudflareaccess\.com', issuer) or not audience or not hosts:
        raise ValueError('Cloudflare mode requires team HTTPS domain, AUD and public hosts')
    host_list = hosts.split(',') if isinstance(hosts, str) else hosts
    if any(not re.fullmatch(r'[a-zA-Z0-9](?:[a-zA-Z0-9.-]*[a-zA-Z0-9])?', h.strip()) or '..' in h.strip() for h in host_list):
        raise ValueError('Public hosts must be explicit DNS names')
    app.config.update(SESSION_COOKIE_SECURE=True, TRUSTED_HOSTS=['localhost', '127.0.0.1', '[::1]'] + [h.strip() for h in host_list])
    app.config.update(ACCESS_TEAM_DOMAIN=issuer, ACCESS_AUD=audience)
    app.extensions['access_jwks'] = jwt.PyJWKClient(issuer + '/cdn-cgi/access/certs', cache_jwk_set=True, lifespan=300, timeout=5)


def verify_access():
    if current_app.config['ACCESS_MODE'] != 'cloudflare' or request.path == '/healthz':
        return
    token = request.headers.get('Cf-Access-Jwt-Assertion', '')
    if not token or len(token) > 16384:
        abort(403, description='Cloudflare Access 認証が必要です。')
    try:
        key = current_app.extensions['access_jwks'].get_signing_key_from_jwt(token)
        jwt.decode(token, key.key, algorithms=['RS256'],
                   issuer=current_app.config['ACCESS_TEAM_DOMAIN'], audience=current_app.config['ACCESS_AUD'],
                   options={'require': ['exp', 'iat', 'iss', 'aud']})
    except Exception:
        # Never put a JWT, key or sensitive claims into a log or error response.
        abort(403, description='Cloudflare Access 認証を確認できませんでした。')
