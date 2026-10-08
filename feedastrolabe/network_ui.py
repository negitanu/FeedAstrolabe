"""Passive Japanese history UI; no browser scripts or automatic lookups on GET."""
from flask import Blueprint,render_template,request,redirect,url_for,flash
from .research_ui import errors,ui_page,identifier
from . import network_intelligence as n,research as r
from .network_api import decoded
ui=Blueprint('network',__name__,url_prefix='/network')

@ui.get('')
def index():
    workspace=request.args.get('workspace') or None;sql='SELECT * FROM network_watches';params=[]
    with errors():
        if workspace:workspace=identifier(workspace);r.find('workspace',workspace);sql+=' WHERE workspace_id=?';params.append(workspace)
    listing=ui_page(sql,params)
    return render_template('network.html',listing=listing,workspace=workspace)

@ui.post('/watches')
def create():
    with errors():
        body={'entity_id':identifier(request.form.get('entity_id')),'provider':request.form.get('provider'),'outbound_public':request.form.get('outbound_public')=='on','interval_seconds':identifier(request.form.get('interval_seconds')),'retention_days':identifier(request.form.get('retention_days'))}
        for field in ('rrtype','prefix','origin'):
            if request.form.get(field):body[field]=request.form[field]
        wid=n.save_watch(identifier(request.form.get('workspace_id')),body)
    return redirect(url_for('network.detail',watch_id=wid))

@ui.get('/watches/<int:watch_id>')
def detail(watch_id):
    with errors():card=n.card(watch_id)
    observations=ui_page('SELECT * FROM network_observations WHERE watch_id=?',[watch_id]);observations['rows']=[decoded(row) for row in observations['rows']]
    events=ui_page('SELECT * FROM network_events WHERE watch_id=?',[watch_id],name='events_page');events['rows']=[decoded(row) for row in events['rows']]
    return render_template('network_watch.html',card=card,observations=observations,events=events)

@ui.post('/watches/<int:watch_id>/lookup')
def lookup(watch_id):
    with errors():result=n.lookup(watch_id)
    flash('IANA登録局情報を先に予約しました。取得後に再度照会してください。' if result['bootstrap_job_id'] else '受動的な公開情報照会を予約しました。','success')
    return redirect(url_for('network.detail',watch_id=watch_id))

@ui.post('/watches/<int:watch_id>/update')
def update(watch_id):
    with errors():item=n.watch(watch_id);n.save_watch(item['workspace_id'],{'expected_revision':identifier(request.form.get('expected_revision')),'outbound_public':request.form.get('outbound_public')=='on','enabled':request.form.get('enabled')=='on','interval_seconds':identifier(request.form.get('interval_seconds')),'retention_days':identifier(request.form.get('retention_days'))},watch_id)
    return redirect(url_for('network.detail',watch_id=watch_id))
