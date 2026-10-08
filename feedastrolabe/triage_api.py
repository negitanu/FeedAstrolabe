"""Bearer-scoped saved conditions, inbox, digest and provenance groups."""
from flask import Blueprint,request,abort
from .keys import authenticate_api
from .db import get_db
from .research_api import page,errors
from .api import integer_arg
from . import triage as t,research as r,evidence as e
api=Blueprint('triage_api',__name__,url_prefix='/api/v1')
api.before_request(authenticate_api)

@api.get('/workspaces/<int:identifier>/watchlists')
def lists(identifier):
    with errors():r.find('workspace',identifier)
    return page('SELECT w.*,v.id AS version_id,v.query,v.exclusion,v.priority,v.reason,v.cursor FROM watchlists w JOIN watchlist_versions v ON v.watchlist_id=w.id AND v.revision=w.revision WHERE w.workspace_id=?',[identifier],column='w.id',transform=t.record)

@api.post('/workspaces/<int:identifier>/watchlists')
def create(identifier):
    with errors():wid=t.save(identifier,request.get_json())
    return detail(wid),201

@api.get('/watchlists/<int:identifier>')
def detail(identifier):
    with errors():return {'data':t.record(t.find(identifier))}

@api.patch('/watchlists/<int:identifier>')
def update(identifier):
    with errors():item=t.find(identifier);t.save(item['workspace_id'],request.get_json(),identifier)
    return detail(identifier)

@api.get('/watchlists/<int:identifier>/revisions')
def versions(identifier):
    with errors():t.find(identifier)
    return page('SELECT * FROM watchlist_versions WHERE watchlist_id=?',[identifier],transform=t.record)

@api.get('/watchlists/<int:identifier>/preview')
def preview(identifier):
    with errors():return t.preview(identifier,integer_arg('after_id',0,minimum=0))

@api.post('/watchlists/<int:identifier>/process')
def process(identifier):
    if request.get_data():abort(400,description='Empty body required')
    with errors():return {'data':t.process(identifier)}

@api.post('/watchlists/<int:identifier>/reprocess')
def reprocess(identifier):
    if request.get_data():abort(400,description='Empty body required')
    with errors():return {'data':t.reprocess(identifier)}

@api.get('/workspaces/<int:identifier>/watch-events')
@api.get('/workspaces/<int:identifier>/digest')
def events(identifier):
    with errors():r.find('workspace',identifier)
    sql=t.EVENT_SQL+' WHERE w.workspace_id=?';params=[identifier]
    if request.path.endswith('/digest'):
        with errors():day=t.date(request.args.get('date',r.now()[:10]))
        sql+=' AND x.included=1 AND x.created_at>=? AND x.created_at<=?';params += [day+' 00:00:00',day+' 23:59:59']
    for name in ('seen','included'):
        if name in request.args:
            if request.args[name] not in ('true','false'):abort(400)
            sql+=' AND x.'+name+'=?';params.append(int(request.args[name]=='true'))
    return page(sql,params,column='x.id',transform=t.record)

@api.patch('/watch-events/<int:identifier>')
def seen(identifier):
    with errors():
        t.positive_id(identifier)
        values=r.fields(request.get_json(),{'seen'})
        if type(values.get('seen')) is not bool:raise ValueError('seen は boolean です。')
        with e.storage_lock(),r.transaction() as db:
            row=db.execute(t.EVENT_SQL+' WHERE x.id=?',(identifier,)).fetchone()
            if row is None:raise r.ResearchMissing('通知が見つかりません。')
            r.editable(row['workspace_id'],db)
            db.execute('UPDATE watch_events SET seen=? WHERE id=?',(int(values['seen']),identifier))
    return {'data':t.record(get_db().execute(t.EVENT_SQL+' WHERE x.id=?',(identifier,)).fetchone())}

@api.get('/duplicate-groups')
def groups():
    suppressed=request.args.get('suppressed','false')
    if suppressed not in ('true','false'):abort(400)
    return page('SELECT g.*,(SELECT count(*) FROM duplicate_members m WHERE m.group_id=g.id) AS member_count FROM duplicate_groups g WHERE g.suppressed=?',[int(suppressed=='true')],column='g.id')

@api.get('/duplicate-groups/<int:identifier>')
def group(identifier):
    with errors():item=t.group(identifier)
    return {'data':dict(item)}

@api.get('/duplicate-groups/<int:identifier>/members')
def members(identifier):
    with errors():t.group(identifier)
    return page('SELECT e.*,a.is_read,a.is_starred FROM duplicate_members m JOIN evidence e ON e.id=m.evidence_id LEFT JOIN articles a ON a.id=e.article_id WHERE m.group_id=?',[identifier],column='e.id',transform=lambda row:{k:v for k,v in dict(row).items() if k!='text'})

@api.patch('/duplicate-groups/<int:identifier>')
def toggle(identifier):
    with errors():t.toggle_group(identifier,request.get_json())
    return group(identifier)
