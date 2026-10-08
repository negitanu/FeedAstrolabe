"""Only the observer parent can access the network. Never forwards credentials."""
import base64
import os
import socket
import time
from urllib.parse import urlsplit, urlunsplit

from flask import current_app
from .fetch import normalize_url, public_address, PinnedHTTP, MAX_BYTES
from .page_protocol import ObservationError, MAX_TEXT, send_message, receive_message


def origin(url):
    value = urlsplit(normalize_url(url))
    return value.scheme, value.hostname, value.port or (443 if value.scheme == 'https' else 80)


class FetchBudget:
    def __init__(self, target):
        self.origin = origin(target)
        self.deadline = time.monotonic() + 30
        self.requests = 0
        self.total = 0

    def fetch(self, url, method='GET'):
        conn = None
        try:
            url = normalize_url(url)
            if method != 'GET' or origin(url) != self.origin:
                raise ObservationError('network')
            self.requests += 1
            if self.requests > 50 or self.total >= 20 * 1024 * 1024:
                raise ObservationError('network')
            parsed = urlsplit(url)
            address = public_address(parsed.hostname, self.origin[2])
            remaining = self.deadline - time.monotonic()
            if remaining <= 0:
                raise ObservationError('timeout')
            conn = PinnedHTTP(parsed.hostname, self.origin[2], address, parsed.scheme == 'https', min(5, remaining))
            conn.request('GET', urlunsplit(('', '', parsed.path or '/', parsed.query, '')),
                         headers={'User-Agent': 'FeedAstrolabe/0.4 PageObserver', 'Accept': '*/*', 'Accept-Encoding': 'identity'})
            response = conn.getresponse()
            # Do not forward redirects, cookies, authentication or provider bodies on error.
            if response.status != 200 or response.getheader('Content-Encoding', 'identity').lower() not in ('', 'identity'):
                raise ObservationError('network')
            length = response.getheader('Content-Length')
            if length and int(length) > MAX_BYTES:
                raise ObservationError('network')
            body = bytearray()
            while True:
                remaining = self.deadline - time.monotonic()
                if remaining <= 0:
                    raise ObservationError('timeout')
                if conn.sock:
                    conn.sock.settimeout(min(5, remaining))
                data = response.read1(min(65536, MAX_BYTES + 1 - len(body)))
                if not data:
                    break
                body.extend(data)
                self.total += len(data)
                if len(body) > MAX_BYTES or self.total > 20 * 1024 * 1024:
                    raise ObservationError('network')
            return {'type': 'response', 'body': base64.b64encode(body).decode('ascii'),
                    'content_type': response.getheader('Content-Type', 'application/octet-stream')}
        except ObservationError:
            raise
        except Exception:
            raise ObservationError('network') from None
        finally:
            if conn:
                conn.close()


def capture_page(feed):
    endpoint = current_app.config.get('RENDER_SOCKET') or os.environ.get('FEEDASTROLABE_RENDER_SOCKET', '/run/observer/renderer.sock')
    conn = socket.socket(socket.AF_UNIX)
    conn.settimeout(50)
    budget = FetchBudget(feed['target'])
    try:
        conn.connect(endpoint)
        with conn.makefile('rwb') as stream:
            send_message(stream, {'type': 'capture', 'url': feed['target'], 'selector': feed['selector'], 'settle_ms': feed['settle_ms']})
            while True:
                message = receive_message(stream)
                if message.get('type') == 'fetch':
                    if not isinstance(message.get('url'), str) or not isinstance(message.get('method'), str):
                        raise ObservationError('protocol')
                    try:
                        response = budget.fetch(message['url'], message['method'])
                    except ObservationError:
                        response = {'type': 'error', 'code': 'network'}
                    send_message(stream, response)
                elif message.get('type') == 'result':
                    text = message.get('text')
                    if not isinstance(text, str) or len(text) > MAX_TEXT:
                        raise ObservationError('protocol')
                    return text
                elif message.get('type') == 'error':
                    raise ObservationError(message.get('code'))
                else:
                    raise ObservationError('protocol')
    except ObservationError:
        raise
    except socket.timeout:
        raise ObservationError('timeout') from None
    except Exception:
        raise ObservationError('unavailable') from None
    finally:
        conn.close()
