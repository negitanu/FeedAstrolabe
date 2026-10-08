"""Scoped read/write APIs for public connector consent and local security cards."""
from flask import Blueprint,request,abort
from .keys import authenticate_api
from .research_api import errors,page
from .api import integer_arg
from .db import get_db
from . import connectors as c,security_intelligence as s,research as r
from .security_adapters import PROVIDERS
api=Blueprint('security_api',__name__,url_prefix='/api/v1');api.before_request(authenticate_api)

@api.get('/connectors')
def providers():
    rows=get_db().execute('SELECT s.*,z.last_request,z.cooldown_until,z.budget_day,z.requests FROM connector_settings s JOIN connector_state z ON z.provider=s.provider ORDER BY s.provider').fetchall()
    return {'data':[dict(row,**PROVIDERS[row['provider']]) for row in rows]}

@api.patch('/connectors/<provider>')
def configure(provider):
    with errors():result=c.configure(provider,request.get_json())
    return {'data':result}

@api.get('/connector-jobs')
def jobs():
    clauses=[];params=[]
    if 'provider' in request.args:
        with errors():c.setting(request.args['provider'])
        clauses.append('provider=?');params.append(request.args['provider'])
    return page('SELECT * FROM connector_jobs'+(' WHERE '+' AND '.join(clauses) if clauses else ''),params)

@api.post('/connectors/<provider>/jobs')
def enqueue(provider):
    with errors():identifier=c.enqueue(provider,request.get_json())
    return job(identifier),202

@api.get('/connector-jobs/<int:identifier>')
def job(identifier):
    with errors():
        from .triage import positive_id
        positive_id(identifier);row=get_db().execute('SELECT * FROM connector_jobs WHERE id=?',(identifier,)).fetchone()
        if row is None:raise r.ResearchMissing('連携ジョブが見つかりません。')
    return {'data':dict(row)}

@api.get('/workspaces/<int:identifier>/security-watches')
def watches(identifier):
    with errors():r.find('workspace',identifier)
    return page('SELECT * FROM security_watches WHERE workspace_id=?',[identifier])

@api.post('/workspaces/<int:identifier>/security-watches')
def create(identifier):
    with errors():wid=s.save_watch(identifier,request.get_json())
    return detail(wid),201

@api.get('/security-watches/<int:identifier>')
def detail(identifier):
    with errors():return {'data':s.card(identifier)}

@api.patch('/security-watches/<int:identifier>')
def update(identifier):
    with errors():old=s.watch(identifier);s.save_watch(old['workspace_id'],request.get_json(),identifier)
    return detail(identifier)

@api.post('/security-watches/<int:identifier>/reviews')
def review(identifier):
    with errors():s.review(identifier,request.get_json())
    return detail(identifier),201

@api.get('/security-watches/<int:identifier>/reviews')
def reviews(identifier):
    with errors():s.watch(identifier)
    return page('SELECT * FROM security_reviews WHERE watch_id=?',[identifier])

@api.get('/entities/<int:identifier>/security-observations')
def observations(identifier):
    with errors():s.cve_entity(identifier)
    def record(row):
        import json
        item=dict(row);item['payload']=json.loads(item['payload']);return item
    return page('SELECT * FROM security_observations WHERE entity_id=?',[identifier],transform=record)

@api.get('/entities/<int:identifier>/vulnerability')
def vulnerability(identifier):
    with errors():return {'data':s.observations(identifier)}

@api.post('/workspaces/<int:identifier>/security-references')
def reference(identifier):
    with errors():rid=s.reference(identifier,request.get_json())
    return {'data':dict(get_db().execute('SELECT * FROM security_references WHERE id=?',(rid,)).fetchone())},201

@api.get('/workspaces/<int:identifier>/security-references')
def references(identifier):
    with errors():r.find('workspace',identifier)
    return page('SELECT * FROM security_references WHERE workspace_id=?',[identifier])
