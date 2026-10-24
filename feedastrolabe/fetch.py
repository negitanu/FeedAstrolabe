"""Bounded HTTP fetching with public-address validation and DNS pinning."""
import http.client
import ipaddress
import socket
import ssl
import time
from urllib.parse import urlsplit, urlunsplit, urljoin, quote

MAX_BYTES = 5 * 1024 * 1024


def normalize_url(url):
    if not isinstance(url, str) or len(url) > 2048 or any(ord(c) < 33 for c in url):
        raise ValueError('URL が不正です。')
    p = urlsplit(url)
    if p.scheme not in ('http', 'https') or not p.hostname or p.username or p.password:
        raise ValueError('認証情報を含まない http/https URL を入力してください。')
    if p.port not in (None, 80 if p.scheme == 'http' else 443):
        raise ValueError('利用できるポートは HTTP 80 / HTTPS 443 です。')
    host = p.hostname.encode('idna').decode('ascii').lower()
    if ':' in host:
        host = '[' + host + ']'
    return urlunsplit((p.scheme, host, quote(p.path or '/', safe="/%:@!$&'()*+,;=-._~"), quote(p.query, safe="=&%/:?@!$'()*+,;~-._"), ''))


def safe_link(url, base=''):
    try:
        return normalize_url(urljoin(base, url)) if url else ''
    except (ValueError, UnicodeError):
        return ''


def public_address(host, port):
    results = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    if not results:
        raise ValueError('ホスト名を解決できません。')
    for _, _, _, _, address in results:
        ip = ipaddress.ip_address(address[0])
        mapped = getattr(ip, 'ipv4_mapped', None)
        if not ip.is_global or (mapped is not None and not mapped.is_global):
            raise ValueError('ローカル・プライベートアドレスは取得できません。')
    return results[0]


class PinnedHTTP(http.client.HTTPConnection):
    def __init__(self, host, port, address, secure, timeout):
        super().__init__(host, port, timeout=timeout)
        self.address = address
        self.secure = secure

    def connect(self):
        family, socktype, proto, _, sockaddr = self.address
        sock = socket.socket(family, socktype, proto)
        try:
            sock.settimeout(self.timeout)
            sock.connect(sockaddr)
            if self.secure:
                sock = ssl.create_default_context().wrap_socket(sock, server_hostname=self.host)
            self.sock = sock
        except BaseException:
            sock.close()
            raise


def fetch(url, etag=None, modified=None, *, accept='application/atom+xml,application/rss+xml,application/xml,text/xml'):
    url = normalize_url(url)
    deadline = time.monotonic() + 30
    for hop in range(6):
        if time.monotonic() >= deadline:
            raise ValueError('取得時間の上限を超えました。')
        p = urlsplit(url)
        port = 443 if p.scheme == 'https' else 80
        address = public_address(p.hostname, port)
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ValueError('取得時間の上限を超えました。')
        conn = PinnedHTTP(p.hostname, port, address, p.scheme == 'https', min(10, remaining))
        headers = {'User-Agent': 'FeedAstrolabe/0.1', 'Accept': accept, 'Accept-Encoding': 'identity'}
        if etag:
            headers['If-None-Match'] = etag
        if modified:
            headers['If-Modified-Since'] = modified
        try:
            conn.request('GET', urlunsplit(('', '', p.path or '/', p.query, '')), headers=headers)
            response = conn.getresponse()
            if response.status in (301, 302, 303, 307, 308):
                location = response.getheader('Location')
                if hop == 5 or not location:
                    raise ValueError('リダイレクトが多すぎるか不正です。')
                url = normalize_url(urljoin(url, location))
                etag = modified = None
                continue
            metadata = {'etag': response.getheader('ETag'), 'modified': response.getheader('Last-Modified'), 'url': url}
            if response.status == 304:
                return None, metadata
            if response.status != 200:
                raise ValueError(f'取得先が HTTP {response.status} を返しました。')
            encoding = response.getheader('Content-Encoding', 'identity').lower()
            if encoding not in ('', 'identity'):
                raise ValueError('圧縮されていないフィード応答が必要です。')
            length = response.getheader('Content-Length')
            if length and int(length) > MAX_BYTES:
                raise ValueError('フィードが 5 MiB の上限を超えています。')
            body = bytearray()
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise ValueError('取得時間の上限を超えました。')
                if conn.sock:
                    conn.sock.settimeout(min(10, remaining))
                chunk = response.read1(min(65536, MAX_BYTES + 1 - len(body)))
                if not chunk:
                    break
                body.extend(chunk)
                if len(body) > MAX_BYTES:
                    raise ValueError('フィードが 5 MiB の上限を超えています。')
            return bytes(body), metadata
        finally:
            conn.close()
    raise ValueError('取得できませんでした。')
