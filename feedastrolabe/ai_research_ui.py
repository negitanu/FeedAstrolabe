"""Japanese paper/release histories and grounded model/evaluation records."""
from flask import Blueprint,render_template,request,redirect,url_for,flash
from .research_ui import errors,identifier,ui_page
from . import ai_research as a,research as r
ui=Blueprint('ai',__name__,url_prefix='/ai-research')

@ui.get('')
def index():
 workspace=request.args.get('workspace') or None;query=request.args.get('q','');sql='SELECT * FROM ai_watches';params=[]
 with errors():
  query=r.text(query,'q',100)
  if workspace:workspace=identifier(workspace);r.find('workspace',workspace);sql+=' WHERE workspace_id=?';params.append(workspace)
  if query:sql+=(' AND ' if workspace else ' WHERE ')+'(instr(lower(target),lower(?))>0 OR instr(lower(term),lower(?))>0)';params.extend([query,query])
 listing=ui_page(sql,params);card_sql='SELECT c.*,e.display_name FROM ai_cards c JOIN entities e ON e.id=c.entity_id';card_params=[];clauses=[]
 if workspace:clauses.append('c.workspace_id=?');card_params.append(workspace)
 if query:clauses.append('(instr(lower(e.display_name),lower(?))>0 OR instr(lower(c.version),lower(?))>0)');card_params.extend([query,query])
 cards=ui_page(card_sql+(' WHERE '+' AND '.join(clauses) if clauses else ''),card_params,name='cards_page',order='c.id DESC')
 return render_template('ai_research.html',listing=listing,cards=cards,workspace=workspace,query=query)

@ui.post('/watches')
def create_watch():
 with errors():wid=a.save_watch(identifier(request.form.get('workspace_id')),{'provider':request.form.get('provider'),'target':request.form.get('target'),'term':request.form.get('term',''),'outbound_public':request.form.get('outbound_public')=='on','interval_seconds':identifier(request.form.get('interval_seconds'))})
 return redirect(url_for('ai.watch',watch_id=wid))

@ui.get('/watches/<int:watch_id>')
def watch(watch_id):
 with errors():card=a.watch_card(watch_id)
 query=request.args.get('q','')
 with errors():query=r.text(query,'q',100)
 listing=ui_page('SELECT * FROM ai_versions WHERE watch_id=?'+(' AND instr(lower(payload),lower(?))>0' if query else ''),[watch_id,query] if query else [watch_id]);listing['rows']=[a.decoded(x) for x in listing['rows']]
 return render_template('ai_watch.html',card=card,listing=listing,query=query)

@ui.post('/watches/<int:watch_id>/lookup')
def lookup(watch_id):
 with errors():a.lookup(watch_id)
 flash('公開メタデータの照会を予約しました。','success');return redirect(url_for('ai.watch',watch_id=watch_id))

@ui.post('/watches/<int:watch_id>/update')
def update(watch_id):
 from .settings_pages import object_redirect
 with errors():w=a.find('ai_watches',watch_id);a.save_watch(w['workspace_id'],{'expected_revision':identifier(request.form.get('expected_revision')),'enabled':request.form.get('enabled')=='on','outbound_public':request.form.get('outbound_public')=='on','interval_seconds':identifier(request.form.get('interval_seconds'))},watch_id)
 flash('収集設定を保存しました。','success')
 return redirect(object_redirect('ai', watch_id, 'ai.watch', watch_id=watch_id))

@ui.post('/cards')
def create_card():
 body={key:request.form.get(key) or None for key in a.CLAIMS};body.update(entity_id=identifier(request.form.get('entity_id')),quotation_id=identifier(request.form.get('quotation_id')),version=request.form.get('version'))
 with errors():cid=a.create_card(identifier(request.form.get('workspace_id')),body)
 return redirect(url_for('ai.card',card_id=cid))

@ui.get('/cards/<int:card_id>')
def card(card_id):
 with errors():result=a.card(card_id)
 listing=ui_page('SELECT * FROM ai_benchmarks WHERE card_id=?',[card_id]);listing['rows']=[a.decoded(x) for x in listing['rows']]
 return render_template('ai_card.html',card=result,listing=listing,condition_fields=sorted(a.CONDITIONS))

@ui.post('/cards/<int:card_id>/links')
def add_link(card_id):
 with errors():a.add_link(card_id,{'kind':request.form.get('kind'),'url':request.form.get('url'),'quotation_id':identifier(request.form.get('quotation_id')),'reviewed':request.form.get('reviewed')=='on'})
 return redirect(url_for('ai.card',card_id=card_id))

@ui.post('/cards/<int:card_id>/benchmarks')
def benchmark(card_id):
 body={key:request.form.get(key) or None for key in a.CONDITIONS};body.update(status=request.form.get('status'),result=request.form.get('result'),notes=request.form.get('notes',''))
 if request.form.get('quotation_id'):body['quotation_id']=identifier(request.form['quotation_id'])
 with errors():a.benchmark(card_id,body)
 return redirect(url_for('ai.card',card_id=card_id))

@ui.get('/compare')
def compare():
 with errors():comparison=a.compare(identifier(request.args.get('left')),identifier(request.args.get('right')))
 return render_template('ai_compare.html',comparison=comparison)
