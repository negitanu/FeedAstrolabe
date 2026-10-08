"""Runs only in the per-job renderer child; Docker supplies no network/data mount."""
import base64
import io
import resource
import sys
from .page_protocol import ObservationError

MAX_ATTACHMENT=10*1024*1024
MAX_EXTRACTED=100000


def extract(job):
    # Applied only to extraction children, never to Chromium jobs or the server.
    resource.setrlimit(resource.RLIMIT_CPU,(15,15))
    if sys.platform == 'linux':
        resource.setrlimit(resource.RLIMIT_AS,(384*1024*1024,384*1024*1024))
    try:
        if set(job)!={'type','mime','body'} or job['type']!='extract' or job['mime'] not in ('text/plain','text/markdown','application/pdf') or not isinstance(job['body'],str) or len(job['body'])>14*1024*1024:
            raise ValueError()
        raw=base64.b64decode(job['body'],validate=True)
        if not raw or len(raw)>MAX_ATTACHMENT:
            raise ValueError()
        if job['mime']=='application/pdf':
            if not raw.startswith(b'%PDF-') or b'%%EOF' not in raw[-4096:]:
                raise ValueError()
            from pypdf import PdfReader
            reader=PdfReader(io.BytesIO(raw),strict=True)
            if reader.is_encrypted or len(reader.pages)>200:
                raise ValueError()
            parts=[];total=0
            for page in reader.pages:
                contents=page.get_contents()
                if contents is not None and len(contents.get_data())>4*1024*1024:
                    raise ValueError()
                part=page.extract_text() or ''
                total+=len(part)+1
                if total>MAX_EXTRACTED:
                    raise ValueError()
                parts.append(part)
            text='\n'.join(parts)
        else:
            if raw.startswith(b'%PDF-') or b'\x00' in raw:
                raise ValueError()
            text=raw.decode('utf-8-sig')
        if len(text)>MAX_EXTRACTED or any(ord(c)<32 and c not in '\n\r\t' for c in text):
            raise ValueError()
        return text
    except Exception:
        raise ObservationError('attachment') from None
