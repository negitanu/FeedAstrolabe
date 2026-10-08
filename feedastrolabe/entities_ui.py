"""Native Japanese attributed-entity UI and bounded server-rendered SVG graph."""
import math
from werkzeug.datastructures import ImmutableMultiDict
from flask import Blueprint,render_template,request,redirect,url_for,abort,flash
from . import entities as n,research as r,evidence as e
from .db import get_db
from .research_ui import errors,ui_page,identifier as positive
from .entities_api import entity_query,mentions_query,timeline_query,relation_query,scope_arg
ui=Blueprint('entities',__name__,url_prefix='/entities')

@ui.before_request
def optional_filters():
    # HTML forms submit empty optional fields; API arguments remain strict.
    request.args=ImmutableMultiDict((key,value) for key,value in request.args.items(multi=True) if not (key in {'workspace','kind','entity'} and value==''))

@ui.get('')
def index():
    with errors():sql,params=entity_query()
    listing=ui_page(sql,params,order='x.id DESC')
    return render_template('entities.html',listing=listing,kinds=sorted(n.KINDS),workspace=scope_arg())

@ui.post('/create')
def create():
    with errors():identifier=n.create({key:request.form.get(key,'') for key in ['kind','value','author']})
    return redirect(url_for('entities.detail',identifier=identifier))

@ui.get('/<int:identifier>')
def detail(identifier):
    with errors():
        item=n.find(identifier);root_id=n.root(identifier);sql,params,truncated=mentions_query(identifier);timeline_sql,timeline_params,timeline_truncated=timeline_query(identifier)
        graph=n.graph(identifier,scope_arg())
    mentions=ui_page(sql,params,name='mentions_page',order='m.id DESC');timeline=ui_page(timeline_sql,timeline_params,name='timeline_page',order='z.id DESC');timeline['rows']=[n.audit_record(row) for row in timeline['rows']]
    aliases=ui_page('SELECT * FROM entity_aliases WHERE entity_id=?',[identifier],name='aliases_page')
    # Stable circular placement works without client scripts and is supplemented by a list.
    count=max(1,len(graph['nodes']));positions={node['id']:(400+300*math.cos(2*math.pi*i/count),300+230*math.sin(2*math.pi*i/count)) for i,node in enumerate(graph['nodes'])}
    return render_template('entity.html',item=item,root_id=root_id,mentions=mentions,timeline=timeline,aliases=aliases,graph=graph,positions=positions,truncated=truncated or timeline_truncated,workspace=scope_arg())

@ui.post('/<int:identifier>/alias')
def alias(identifier):
    with errors():n.alias(identifier,{'value':request.form.get('value'),'reviewed':request.form.get('reviewed')=='on','author':request.form.get('author','local-user')})
    return redirect(url_for('entities.detail',identifier=identifier))

@ui.post('/<int:identifier>/merge')
@ui.post('/<int:identifier>/unmerge',endpoint='unmerge')
def merge(identifier):
    undo=request.path.endswith('/unmerge')
    with errors():
        body={'expected_revision':positive(request.form.get('expected_revision')),'reason':request.form.get('reason'),'author':request.form.get('author','local-user')}
        if not undo:body.update(target_id=positive(request.form.get('target_id')),reviewed=request.form.get('reviewed')=='on')
        n.merge(identifier,body,undo=undo)
    return redirect(url_for('entities.detail',identifier=identifier))

@ui.post('/mentions/<int:identifier>/correct')
def correct(identifier):
    with errors():
        old=n.mention(identifier);body={'expected_revision':positive(request.form.get('expected_revision')),'entity_id':positive(request.form.get('entity_id')),'status':request.form.get('status'),'author':request.form.get('author','local-user')};n.correct_mention(identifier,body)
    return redirect(url_for('entities.detail',identifier=old['entity_id']))

@ui.post('/evidence/<int:identifier>/extract')
def extract(identifier):
    with errors():result=n.extract(identifier,reprocess=True)
    flash(f"対象抽出：{result['mentions_created']}件の新しい言及。既存の訂正・却下は保持します。",'success')
    return redirect(url_for('evidence.detail',eid=identifier))

@ui.post('/mentions/create')
def mention():
    with errors():
        try:start=int(request.form.get('start',''));end=int(request.form.get('end',''))
        except ValueError:raise ValueError('文字位置が不正です。') from None
        mid=n.add_mention({'entity_id':positive(request.form.get('entity_id')),'evidence_id':positive(request.form.get('evidence_id')),'start':start,'end':end,'original':request.form.get('original'),'status':'confirmed','author':request.form.get('author','local-user')})
        item=n.mention(mid)
    return redirect(url_for('entities.detail',identifier=item['entity_id']))

@ui.get('/relations')
def relations():
    with errors():sql,params=relation_query()
    listing=ui_page(sql,params,order='a.id DESC')
    return render_template('relations.html',listing=listing,workspace=scope_arg(),entity=request.args.get('entity'))

@ui.get('/relations/<int:identifier>')
def relation(identifier):
    with errors():item=n.relation(identifier);workspace=r.find('workspace',item['workspace_id'])
    versions=ui_page('SELECT * FROM relation_versions WHERE relation_id=?',[identifier])
    return render_template('relation.html',item=item,workspace=workspace,versions=versions)


def relation_fields():
    values={name:request.form.get(name,'') for name in ['predicate','label','confidence','author']}
    values.update({name:positive(request.form.get(name)) for name in ['source_id','target_id','quotation_id']})
    values.update({name:request.form.get(name) or None for name in ['observed_at','valid_from','valid_to']});values['archived']=request.form.get('archived')=='on'
    return values

@ui.get('/relations/new/<int:workspace_id>')
def new_relation(workspace_id):
    with errors():workspace=r.find('workspace',workspace_id)
    return render_template('relation_new.html',workspace=workspace)

@ui.post('/relations/new/<int:workspace_id>')
def add_relation(workspace_id):
    with errors():identifier=n.save_relation(workspace_id,relation_fields())
    return redirect(url_for('entities.relation',identifier=identifier))

@ui.post('/relations/<int:identifier>/update')
def update_relation(identifier):
    with errors():
        item=n.relation(identifier);body=relation_fields();body['expected_revision']=positive(request.form.get('expected_revision'));n.save_relation(item['workspace_id'],body,identifier)
    return redirect(url_for('entities.relation',identifier=identifier))
