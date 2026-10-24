"""Scoped transient OPML plans; no plan content in cookies, logs or the DB."""
import hashlib
import hmac

from flask import current_app, session
from itsdangerous import BadData, URLSafeTimedSerializer

from .opml import validate_entries

PLAN_MAX_AGE = 15 * 60
MAX_PLAN_BYTES = 512 * 1024
PLAN_ERROR = 'プレビューが無効か有効期限が切れています。OPML をアップロードし直してください。'


def serializer():
    return URLSafeTimedSerializer(current_app.secret_key, salt='feedastrolabe-opml-preview-v1',
                                  signer_kwargs={'digest_method': hashlib.sha256})


def session_binding():
    return hashlib.sha256(session['csrf'].encode()).hexdigest()


def sign_plan(entries):
    token = serializer().dumps({'version': 1, 'session': session_binding(), 'entries': validate_entries(entries)})
    if len(token) > MAX_PLAN_BYTES:
        raise ValueError('プレビューが大きすぎます。OPML を小さなファイルに分けてください。')
    return token


def load_plan(token):
    if not isinstance(token, str) or not token or len(token) > MAX_PLAN_BYTES or not token.isascii():
        raise ValueError(PLAN_ERROR)
    try:
        plan = serializer().loads(token, max_age=PLAN_MAX_AGE)
        if not isinstance(plan, dict) or set(plan) != {'version', 'session', 'entries'} or type(plan['version']) is not int or plan['version'] != 1:
            raise ValueError()
        binding = plan['session']
        if not isinstance(binding, str) or not hmac.compare_digest(binding.encode(), session_binding().encode()):
            raise ValueError()
        return validate_entries(plan['entries'])
    except (BadData, ValueError, TypeError, KeyError):
        raise ValueError(PLAN_ERROR) from None
