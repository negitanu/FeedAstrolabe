"""Shared-library identifier and quoted-assessment API."""
from flask import Blueprint,request,abort
from .db import get_db
from .keys import authenticate_api
from .research_api import errors,page
from .api import integer_arg
from . import entities as n,research as r,evidence as e,triage as t
api=Blueprint('entities_api',__name__,url_prefix='/api/v1')
api.before_request(authenticate_api)


def scope_arg():return integer_arg('workspace',None) if 'workspace' in request.args else None


def entity_query():
    clauses=[];params=[]
    if 'kind' in request.args:
        kind=request.args['kind']
        if kind not in n.KINDS:abort(400,description='Unknown entity kind')
        clauses.append('x.kind=?');params.append(kind)
    query=request.args.get('q','')
    if len(query)>200:abort(400)
    if query:
        pattern='%'+query.replace('!','!!').replace('%','!%').replace('_','!_')+'%'
        clauses.append("(x.display_name LIKE ? ESCAPE '!' OR x.canonical LIKE ? ESCAPE '!' OR EXISTS(SELECT 1 FROM entity_aliases s WHERE s.entity_id=x.id AND s.value LIKE ? ESCAPE '!'))");params.extend([pattern]*3)
    workspace=scope_arg()
    if workspace is not None:
        with errors():clause,values=n.workspace_clause(workspace)
        clauses.append(clause);params+=values
    return 'SELECT x.* FROM entities x'+(' WHERE '+' AND '.join(clauses) if clauses else ''),params

@api.get('/entities')
def listing():
    sql,params=entity_query();return page(sql,params,column='x.id')

@api.post('/entities')
def create():
    with errors():identifier=n.create(request.get_json())
    return detail(identifier),201

@api.get('/entities/<int:identifier>')
def detail(identifier):
    with errors():item=dict(n.find(identifier));item['root_id']=n.root(identifier)
    return {'data':item}

@api.get('/entities/<int:identifier>/aliases')
def aliases(identifier):
    with errors():n.find(identifier)
    return page('SELECT * FROM entity_aliases WHERE entity_id=?',[identifier])

@api.post('/entities/<int:identifier>/aliases')
def alias(identifier):
    with errors():aid=n.alias(identifier,request.get_json())
    return {'data':dict(get_db().execute('SELECT * FROM entity_aliases WHERE id=?',(aid,)).fetchone())},201

@api.post('/entities/<int:identifier>/merge')
@api.post('/entities/<int:identifier>/unmerge')
def merge(identifier):
    with errors():n.merge(identifier,request.get_json(),undo=request.path.endswith('/unmerge'))
    return detail(identifier)


def mentions_query(identifier):
    ids,truncated=n.family(identifier);params=list(ids)
    sql='SELECT m.*,e.title,e.publisher,e.captured_at,x.display_name,x.kind FROM entity_mentions m JOIN evidence e ON e.id=m.evidence_id JOIN entities x ON x.id=m.entity_id WHERE (m.entity_id IN ('+','.join('?' for _ in ids)+') OR m.original_entity_id IN ('+','.join('?' for _ in ids)+'))';params*=2
    workspace=scope_arg()
    if workspace is not None:
        with errors():r.find('workspace',workspace)
        sql+=' AND '+t.SCOPE;params += [workspace]*5
    return sql,params,truncated

@api.get('/entities/<int:identifier>/mentions')
def mentions(identifier):
    with errors():sql,params,truncated=mentions_query(identifier)
    result=page(sql,params,column='m.id');result['family_truncated']=truncated;return result

@api.get('/evidence/<int:identifier>/mentions')
def evidence_mentions(identifier):
    with errors():e.find(identifier)
    result=page('SELECT * FROM entity_mentions WHERE evidence_id=?',[identifier])
    marker=get_db().execute('SELECT * FROM entity_extractions WHERE evidence_id=?',(identifier,)).fetchone()
    result['extraction']=dict(marker) if marker else None
    return result

@api.post('/mentions')
def add_mention():
    with errors():mid=n.add_mention(request.get_json())
    return mention(mid),201

@api.get('/mentions/<int:identifier>')
def mention(identifier):
    with errors():return {'data':dict(n.mention(identifier))}

@api.patch('/mentions/<int:identifier>')
def correct(identifier):
    with errors():n.correct_mention(identifier,request.get_json())
    return mention(identifier)

@api.post('/evidence/<int:identifier>/extract-entities')
def extract(identifier):
    if request.get_data():abort(400,description='Empty body required')
    with errors():return {'data':n.extract(identifier,reprocess=True)}


def timeline_query(identifier):
    ids,truncated=n.family(identifier)
    sql='SELECT DISTINCT z.* FROM entity_audit z JOIN entity_audit_entities az ON az.audit_id=z.id WHERE az.entity_id IN ('+','.join('?' for _ in ids)+')';params=list(ids)
    workspace=scope_arg()
    if workspace is not None:
        with errors():r.find('workspace',workspace)
        sql+=' AND (z.workspace_id=? OR EXISTS(SELECT 1 FROM evidence e WHERE e.id=z.evidence_id AND '+t.SCOPE+'))';params+=[workspace]*6
    return sql,params,truncated

@api.get('/entities/<int:identifier>/timeline')
def timeline(identifier):
    with errors():sql,params,truncated=timeline_query(identifier)
    result=page(sql,params,column='z.id',transform=n.audit_record);result['family_truncated']=truncated;return result

@api.get('/entities/<int:identifier>/graph')
def graph(identifier):
    with errors():return {'data':n.graph(identifier,scope_arg(),integer_arg('depth',2,minimum=0,maximum=2),integer_arg('limit',200,maximum=200))}


def relation_query():
    clauses=[];params=[];workspace=scope_arg()
    if workspace is not None:
        with errors():r.find('workspace',workspace)
        clauses.append('a.workspace_id=?');params.append(workspace)
    if 'entity' in request.args:
        identifier=integer_arg('entity',None)
        with errors():ids,truncated=n.family(identifier)
        marks=','.join('?' for _ in ids);clauses.append(f'(v.source_id IN ({marks}) OR v.target_id IN ({marks}))');params+=ids*2
    archived=request.args.get('archived','false')
    if archived not in ('true','false'):abort(400)
    clauses.append('v.archived=?');params.append(int(archived=='true'))
    return n.RELATION_SQL+' WHERE '+' AND '.join(clauses),params

@api.get('/relations')
def relations():
    sql,params=relation_query();return page(sql,params,column='a.id')

@api.post('/workspaces/<int:identifier>/relations')
def add_relation(identifier):
    with errors():rid=n.save_relation(identifier,request.get_json())
    return relation(rid),201

@api.get('/relations/<int:identifier>')
def relation(identifier):
    with errors():return {'data':r.record(n.relation(identifier))}

@api.patch('/relations/<int:identifier>')
def edit_relation(identifier):
    with errors():item=n.relation(identifier);n.save_relation(item['workspace_id'],request.get_json(),identifier)
    return relation(identifier)

@api.get('/relations/<int:identifier>/revisions')
def relation_versions(identifier):
    with errors():n.relation(identifier)
    return page('SELECT * FROM relation_versions WHERE relation_id=?',[identifier])
