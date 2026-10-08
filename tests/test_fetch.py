import socket
import pytest
from feedastrolabe import fetch as net

@pytest.mark.parametrize('url', ['file:///etc/passwd', 'ftp://example.com/a', 'https://user:pass@example.com/', 'https://example.com:8000/', 'http://example.com:443/', 'https://example.com/\r\nx', 'https://', 'https://example.com:abc/'])
def test_invalid_urls(url):
    with pytest.raises(ValueError):
        net.normalize_url(url)


def test_normalization():
    assert net.normalize_url('https://EXAMPLE.com:443/rss#x') == 'https://example.com/rss'
    assert net.normalize_url('https://example.com/日本語') == 'https://example.com/%E6%97%A5%E6%9C%AC%E8%AA%9E'
    assert net.safe_link('javascript:alert(1)') == ''

@pytest.mark.parametrize('ip', ['127.0.0.1', '10.0.0.1', '192.168.1.1', '169.254.169.254', '::1', '::ffff:127.0.0.1', '100.64.0.1'])
def test_private_addresses(ip, monkeypatch):
    monkeypatch.setattr(socket, 'getaddrinfo', lambda *a, **k: [(socket.AF_INET, socket.SOCK_STREAM, 6, '', (ip, 443))])
    with pytest.raises(ValueError, match='プライベート'):
        net.public_address('example.com', 443)


def test_mixed_dns_rejected(monkeypatch):
    monkeypatch.setattr(socket, 'getaddrinfo', lambda *a, **k: [(2, 1, 6, '', ('1.1.1.1', 443)), (2, 1, 6, '', ('127.0.0.1', 443))])
    with pytest.raises(ValueError):
        net.public_address('example.com', 443)


class Response:
    def __init__(self, status=200, headers=None, body=b'hello'):
        self.status, self.headers, self.body = status, headers or {}, body
    def getheader(self, key, default=None):
        return self.headers.get(key, default)
    def read1(self, amount):
        chunk, self.body = self.body[:amount], self.body[amount:]
        return chunk


def fake_connections(monkeypatch, responses):
    calls = []
    class Connection:
        sock = None
        def __init__(self, host, port, address, secure, timeout):
            calls.append({'host': host, 'address': address, 'secure': secure})
        def request(self, method, path, headers):
            calls[-1].update(path=path, headers=headers)
        def getresponse(self):
            return responses.pop(0)
        def close(self):
            calls[-1]['closed'] = True
    monkeypatch.setattr(net, 'PinnedHTTP', Connection)
    monkeypatch.setattr(socket, 'getaddrinfo', lambda *a, **k: [(2, 1, 6, '', ('1.1.1.1', 443))])
    return calls


def test_conditionals_and_304(monkeypatch):
    calls = fake_connections(monkeypatch, [Response(304)])
    body, meta = net.fetch('https://example.com/feed', 'v1', 'yesterday')
    assert body is None
    assert calls[0]['headers']['If-None-Match'] == 'v1'
    assert calls[0]['headers']['If-Modified-Since'] == 'yesterday'
    assert calls[0]['closed']


def test_redirect_revalidates(monkeypatch):
    calls = fake_connections(monkeypatch, [Response(302, {'Location': 'http://private.example/feed'})])
    def dns(host, *args, **kwargs):
        return [(2, 1, 6, '', ('127.0.0.1' if host == 'private.example' else '1.1.1.1', 80))]
    monkeypatch.setattr(socket, 'getaddrinfo', dns)
    with pytest.raises(ValueError, match='プライベート'):
        net.fetch('https://example.com/feed')
    assert len(calls) == 1 and calls[0]['closed']


def test_successful_redirect(monkeypatch):
    calls = fake_connections(monkeypatch, [Response(301, {'Location': '/new'}), Response(200, {'ETag': 'v2'}, b'feed')])
    body, meta = net.fetch('https://example.com/feed', 'v1')
    assert body == b'feed' and meta['url'] == 'https://example.com/new'
    assert calls[1]['path'] == '/new' and 'If-None-Match' not in calls[1]['headers']

@pytest.mark.parametrize('response,match', [(Response(500), 'HTTP 500'), (Response(200, {'Content-Length': str(net.MAX_BYTES + 1)}), '5 MiB'), (Response(200, body=b'x' * (net.MAX_BYTES + 1)), '5 MiB'), (Response(200, {'Content-Encoding': 'gzip'}), '圧縮')])
def test_fetch_limits(response, match, monkeypatch):
    calls = fake_connections(monkeypatch, [response])
    with pytest.raises(ValueError, match=match):
        net.fetch('https://example.com/feed')
    assert calls[0]['closed']


def test_redirect_limit(monkeypatch):
    calls = fake_connections(monkeypatch, [Response(302, {'Location': '/loop'}) for _ in range(6)])
    with pytest.raises(ValueError, match='リダイレクト'):
        net.fetch('https://example.com/feed')
    assert len(calls) == 6


def test_connection_pins_resolved_ip_and_tls_hostname(monkeypatch):
    seen = []
    class Socket:
        def settimeout(self, value):
            pass
        def connect(self, address):
            seen.append(address)
        def close(self):
            pass
    class Context:
        def wrap_socket(self, sock, server_hostname):
            seen.append(server_hostname)
            return sock
    monkeypatch.setattr(socket, 'socket', lambda *a: Socket())
    monkeypatch.setattr(net.ssl, 'create_default_context', lambda: Context())
    monkeypatch.setattr(socket, 'getaddrinfo', lambda *a, **k: pytest.fail('Must not resolve DNS again'))
    conn = net.PinnedHTTP('example.com', 443, (2, 1, 6, '', ('1.1.1.1', 443)), True, 10)
    conn.connect()
    assert seen == [('1.1.1.1', 443), 'example.com']


def test_total_timeout(monkeypatch):
    fake_connections(monkeypatch, [Response()])
    moments = iter([0, 31])
    monkeypatch.setattr(net.time, 'monotonic', lambda: next(moments))
    with pytest.raises(ValueError, match='取得時間'):
        net.fetch('https://example.com/feed')
