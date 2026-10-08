from flask import Blueprint,abort,redirect,render_template,request,url_for,flash
from .db import get_db
from . import evidence as e,research as r
from .research_ui import errors,identifier,ui_page
from .evidence_api import download
from .attachments import upload

ui=Blueprint('evidence',__name__,url_prefix='/evidence')


@ui.get('')
def index():
    workspace=request.args.get('workspace','')
    clauses,params=[],[]
    if workspace:
        wid=identifier(workspace)
        with errors():r.find('workspace',wid)
        clauses.append('(EXISTS(SELECT 1 FROM workspace_evidence w WHERE w.evidence_id=e.id AND w.workspace_id=?) OR EXISTS(SELECT 1 FROM note_evidence n JOIN notes nn ON nn.id=n.note_id WHERE n.evidence_id=e.id AND nn.workspace_id=?) OR EXISTS(SELECT 1 FROM quotations q WHERE q.evidence_id=e.id AND q.workspace_id=?))');params.extend([wid]*3)
    if request.args.get('article'):
        aid=identifier(request.args['article']);clauses.append('e.article_id=?');params.append(aid)
    where=' WHERE '+' AND '.join(clauses) if clauses else ''
    listing=ui_page('SELECT e.*,b.size FROM evidence e JOIN evidence_blobs b ON b.hash=e.blob_hash'+where,params,order='e.id DESC')
    return render_template('evidence_list.html',listing=listing,workspace=workspace,settings=get_db().execute('SELECT * FROM evidence_settings').fetchone(),capture_errors=get_db().execute('SELECT * FROM evidence_capture_errors ORDER BY feed_id LIMIT 100').fetchall())


@ui.get('/<int:eid>')
def detail(eid):
    with errors():
        item=e.find(eid)
        if e.digest(item['text'].encode())!=item['text_hash']:abort(409)
    return render_template('evidence_detail.html',item=item,workspaces=r.options('workspace'),notes=get_db().execute('SELECT n.id,n.title,n.workspace_id FROM notes n JOIN workspaces w ON w.id=n.workspace_id WHERE n.archived=0 AND w.archived=0 ORDER BY n.id DESC LIMIT 100').fetchall(),pins=get_db().execute('SELECT w.id,w.title FROM workspaces w JOIN workspace_evidence p ON p.workspace_id=w.id WHERE p.evidence_id=? ORDER BY w.id LIMIT 100',(eid,)).fetchall(),quotations=ui_page('SELECT q.*,w.title AS workspace_title FROM quotations q JOIN workspaces w ON w.id=q.workspace_id WHERE q.evidence_id=?',[eid],order='q.id DESC'))


@ui.get('/<int:identifier>/download')
def download_ui(identifier):return download(identifier)


@ui.post('/articles/<int:aid>/capture')
def capture(aid):
    with errors():eid=e.article_capture(aid)
    return redirect(url_for('evidence.detail',eid=eid))


@ui.post('/<int:eid>/pin/<kind>')
def pin(eid,kind):
    if kind not in ('workspace','note') or request.form.get('operation','add') not in ('add','remove'):abort(400)
    with errors():e.pin(kind,identifier(request.form.get('target_id')),eid,request.form.get('operation')=='remove')
    return redirect(url_for('evidence.detail',eid=eid))


@ui.post('/workspaces/<int:wid>/attachments')
def attachment(wid):
    if set(request.files)!={'file'} or len(request.files.getlist('file'))!=1:abort(400)
    # Browser MIME for Markdown is often empty/text/plain; set only the known extension.
    file=request.files['file']
    if file.filename and file.filename.lower().endswith('.md') and file.mimetype in ('','application/octet-stream','text/plain'):
        from werkzeug.datastructures import FileStorage
        file=FileStorage(stream=file.stream,filename=file.filename,content_type='text/markdown')
    with errors():eid=upload(wid,file)
    return redirect(url_for('evidence.detail',eid=eid))


@ui.post('/<int:eid>/quote')
def quote(eid):
    with errors():
        e.quotation(identifier(request.form.get('workspace_id')),{'evidence_id':eid,'start':int(request.form.get('start','-1')),'end':int(request.form.get('end','-1')),'quote':request.form.get('quote',''),**({'note_id':identifier(request.form['note_id'])} if request.form.get('note_id') else {})})
    return redirect(url_for('evidence.detail',eid=eid))


@ui.post('/settings')
def settings():
    with errors():
        quota=int(request.form.get('quota_mib','0'));days=int(request.form.get('retention_days','0'))
        if not 10<=quota<=10240 or not 1<=days<=3650:raise ValueError('容量は10〜10240MiB、保存期間は1〜3650日で指定してください。')
        with e.storage_lock(),r.transaction() as db:db.execute('UPDATE evidence_settings SET quota_bytes=?,retention_days=?',(quota*1024*1024,days))
    flash('根拠の容量・保存期間を更新しました。','success')
    return redirect(url_for('evidence.index'))
