"""Exact input inspection and human result revisions, rendered as escaped text."""
from flask import Blueprint,request,render_template,redirect,url_for
from .research_ui import errors,identifier,ui_page
from . import assistant as a,research as r
from .db import get_db
ui=Blueprint('assistant',__name__,url_prefix='/assistant')

@ui.get('')
def index():
 workspace=request.args.get('workspace') or None
 with errors():
  if workspace:workspace=identifier(workspace);r.find('workspace',workspace)
 profiles=[dict(x) for x in get_db().execute('SELECT * FROM assistant_profiles ORDER BY id DESC')]
 jobs=ui_page('SELECT j.*,p.workspace_id,p.mode FROM assistant_jobs j JOIN assistant_previews p ON p.id=j.preview_id'+(' WHERE p.workspace_id=?' if workspace else ''),[workspace] if workspace else [],order='j.id DESC')
 return render_template('assistant.html',profiles=profiles,listing=jobs,workspace=workspace)

@ui.post('/profiles')
def profile():
 with errors():
  body={'name':request.form.get('name'),'kind':request.form.get('kind'),'model':request.form.get('model'),'model_digest':request.form.get('model_digest') or None,'enabled':request.form.get('enabled')=='on','max_output_tokens':identifier(request.form.get('max_output_tokens')),'daily_calls':identifier(request.form.get('daily_calls'))}
  if body['kind']=='cloud':body.update(input_rate=identifier(request.form.get('input_rate')),output_rate=identifier(request.form.get('output_rate')),price_date=request.form.get('price_date'))
  a.profile(body)
 return redirect(url_for('assistant.index'))

@ui.post('/profiles/<int:profile_id>/update')
def update_profile(profile_id):
 with errors():a.profile({'expected_revision':identifier(request.form.get('expected_revision')),'enabled':request.form.get('enabled')=='on'},profile_id)
 return redirect(url_for('assistant.index'))

@ui.post('/previews')
def preview():
 with errors():
  body={'profile_id':identifier(request.form.get('profile_id')),'mode':request.form.get('mode'),'question':request.form.get('question','')}
  for field in ('evidence_ids','quotation_ids'):
   if request.form.get(field):body[field]=[identifier(x.strip()) for x in request.form[field].split(',')]
  pid=a.preview(identifier(request.form.get('workspace_id')),body)
 return redirect(url_for('assistant.get_preview',preview_id=pid))

@ui.get('/previews/<int:preview_id>')
def get_preview(preview_id):
 with errors():item=a.find('assistant_previews',preview_id);profile=a.find('assistant_profiles',item['profile_id'])
 return render_template('assistant_preview.html',preview=a.decoded(item),profile=profile)

@ui.post('/previews/<int:preview_id>/jobs')
def enqueue(preview_id):
 with errors():jid=a.enqueue(preview_id,{'approved':request.form.get('approved')=='on','input_hash':request.form.get('input_hash')})
 return redirect(url_for('assistant.detail',job_id=jid))

@ui.get('/jobs/<int:job_id>')
def detail(job_id):
 with errors():item=a.detail(job_id)
 reviews=ui_page('SELECT * FROM assistant_review_versions WHERE job_id=?',[job_id])
 return render_template('assistant_job.html',item=item,reviews=reviews)

@ui.post('/jobs/<int:job_id>/reviews')
def review(job_id):
 with errors():
  revision=request.form.get('expected_revision','')
  if not revision.isdecimal():raise ValueError('レビュー版が不正です。')
  a.review(job_id,{'expected_revision':int(revision),'status':request.form.get('status'),'text':request.form.get('text')})
 return redirect(url_for('assistant.detail',job_id=job_id))
