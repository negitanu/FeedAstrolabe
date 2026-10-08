"""Explicit immutable outputs. Source mentions are not verified indicators."""
import csv,io,json,uuid,ipaddress
from .db import get_db
from . import research as r,evidence as e,assistant as a

FORMATS={'markdown':('text/markdown','md'),'manifest':('application/json','json'),'json':('application/json','json'),'csv':('text/csv','csv'),'stix':('application/stix+json','json')}

def encode(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'))

def find(identifier):
 if type(identifier) is not int or not 1<=identifier<=2**63-1:raise ValueError('ID は正の整数です。')
 row=get_db().execute('SELECT * FROM reports WHERE id=?',(identifier,)).fetchone()
 if not row:raise r.ResearchMissing('レポートが見つかりません。')
 return row

def public(wid,eid,db):
 try:a.remote_scope(wid,eid,db);return True
 except ValueError:return False

def cell(value):
 text=str(value)
 if text.lstrip().startswith(('=','+','-','@')) or text.startswith(('\t','\r','\n')):return "'"+text
 return text

def stix(records,manifest):
 objects=[];timestamp=manifest['created_at'].replace(' ','T')+'Z'
 for row in records:
  for ent in row['entities']:
   kind=ent['kind'];value=ent['canonical'];props=None
   if kind=='domain':typ='domain-name';props={'value':value}
   elif kind=='ip':typ='ipv4-addr' if ipaddress.ip_address(value).version==4 else 'ipv6-addr';props={'value':value}
   elif kind=='asn':typ='autonomous-system';props={'number':int(value.removeprefix('AS'))}
   elif kind=='cve':typ='vulnerability';props={'name':value,'created':timestamp,'modified':timestamp,'external_references':[{'source_name':'cve','external_id':value}]}
   if props is None:continue
   # SCO UUIDv4 is permitted; avoid claiming UUIDv5 canonical contributing-property calculation.
   obj={'type':typ,'spec_version':'2.1','id':typ+'--'+str(uuid.uuid4()),**props};objects.append(obj)
 if objects:
  objects.append({'type':'note','spec_version':'2.1','id':'note--'+str(uuid.uuid4()),'created':timestamp,'modified':timestamp,'content':'Source mentions only; not independently verified indicators. Citation manifest: '+encode(manifest),'object_refs':[obj['id'] for obj in objects]})
 return {'type':'bundle','id':'bundle--'+str(uuid.uuid4()),'objects':objects}

def create(wid,body):
 v=r.fields(body,{'format','evidence_ids','include_nonpublic'});fmt=v.get('format','markdown')
 if not isinstance(fmt,str) or fmt not in FORMATS:raise ValueError('出力形式が不正です。')
 include=v.get('include_nonpublic',False)
 if type(include) is not bool:raise ValueError('公開区分の選択は真偽値です。')
 ids=v.get('evidence_ids')
 if ids is not None and (not isinstance(ids,list) or not 1<=len(ids)<=100 or any(type(i) is not int or not 1<=i<=2**63-1 for i in ids) or len(set(ids))!=len(ids)):raise ValueError('資料 ID は重複なし1〜100件です。')
 with e.storage_lock(),r.transaction() as db:
  workspace=r.find('workspace',wid,db)
  if db.execute('SELECT count(*) FROM reports').fetchone()[0]>=10000:raise ValueError('レポート保存上限です。')
  scoped=[row[0] for row in db.execute('SELECT evidence_id FROM workspace_evidence WHERE workspace_id=? ORDER BY evidence_id DESC LIMIT 101',(wid,))]
  if ids is None:
   if len(scoped)>100:raise ValueError('100件以内を明示選択してください。')
   ids=scoped
  records=[];anchors=[];excluded=0
  for eid in ids:
   if not db.execute('SELECT 1 FROM workspace_evidence WHERE workspace_id=? AND evidence_id=?',(wid,eid)).fetchone():raise ValueError('別案件の資料は選択できません。')
   if not include and not public(wid,eid,db):excluded+=1;continue
   item=dict(e.find(eid,db));e.read_blob(item['blob_hash'],item['size'])
   if e.digest(item['text'].encode())!=item['text_hash']:raise ValueError('根拠hashが不正です。')
   if len(item['text'])>20000:raise ValueError('資料本文は20000文字以内を選択してください。')
   anchors.append({k:item[k] for k in ('id','text_hash','blob_hash','captured_at','observed_at','published_at','source_url','method')})
   entities=[dict(x) for x in db.execute('SELECT DISTINCT n.id,n.kind,n.canonical,n.display_name,m.status FROM entities n JOIN entity_mentions m ON m.entity_id=n.id WHERE m.evidence_id=? AND m.status!=\'rejected\' ORDER BY n.id LIMIT 101',(eid,))]
   if len(entities)>100:raise ValueError('対象件数の上限です。')
   observations=[{'kind':'network',**dict(x)} for x in db.execute('SELECT id,source_url,source_version,observed_at,normalized FROM network_observations WHERE evidence_id=? ORDER BY id LIMIT 101',(eid,))]
   observations += [{'kind':'security',**dict(x)} for x in db.execute('SELECT id,observed_at,payload AS normalized FROM security_observations WHERE evidence_id=? ORDER BY id LIMIT 101',(eid,))]
   if len(observations)>100:raise ValueError('観測件数の上限です。')
   records.append({'evidence_id':eid,'title':item['title'],'text':item['text'],'entities':entities,'observations':observations})
  manifest={'version':1,'workspace_id':wid,'classification':workspace['classification'],'include_nonpublic':include,'created_at':r.now(),'excluded_count':excluded,'sources':anchors,'limitations':'Source claims/mentions; no truth verification, complete historical coverage or TAXII.'}
  # Nonpublic workspace title/purpose never enters a default public export.
  title=workspace['title'] if include or workspace['classification']=='public' else '公開資料なし'
  a.clean(encode(manifest))
  data={'title':title,'manifest':manifest,'records':records}
  if fmt=='markdown':payload='# '+title+'\n\n'+'\n\n'.join('## 資料 #'+str(x['evidence_id'])+' '+x['title']+'\n\n'+x['text'] for x in records)+'\n\n## 引用マニフェスト\n\n'+encode(manifest)+'\n'
  elif fmt=='manifest':payload=encode(manifest)
  elif fmt=='json':payload=encode(data)
  elif fmt=='stix':payload=encode(stix(records,manifest))
  else:
   stream=io.StringIO(newline='');writer=csv.writer(stream);writer.writerow(['record_kind','evidence_id','title','value','source_id','observed_at','text_hash','blob_hash','captured_at'])
   for rec in records:
    citation=next(x for x in anchors if x['id']==rec['evidence_id']);hashes=[citation[k] for k in ('text_hash','blob_hash','captured_at')]
    writer.writerow([cell(x) for x in ['evidence',rec['evidence_id'],rec['title'],rec['text'],rec['evidence_id'],'']+hashes])
    for ent in rec['entities']:writer.writerow([cell(x) for x in ['entity',rec['evidence_id'],ent['kind'],ent['canonical'],ent['id'],ent['status']]+hashes])
    for obs in rec['observations']:writer.writerow([cell(x) for x in ['observation',rec['evidence_id'],obs['kind'],obs['normalized'],obs['id'],obs['observed_at']]+hashes])
   payload=stream.getvalue()
  a.clean(payload)
  if len(payload.encode())>4*1024*1024:raise ValueError('出力は4MiB以内です。')
  rid=db.execute('INSERT INTO reports(workspace_id,format,payload,payload_hash,manifest,include_nonpublic,created_at) VALUES(?,?,?,?,?,?,?)',(wid,fmt,payload,e.digest(payload.encode()),encode(manifest),int(include),r.now())).lastrowid
  db.executemany('INSERT INTO report_sources(report_id,evidence_id) VALUES(?,?)',[(rid,x['id']) for x in anchors]);return rid

def outbound(report,db):
 if report['include_nonpublic']:raise ValueError('非公開選択のレポートは外部送信できません。')
 a.clean(report['payload']);a.clean(report['manifest'])
 if e.digest(report['payload'].encode())!=report['payload_hash']:raise ValueError('レポートhashが不正です。')
 r.find('workspace',report['workspace_id'],db)
 if r.find('workspace',report['workspace_id'],db)['classification']!='public':raise ValueError('外部送信は公開案件だけです。')
 for src in json.loads(report['manifest'])['sources']:
  a.remote_scope(report['workspace_id'],src['id'],db);item=e.find(src['id'],db)
  if item['text_hash']!=src['text_hash'] or item['blob_hash']!=src['blob_hash']:raise ValueError('根拠hashが不正です。')
  e.read_blob(item['blob_hash'],item['size'])
