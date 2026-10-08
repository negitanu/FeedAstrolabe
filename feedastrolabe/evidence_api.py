"""Scoped evidence and provenance endpoints."""
import io
from flask import Blueprint,abort,request,send_file,url_for
from .keys import authenticate_api
from .db import get_db
from . import evidence as e,research as r
from .research_api import errors,page
from .api import integer_arg
from .attachments import upload

api=Blueprint('evidence_api',__name__,url_prefix='/api/v1')
api.before_request(authenticate_api)


def filters():
    clauses,params=[],[]
    for name in ('workspace','note'):
        if name in request.args:
            identifier=integer_arg(name,None)
            with errors():r.find(name,identifier)
            if name=='workspace':
                clauses.append('''(EXISTS(SELECT 1 FROM workspace_evidence w WHERE w.evidence_id=e.id AND w.workspace_id=?) OR EXISTS(SELECT 1 FROM note_evidence n JOIN notes nn ON nn.id=n.note_id WHERE n.evidence_id=e.id AND nn.workspace_id=?) OR EXISTS(SELECT 1 FROM quotations q WHERE q.evidence_id=e.id AND q.workspace_id=?))''')
                params.extend([identifier]*3)
            else:
                clauses.append('(EXISTS(SELECT 1 FROM note_evidence n WHERE n.evidence_id=e.id AND n.note_id=?) OR EXISTS(SELECT 1 FROM quotations q WHERE q.evidence_id=e.id AND q.note_id=?))')
                params.extend([identifier]*2)
    if 'article' in request.args:
        identifier=integer_arg('article',None)
        with errors():r.find('article',identifier)
        clauses.append('e.article_id=?');params.append(identifier)
    return (' WHERE '+' AND '.join(clauses) if clauses else ''),params


@api.get('/evidence')
def listing():
    where,params=filters()
    def summary(row):
        item=dict(row);item.pop('text');return item
    return page('SELECT e.*,b.size FROM evidence e JOIN evidence_blobs b ON b.hash=e.blob_hash'+where,params,column='e.id',transform=summary)


@api.get('/evidence/<int:identifier>')
def detail(identifier):
    with errors():
        item=dict(e.find(identifier))
        if e.digest(item['text'].encode())!=item['text_hash']:abort(409,description='根拠テキストの整合性が不正です。')
    return {'data':item}


@api.get('/evidence/<int:identifier>/download')
def download(identifier):
    with errors():
        with e.storage_lock():
            item=e.find(identifier);raw=e.read_blob(item['blob_hash'],item['size'])
    return send_file(io.BytesIO(raw),mimetype='application/octet-stream',as_attachment=True,download_name=item['filename'] or f'evidence-{identifier}.txt',max_age=0)


@api.post('/articles/<int:identifier>/evidence')
def capture(identifier):
    if request.get_data():abort(400,description='Empty request body required')
    with errors():eid=e.article_capture(identifier)
    return detail(eid),201,{'Location':url_for('evidence_api.detail',identifier=eid)}


@api.post('/workspaces/<int:identifier>/attachments')
def attachment(identifier):
    if set(request.files)!={'file'} or request.form or len(request.files.getlist('file'))!=1:abort(400,description='Supply one multipart file')
    with errors():eid=upload(identifier,request.files['file'])
    return detail(eid),201


def link(kind,identifier,evidence_id):
    if request.get_data():abort(400,description='Empty request body required')
    with errors():e.pin(kind,identifier,evidence_id,remove=request.method=='DELETE')
    return '',204


for kind in ('workspace','note'):
    def handler(identifier,evidence_id,kind=kind):return link(kind,identifier,evidence_id)
    api.add_url_rule(f'/{kind}s/<int:identifier>/evidence/<int:evidence_id>',endpoint=kind+'_pin',view_func=handler,methods=['POST','DELETE'])


@api.get('/workspaces/<int:identifier>/quotations')
def quotations(identifier):
    with errors():r.find('workspace',identifier)
    return page('SELECT * FROM quotations WHERE workspace_id=?',[identifier])


@api.post('/workspaces/<int:identifier>/quotations')
def quote(identifier):
    with errors():qid=e.quotation(identifier,request.get_json())
    return {'data':dict(get_db().execute('SELECT * FROM quotations WHERE id=?',(qid,)).fetchone())},201


@api.get('/evidence-settings')
def settings():
    result=dict(get_db().execute('SELECT * FROM evidence_settings').fetchone());result.pop('id')
    result['used_bytes']=get_db().execute('SELECT coalesce(sum(size),0) FROM evidence_blobs').fetchone()[0]
    result['capture_errors']=[dict(row) for row in get_db().execute('SELECT * FROM evidence_capture_errors ORDER BY feed_id LIMIT 100')]
    return {'data':result}


@api.patch('/evidence-settings')
def update_settings():
    with errors():
        values=r.fields(request.get_json(),{'quota_bytes','retention_days'})
        for name,value in values.items():
            low,high=(10*1024*1024,10*1024*1024*1024) if name=='quota_bytes' else (1,3650)
            if type(value) is not int or not low<=value<=high:raise ValueError(name+' の上限が不正です。')
        with e.storage_lock(),r.transaction() as db:
            db.execute('UPDATE evidence_settings SET '+','.join(name+'=?' for name in values)+' WHERE id=1',list(values.values()))
    return settings()
