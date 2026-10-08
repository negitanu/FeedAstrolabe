"""Scoped explicit exports, notification approval and bounded management endpoints."""
from flask import Blueprint,request,Response,abort
from .keys import authenticate_api
from .research_api import errors,page
from .db import get_db
from . import reports as p,delivery as d,operations as o,research as r
from .preferences import preferences,save_preferences
from .opml import import_opml,export_opml,MAX_OPML
api=Blueprint('operations_api',__name__,url_prefix='/api/v1');api.before_request(authenticate_api)

@api.post('/workspaces/<int:identifier>/reports')
def report_create(identifier):
 with errors():rid=p.create(identifier,request.get_json())
 return report(rid),201

@api.get('/reports/<int:identifier>')
def report(identifier):
 with errors():return {'data':dict(p.find(identifier))}

@api.get('/reports/<int:identifier>/download')
def download(identifier):
 with errors():row=p.find(identifier)
 mime,extension=p.FORMATS[row['format']]
 return Response(row['payload'],content_type=mime+'; charset=utf-8',headers={'Content-Disposition':f'attachment; filename=report-{identifier}.{extension}'})

@api.get('/workspaces/<int:identifier>/reports')
def report_list(identifier):
 with errors():r.find('workspace',identifier)
 return page('SELECT id,workspace_id,format,payload_hash,include_nonpublic,created_at FROM reports WHERE workspace_id=?',[identifier])

@api.get('/delivery-profiles')
def profiles():return page('SELECT * FROM delivery_profiles')

@api.post('/delivery-profiles')
def profile_create():
 with errors():pid=d.profile(request.get_json())
 return {'data':dict(d.find('delivery_profiles',pid))},201

@api.patch('/delivery-profiles/<int:identifier>')
def profile_update(identifier):
 with errors():d.profile(request.get_json(),identifier)
 return {'data':dict(d.find('delivery_profiles',identifier))}

@api.post('/reports/<int:identifier>/delivery-previews')
def preview_create(identifier):
 with errors():pid=d.preview(identifier,request.get_json())
 return preview(pid),201

@api.get('/delivery-previews/<int:identifier>')
def preview(identifier):
 with errors():return {'data':dict(d.find('delivery_previews',identifier))}

@api.post('/delivery-previews/<int:identifier>/jobs')
def job_create(identifier):
 with errors():jid=d.enqueue(identifier,request.get_json())
 return job(jid),202

@api.get('/delivery-jobs')
def jobs():return page('SELECT * FROM delivery_jobs')

@api.get('/delivery-jobs/<int:identifier>')
def job(identifier):
 with errors():row=dict(d.find('delivery_jobs',identifier))
 row['attempts_history']=[dict(x) for x in get_db().execute('SELECT * FROM delivery_attempts WHERE job_id=? ORDER BY attempt',(identifier,))]
 return {'data':row}

@api.get('/operations')
def health():return {'data':o.health()}

@api.get('/operations/worker-runs')
def runs():return page('SELECT * FROM worker_runs')

@api.get('/operations/config')
def configuration():return {'data':dict(get_db().execute('SELECT * FROM operations_config').fetchone())}

@api.patch('/operations/config')
def configure():
 with errors():o.config(request.get_json())
 return configuration()

@api.get('/operations/backups')
def backups():return page('SELECT * FROM backup_jobs')

@api.post('/operations/backups')
def enqueue_backup():
 if request.get_data():abort(400,description='Backup requests must have an empty body')
 with errors():jid=o.enqueue()
 return {'data':dict(get_db().execute('SELECT * FROM backup_jobs WHERE id=?',(jid,)).fetchone())},202

@api.get('/settings')
def settings_get():return {'data':preferences()}

@api.patch('/settings')
def settings_patch():
 with errors():
  fields={'poll_interval','polling_enabled','page_size','default_view','api_rate_limit'};v=r.fields(request.get_json(),fields);old=preferences()
  for key in ('poll_interval','page_size','api_rate_limit'):
   if key in v and type(v[key]) is not int:raise ValueError(key+' は整数です。')
  if 'polling_enabled' in v and type(v['polling_enabled']) is not bool:raise ValueError('polling_enabled は真偽値です。')
  old.update(v);old['polling_enabled']='1' if old['polling_enabled'] else '0';save_preferences(old)
 return settings_get()

@api.post('/articles/bulk-state')
def bulk():
 with errors():
  v=r.fields(request.get_json(),{'ids','is_read','is_starred'});ids=v.get('ids')
  if not isinstance(ids,list) or not 1<=len(ids)<=100 or any(type(x) is not int or not 1<=x<=2**63-1 for x in ids) or len(set(ids))!=len(ids):raise ValueError('記事 ID は重複なし1〜100件です。')
  columns={k:int(v[k]) for k in ('is_read','is_starred') if k in v and type(v[k]) is bool}
  if not columns or len(columns)!=len(v)-1:raise ValueError('既読・スターは真偽値です。')
  marks=','.join('?' for _ in ids)
  with r.transaction() as db:
   if db.execute('SELECT count(*) FROM articles WHERE id IN('+marks+')',ids).fetchone()[0]!=len(ids):raise r.ResearchMissing('記事が見つかりません。変更しませんでした。')
   db.execute('UPDATE articles SET '+','.join(k+'=?' for k in columns)+' WHERE id IN('+marks+')',list(columns.values())+ids)
 return {'data':{'ids':ids,**{k:bool(x) for k,x in columns.items()}}}

@api.get('/opml')
def opml_export():return Response(export_opml(),content_type='application/xml; charset=utf-8',headers={'Content-Disposition':'attachment; filename=subscriptions.opml'})

@api.post('/opml')
def opml_import():
 if request.content_length and request.content_length>MAX_OPML:abort(413)
 if request.mimetype not in ('application/xml','text/xml','text/x-opml'):abort(415,description='OPML XML content type required')
 with errors():added,skipped=import_opml(request.get_data())
 return {'data':{'added':added,'skipped':skipped,'contract':'atomic insertion-only; duplicate URLs skipped; no inline fetch'}}
