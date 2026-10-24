"""Browser presentation preferences and narrowly scoped script nonces."""
import secrets
from flask import g, request

THEMES = ('system', 'light', 'dark')
THEME_COOKIE = 'feedastrolabe_theme'


def presentation_context():
    theme = request.cookies.get(THEME_COOKIE, 'system')
    return {'appearance': theme if theme in THEMES else 'system', 'context_nonce': script_nonce()}


def script_nonce():
    if not hasattr(g, 'sidebar_nonce'):
        g.sidebar_nonce = secrets.token_urlsafe(32)
    return g.sidebar_nonce
