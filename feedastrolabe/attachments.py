"""Bounded attachment transfer to the credential-free renderer."""
import base64
import os
import socket
from pathlib import Path
from flask import current_app
from .page_protocol import send_message,receive_message,ObservationError
from . import evidence as e,research as r


def upload(workspace_id,file):
    filename=file.filename or ''
    if not filename or len(filename)>200 or '/' in filename or '\\' in filename or any(ord(c)<32 for c in filename):
        raise ValueError('添付ファイル名が不正です。')
    types={'.txt':'text/plain','.md':'text/markdown','.pdf':'application/pdf'}
    mime=types.get(Path(filename).suffix.lower())
    if mime is None or file.mimetype!=mime:
        raise ValueError('添付は UTF-8 text/plain (.txt)、text/markdown (.md)、application/pdf (.pdf) に限定します。')
    raw=file.stream.read(e.MAX_FILE+1)
    if not raw or len(raw)>e.MAX_FILE:
        raise ValueError('添付は空でない10MiB以下のファイルを指定してください。')
    # Reject archived/nonexistent parent before sending even to the local parser.
    with e.storage_lock(),r.transaction() as db:
        r.editable(workspace_id,db)
        quota=db.execute('SELECT quota_bytes FROM evidence_settings').fetchone()[0]
        used=db.execute('SELECT coalesce(sum(size),0) FROM evidence_blobs').fetchone()[0]
        if not db.execute('SELECT 1 FROM evidence_blobs WHERE hash=?',(e.digest(raw),)).fetchone() and used+len(raw)>quota:
            raise ValueError('根拠ライブラリの容量上限に達しました。')
    endpoint=current_app.config.get('RENDER_SOCKET') or os.environ.get('FEEDASTROLABE_RENDER_SOCKET','/run/observer/renderer.sock')
    try:
        with socket.socket(socket.AF_UNIX) as connection:
            connection.settimeout(50);connection.connect(endpoint)
            with connection.makefile('rwb') as stream:
                send_message(stream,{'type':'extract','mime':mime,'body':base64.b64encode(raw).decode()},maximum=18*1024*1024)
                result=receive_message(stream)
        if result.get('type')!='result' or not isinstance(result.get('text'),str) or len(result['text'])>100000:
            raise ValueError()
    except Exception:
        raise ValueError('添付を安全に抽出できません。renderer・形式・暗号化・解析上限を確認してください。') from None
    with e.storage_lock(),r.transaction() as db:
        r.editable(workspace_id,db)
        eid=e.save(db,source_key=e.digest(('attachment\0'+str(workspace_id)+'\0'+filename).encode()),title=filename,text=result['text'],method='attachment-'+{'.txt':'text','.md':'markdown','.pdf':'pdf'}[Path(filename).suffix.lower()],publisher='手動添付',raw=raw,mime=mime,filename=filename)
        db.execute('INSERT OR IGNORE INTO workspace_evidence(workspace_id,evidence_id) VALUES(?,?)',(workspace_id,eid))
        return eid
