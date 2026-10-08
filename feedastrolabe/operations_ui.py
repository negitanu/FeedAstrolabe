"""Japanese operations, local export downloads and exact outbound approval."""
from flask import Blueprint,request,render_template,redirect,url_for,Response
from .research_ui import errors,identifier
from .db import get_db
from . import reports as p,delivery as d,operations as o
ui=Blueprint('operations',__name__,url_prefix='/operations')

@ui.get('')
def index():
 db=get_db();return render_template('operations.html',health=o.health(),config=dict(db.execute('SELECT * FROM operations_config').fetchone()),profiles=db.execute('SELECT * FROM delivery_profiles ORDER BY id DESC').fetchall(),reports=db.execute('SELECT id,workspace_id,format,payload_hash,created_at FROM reports ORDER BY id DESC LIMIT 100').fetchall(),jobs=db.execute('SELECT * FROM delivery_jobs ORDER BY id DESC LIMIT 100').fetchall(),backups=db.execute('SELECT * FROM backup_jobs ORDER BY id DESC LIMIT 100').fetchall(),runs=db.execute('SELECT * FROM worker_runs ORDER BY id DESC LIMIT 100').fetchall())

@ui.post('/reports')
def create_report():
 with errors():
  body={'format':request.form.get('format'),'include_nonpublic':request.form.get('include_nonpublic')=='on'}
  if request.form.get('evidence_ids'):body['evidence_ids']=[identifier(x.strip()) for x in request.form['evidence_ids'].split(',')]
  rid=p.create(identifier(request.form.get('workspace_id')),body)
 return redirect(url_for('operations.report',identifier=rid))

@ui.get('/reports/<int:identifier>')
def report(identifier):
 with errors():row=p.find(identifier)
 return render_template('report.html',report=row)

@ui.get('/reports/<int:identifier>/download')
def download(identifier):
 with errors():row=p.find(identifier)
 mime,ext=p.FORMATS[row['format']];return Response(row['payload'],content_type=mime+'; charset=utf-8',headers={'Content-Disposition':f'attachment; filename=report-{identifier}.{ext}'})

@ui.post('/profiles')
def profile():
 with errors():d.profile({'name':request.form.get('name'),'kind':request.form.get('kind'),'destination':request.form.get('destination')})
 return redirect(url_for('operations.index'))

@ui.post('/profiles/<int:identifier>')
def profile_update(identifier):
 with errors():d.profile({'enabled':request.form.get('enabled')=='on','expected_revision':identifier_fn(request.form.get('expected_revision'))},identifier)
 return redirect(url_for('operations.index'))
identifier_fn=identifier

@ui.post('/reports/<int:identifier>/preview')
def preview_create(identifier):
 with errors():pid=d.preview(identifier,{'profile_id':identifier_fn(request.form.get('profile_id'))})
 return redirect(url_for('operations.preview',identifier=pid))

@ui.get('/previews/<int:identifier>')
def preview(identifier):
 with errors():row=d.find('delivery_previews',identifier);profile=d.find('delivery_profiles',row['profile_id'])
 return render_template('delivery_preview.html',preview=row,profile=profile)

@ui.post('/previews/<int:identifier>/approve')
def approve(identifier):
 with errors():d.enqueue(identifier,{'approved':request.form.get('approved')=='on','payload_hash':request.form.get('payload_hash')})
 return redirect(url_for('operations.index'))

@ui.post('/backups')
def backup():
 with errors():o.enqueue()
 return redirect(url_for('operations.index'))

@ui.post('/config')
def configure():
 with errors():o.config({'expected_revision':identifier(request.form.get('expected_revision')),'backup_enabled':request.form.get('backup_enabled')=='on','interval_seconds':identifier(request.form.get('interval_seconds')),'generations':identifier(request.form.get('generations')),'quota_bytes':identifier(request.form.get('quota_bytes'))})
 return redirect(url_for('operations.index'))
