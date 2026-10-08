"""Registered endpoints only, TLS DNS pinning; no redirects/auth/cookies/proxy."""
import json,time
from urllib.parse import urlsplit,urlunsplit
from .fetch import public_address,PinnedHTTP
from .social_http import retry_time

class ConnectorError(ValueError):
    def __init__(self,code,retry_at=None):self.code=code;self.retry_at=retry_at;super().__init__(code)


def retrieve(url,max_bytes=5*1024*1024):
    conn=None
    try:
        p=urlsplit(url)
        if p.scheme!='https' or p.username or p.password or p.port not in (None,443):raise ConnectorError('endpoint-policy')
        deadline=time.monotonic()+30
        address=public_address(p.hostname,443)
        remaining=deadline-time.monotonic()
        if remaining<=0:raise ConnectorError('timeout')
        conn=PinnedHTTP(p.hostname,443,address,True,min(10,remaining))
        headers={'User-Agent':'FeedAstrolabe/0.12','Accept':'application/atom+xml' if p.hostname=='export.arxiv.org' else 'application/json','Accept-Encoding':'identity'}
        if p.hostname=='api.github.com':headers['Accept']='application/vnd.github+json';headers['X-GitHub-Api-Version']='2026-03-10'
        conn.request('GET',urlunsplit(('','',p.path or '/',p.query,'')),headers=headers)
        response=conn.getresponse();headers={k.lower():v for k,v in response.getheaders()}
        if response.status==429 or (response.status==403 and p.hostname=='api.github.com' and headers.get('x-ratelimit-remaining')=='0'):raise ConnectorError('rate-limited',retry_time(headers))
        if 300<=response.status<400:raise ConnectorError('redirect-rejected')
        if response.status!=200:raise ConnectorError('http-'+str(response.status))
        if headers.get('content-encoding','identity').lower() not in ('','identity'):raise ConnectorError('encoding-rejected')
        if int(headers.get('content-length','0'))>max_bytes:raise ConnectorError('response-size')
        raw=bytearray()
        while True:
            remaining=deadline-time.monotonic()
            if remaining<=0:raise ConnectorError('timeout')
            if conn.sock:conn.sock.settimeout(min(10,remaining))
            part=response.read1(min(65536,max_bytes+1-len(raw)))
            if not part:break
            raw.extend(part)
            if len(raw)>max_bytes:raise ConnectorError('response-size')
        if p.hostname=='export.arxiv.org':
            from .ai_research_adapters import atom
            return atom(bytes(raw)),bytes(raw)
        # JSON duplicate keys/non-finite numbers are rejected before accepting cache.
        def pairs(items):
            result={}
            for key,value in items:
                if key in result:raise ValueError()
                result[key]=value
            return result
        payload=json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda _:(_ for _ in ()).throw(ValueError()))
        return payload,bytes(raw)
    except ConnectorError:raise
    except Exception:raise ConnectorError('transport-or-format') from None
    finally:
        if conn:conn.close()
