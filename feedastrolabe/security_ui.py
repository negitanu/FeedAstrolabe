"""Japanese server rendered security signals; POST is covered by global CSRF."""
from flask import Blueprint,render_template,request,redirect,url_for,flash
from .research_ui import errors,ui_page,identifier
from . import security_intelligence as s,connectors as c,research as r
from .db import get_db
from .connector_registry import PROVIDERS
ui=Blueprint('security',__name__,url_prefix='/security')

@ui.get('')
def index():
    workspace=request.args.get('workspace') or None;params=[];sql='SELECT * FROM security_watches'
    with errors():
        if workspace:workspace=identifier(workspace);r.find('workspace',workspace);sql+=' WHERE workspace_id=?';params.append(workspace)
    listing=ui_page(sql,params)
    settings=get_db().execute('SELECT s.*,z.last_request,z.cooldown_until,z.requests,z.budget_day FROM connector_settings s JOIN connector_state z ON z.provider=s.provider ORDER BY s.provider').fetchall()
    jobs=ui_page('SELECT * FROM connector_jobs',name='jobs_page')
    return render_template('security.html',listing=listing,workspace=workspace,settings=settings,providers=PROVIDERS,jobs=jobs)

@ui.post('/connectors/<provider>')
def configure(provider):
    with errors():c.configure(provider,{'expected_revision':identifier(request.form.get('expected_revision')),'enabled':request.form.get('enabled')=='on','daily_budget':identifier(request.form.get('daily_budget')),'ttl_seconds':identifier(request.form.get('ttl_seconds'))})
    flash('公開識別子の連携設定を保存しました。','success');return redirect(url_for('settings_pages.page',section='connectors'))

@ui.post('/watches')
def create():
    with errors():wid=s.save_watch(identifier(request.form.get('workspace_id')),{'entity_id':identifier(request.form.get('entity_id')),'product':request.form.get('product',''),'version':request.form.get('version',''),'outbound_public':request.form.get('outbound_public')=='on'})
    return redirect(url_for('security.detail',watch_id=wid))

@ui.get('/watches/<int:watch_id>')
def detail(watch_id):
    with errors():card=s.card(watch_id)
    reviews=ui_page('SELECT * FROM security_reviews WHERE watch_id=?',[watch_id]);observations=ui_page('SELECT * FROM security_observations WHERE entity_id=?',[card['entity']['id']],name='observations_page')
    refs=ui_page('SELECT * FROM security_references WHERE workspace_id=? AND entity_id=?',[card['watch']['workspace_id'],card['entity']['id']],name='refs_page')
    return render_template('vulnerability.html',card=card,reviews=reviews,observations=observations,refs=refs)

@ui.post('/watches/<int:watch_id>/update')
def update(watch_id):
    from .settings_pages import object_redirect
    with errors():
        old=s.watch(watch_id);s.save_watch(old['workspace_id'],{'expected_revision':identifier(request.form.get('expected_revision')),'product':request.form.get('product',''),'version':request.form.get('version',''),'outbound_public':request.form.get('outbound_public')=='on','enabled':request.form.get('enabled')=='on'},watch_id)
    flash('ウォッチ設定を保存しました。','success')
    return redirect(object_redirect('security', watch_id, 'security.detail', watch_id=watch_id))

@ui.post('/watches/<int:watch_id>/review')
def review(watch_id):
    with errors():s.review(watch_id,{'expected_revision':identifier(request.form.get('expected_revision')),'status':request.form.get('status'),'quotation_id':identifier(request.form.get('quotation_id')) if request.form.get('quotation_id') else None,'reason':request.form.get('reason'),'author':request.form.get('author')})
    return redirect(url_for('security.detail',watch_id=watch_id))

@ui.post('/watches/<int:watch_id>/reference')
def reference(watch_id):
    with errors():
        old=s.watch(watch_id);s.reference(old['workspace_id'],{'entity_id':old['entity_id'],'url':request.form.get('url'),'kind':request.form.get('kind'),'quotation_id':identifier(request.form.get('quotation_id')),'reviewed':request.form.get('reviewed')=='on','author':request.form.get('author')})
    return redirect(url_for('security.detail',watch_id=watch_id))
