"""Pinned, bounded HTTPS JSON. Provider error bodies are never surfaced."""
import json
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit, urlunsplit

from .fetch import normalize_url, public_address, PinnedHTTP, MAX_BYTES


class SocialError(ValueError):
    def __init__(self, message, retry_at=None):
        super().__init__(message)
        self.retry_at = retry_at


def retry_time(headers):
    current = time.time()
    candidates = [current + 900]
    value = headers.get('retry-after')
    if value:
        try:
            candidates.append(current + max(0, int(value)))
        except ValueError:
            try:
                candidates.append(parsedate_to_datetime(value).timestamp())
            except (TypeError, ValueError, OverflowError):
                pass
    value = headers.get('x-rate-limit-reset') or headers.get('x-ratelimit-reset')
    if value:
        try:
            candidates.append(float(value))
        except ValueError:
            try:
                candidates.append(parsedate_to_datetime(value).timestamp())
            except (TypeError, ValueError, OverflowError):
                pass
    future = min(current + 7 * 86400, max(candidates))
    return datetime.fromtimestamp(future, timezone.utc).strftime('%Y-%m-%d %H:%M:%S')


def request_json(url, token=None):
    conn = None
    try:
        url = normalize_url(url)
        parsed = urlsplit(url)
        if parsed.scheme != 'https' or (token and parsed.hostname != 'api.x.com'):
            raise SocialError('SNS の取得先・認証先が不正です。')
        deadline = time.monotonic() + 30
        address = public_address(parsed.hostname, 443)
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise SocialError('SNS 取得がタイムアウトしました。')
        conn = PinnedHTTP(parsed.hostname, 443, address, True, min(10, remaining))
        headers = {'User-Agent': 'FeedAstrolabe/0.3', 'Accept': 'application/json', 'Accept-Encoding': 'identity'}
        if token:
            headers['Authorization'] = 'Bearer ' + token
        conn.request('GET', urlunsplit(('', '', parsed.path or '/', parsed.query, '')), headers=headers)
        response = conn.getresponse()
        metadata = {k.lower(): v for k, v in response.getheaders()}
        if response.status == 429:
            raise SocialError('SNS API のレート上限に達しました。再試行予定まで待機します。', retry_time(metadata))
        if response.status in (401, 403):
            raise SocialError('SNS API の認証・アクセス権限を確認してください。')
        if 300 <= response.status < 400:
            raise SocialError('SNS API のリダイレクトは許可されていません。')
        if response.status != 200:
            raise SocialError(f'SNS API が HTTP {response.status} を返しました。')
        if metadata.get('content-encoding', 'identity').lower() not in ('', 'identity'):
            raise SocialError('SNS API の圧縮応答は処理できません。')
        if int(metadata.get('content-length', '0')) > MAX_BYTES:
            raise SocialError('SNS 応答が 5 MiB の上限を超えています。')
        body = bytearray()
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise SocialError('SNS 取得がタイムアウトしました。')
            if conn.sock:
                conn.sock.settimeout(min(10, remaining))
            chunk = response.read1(min(65536, MAX_BYTES + 1 - len(body)))
            if not chunk:
                break
            body.extend(chunk)
            if len(body) > MAX_BYTES:
                raise SocialError('SNS 応答が 5 MiB の上限を超えています。')
        return json.loads(body), metadata
    except SocialError:
        raise
    except Exception:
        # Do not interpolate URLs, tokens, upstream bodies or raw exceptions.
        raise SocialError('SNS API に接続できないか、応答形式が不正です。') from None
    finally:
        if conn:
            conn.close()
