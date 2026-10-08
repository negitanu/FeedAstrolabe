"""Japanese saved-rule and digest UI; global CSRF covers mutations."""
import json
from flask import Blueprint,render_template,request,redirect,url_for,flash,abort
from . import triage as t,research as r
from .db import get_db
from .research_ui import ui_page,errors
ui=Blueprint('triage',__name__,url_prefix='/triage')

@ui.get('/<int:workspace_id>')
def index(workspace_id):
    with errors():workspace=r.find('workspace',workspace_id);day=t.date(request.args.get('date',r.now()[:10]))
    lists=ui_page('SELECT id FROM watchlists WHERE workspace_id=?',[workspace_id],name='lists_page')
    rules=[t.record(t.find(row['id'])) for row in lists['rows']]
    clauses=['w.workspace_id=?'];params=[workspace_id]
    if request.args.get('digest','false') not in ('true','false'):abort(400)
    digest=request.args.get('digest','false')=='true'
    if digest:clauses += ['x.included=1','x.created_at>=?','x.created_at<=?'];params += [day+' 00:00:00',day+' 23:59:59']
    events=ui_page(t.EVENT_SQL+' WHERE '+' AND '.join(clauses),params,name='events_page',order='x.id DESC')
    events['rows']=[t.record(row) for row in events['rows']]
    return render_template('triage.html',workspace=workspace,lists=lists,rules=rules,events=events,day=day,digest=digest)

def fields():
    try:
        return {'name':request.form['name'],'kind':request.form['kind'],'enabled':request.form.get('enabled')=='on','query':json.loads(request.form['query']) if request.form.get('query') else {'any':[{'field':request.form.get('match_field','text'),'op':'contains','value':term.strip()} for term in request.form.get('terms','').splitlines() if term.strip()]},'exclusion':json.loads(request.form['exclusion']) if request.form.get('exclusion') else {'any':[{'field':'text','op':'contains','value':term.strip()} for term in request.form.get('exclude_terms','').splitlines() if term.strip()]},'priority':request.form['priority'],'reason':request.form.get('reason','')}
    except (ValueError,KeyError):raise ValueError('検索条件の JSON または入力が不正です。') from None

@ui.post('/<int:workspace_id>/create')
def create(workspace_id):
    with errors():t.save(workspace_id,fields())
    flash('条件を保存しました。次の worker 処理で照合します。','success')
    return redirect(url_for('triage.index',workspace_id=workspace_id))

@ui.get('/watchlists/<int:identifier>')
def detail(identifier):
    with errors():item=t.record(t.find(identifier));workspace=r.find('workspace',item['workspace_id'])
    versions=ui_page('SELECT * FROM watchlist_versions WHERE watchlist_id=?',[identifier]);versions['rows']=[t.record(row) for row in versions['rows']]
    return render_template('watchlist.html',item=item,workspace=workspace,versions=versions)

@ui.post('/watchlists/<int:identifier>/update')
def update(identifier):
    with errors():
        item=t.find(identifier);values=fields()
        try:values['expected_revision']=int(request.form.get('expected_revision',''))
        except ValueError:raise ValueError('版番号が不正です。') from None
        t.save(item['workspace_id'],values,identifier)
    return redirect(url_for('triage.detail',identifier=identifier))

@ui.post('/watchlists/<int:identifier>/process')
def process(identifier):
    with errors():result=t.process(identifier);item=t.find(identifier)
    flash(f"今回の照合：{result['evidence_scanned']}件、新規通知：{result['events_created']}件。",'success')
    return redirect(url_for('triage.index',workspace_id=item['workspace_id']))

@ui.post('/watchlists/<int:identifier>/reprocess')
def reprocess(identifier):
    with errors():result=t.reprocess(identifier);item=t.find(identifier)
    flash(f"今回の照合：{result['evidence_scanned']}件、新規通知：{result['events_created']}件。同じ版の再処理では通知を重複させません。",'success')
    return redirect(url_for('triage.index',workspace_id=item['workspace_id']))

@ui.post('/events/<int:identifier>/seen')
def seen(identifier):
    # Reuse the same scoped implementation after UI CSRF; no synthetic bearer key.
    from . import evidence as e
    with errors():
        t.positive_id(identifier)
        with e.storage_lock(),r.transaction() as db:
            row=db.execute(t.EVENT_SQL+' WHERE x.id=?',(identifier,)).fetchone()
            if row is None:raise r.ResearchMissing('通知が見つかりません。')
            r.editable(row['workspace_id'],db);db.execute('UPDATE watch_events SET seen=1-seen WHERE id=?',(identifier,))
    return redirect(url_for('triage.index',workspace_id=row['workspace_id']))

@ui.get('/groups')
def groups():
    if request.args.get('suppressed','false') not in ('true','false'):abort(400)
    suppressed=request.args.get('suppressed','false')=='true'
    listing=ui_page('SELECT g.*,(SELECT count(*) FROM duplicate_members m WHERE m.group_id=g.id) AS member_count FROM duplicate_groups g WHERE suppressed=?',[int(suppressed)])
    return render_template('duplicate_groups.html',listing=listing,suppressed=suppressed)

@ui.get('/groups/<int:identifier>')
def group(identifier):
    with errors():item=t.group(identifier)
    members=ui_page('SELECT e.*,a.is_read,a.is_starred FROM duplicate_members m JOIN evidence e ON e.id=m.evidence_id LEFT JOIN articles a ON a.id=e.article_id WHERE m.group_id=?',[identifier],order='e.id DESC')
    return render_template('duplicate_group.html',item=item,members=members)

@ui.post('/groups/<int:identifier>/toggle')
def toggle(identifier):
    with errors():item=t.group(identifier);t.toggle_group(identifier,{'suppressed':not bool(item['suppressed'])})
    return redirect(url_for('triage.group',identifier=identifier))
