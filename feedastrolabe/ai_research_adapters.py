"""Registered public metadata only; bounded literal queries and no artifact downloads."""
import re
from urllib.parse import urlencode,urlsplit
from datetime import datetime
from defusedxml.ElementTree import fromstring
from .entities import normalize
PROVIDERS={'arxiv':{'name':'arXiv Atom metadata','license':'https://info.arxiv.org/help/api/tou.html'},'github-releases':{'name':'GitHub public releases','license':'https://docs.github.com/en/rest/releases/releases'}}
CATEGORIES={'cs.AI','cs.CL','cs.LG','cs.CV','stat.ML'}
ID=re.compile(r'(?:\d{4}\.\d{4,5}|[a-z][a-z.-]{0,30}/\d{7})(?:v[1-9]\d{0,3})?')
ATOM='{http://www.w3.org/2005/Atom}';OS='{http://a9.com/-/spec/opensearch/1.1/}';AX='{http://arxiv.org/schemas/atom}'

def contract(provider,value):
 if not isinstance(value,str) or len(value)>400:raise ValueError('research-input')
 try:target,term,page=value.split('|');page=int(page)
 except (ValueError,TypeError):raise ValueError('research-input') from None
 if not 0<=page<=19 or str(page)!=value.rsplit('|',1)[1]:raise ValueError('research-page')
 if provider=='arxiv':
  if target.startswith('id:') and ID.fullmatch(target[3:]):
   if term or page:raise ValueError('id-query-page')
  elif target.startswith('cat:') and target[4:] in CATEGORIES:
   if len(term)>80 or not all(x.isalnum() or x in ' -_' for x in term):raise ValueError('literal-title-query')
  else:raise ValueError('arxiv-query')
 elif provider=='github-releases':
  if term or normalize('repository','https://github.com/'+target)!='github.com/'+target:raise ValueError('repository-query')
 else:raise ValueError('provider-policy')
 return {'target':target,'term':term,'page':page}

def endpoint(provider,value):
 q=contract(provider,value)
 if provider=='github-releases':return 'https://api.github.com/repos/'+q['target']+'/releases?'+urlencode({'per_page':50,'page':q['page']+1})
 params={'max_results':50,'start':q['page']*50,'sortBy':'lastUpdatedDate','sortOrder':'descending'}
 if q['target'].startswith('id:'):params['id_list']=q['target'][3:]
 else:params['search_query']=q['target']+(' AND ti:"'+q['term']+'"' if q['term'] else '')
 return 'https://export.arxiv.org/api/query?'+urlencode(params)

def atom(raw):
 root=fromstring(raw,forbid_dtd=True,forbid_entities=True,forbid_external=True)
 if root.tag!=ATOM+'feed' or sum(1 for _ in root.iter())>10000:raise ValueError('atom-shape')
 entries=root.findall(ATOM+'entry')
 if len(entries)>50:raise ValueError('atom-entries')
 def txt(node,tag,maximum,required=False):
  value=node.findtext(tag) or ''
  if len(value)>maximum or (required and not value):raise ValueError('atom-field')
  return value
 records=[]
 for node in entries:
  uri=txt(node,ATOM+'id',300,True);p=urlsplit(uri)
  if p.scheme not in ('http','https') or p.netloc!='arxiv.org' or not p.path.startswith('/abs/') or p.query or p.fragment:raise ValueError('paper-id')
  identifier=p.path[5:]
  if not ID.fullmatch(identifier) or not re.search(r'v[1-9]\d*$',identifier):raise ValueError('versioned-paper-id')
  authors=node.findall(ATOM+'author');categories=node.findall(ATOM+'category')
  if len(authors)>100 or len(categories)>20:raise ValueError('paper-array')
  records.append({'record_id':identifier,'version':identifier.rsplit('v',1)[1],'url':'https://arxiv.org/abs/'+identifier,'title':txt(node,ATOM+'title',2000,True),'abstract':txt(node,ATOM+'summary',20000,True),'published_at':txt(node,ATOM+'published',50,True),'updated_at':txt(node,ATOM+'updated',50,True),'authors':[txt(a,ATOM+'name',300,True) for a in authors],'categories':[x.get('term','') for x in categories],'doi':txt(node,AX+'doi',300) or None,'journal_ref':txt(node,AX+'journal_ref',1000) or None,'paper_license':None,'metadata_license':'CC0 1.0','coverage':'returned metadata; only observed revisions'})
 def integer(tag,default):
  value=int(txt(root,OS+tag,20) or default)
  if not 0<=value<=10**9:raise ValueError('atom-pagination')
  return value
 return {'records':records,'total':integer('totalResults',len(records)),'start':integer('startIndex',0)}

def date(value):
 if not isinstance(value,str) or len(value)>50:raise ValueError('source-date')
 dt=datetime.fromisoformat(value.replace('Z','+00:00'))
 if dt.tzinfo is None:raise ValueError('source-timezone')
 return value

def project(provider,value,payload):
 q=contract(provider,value);records=[]
 def text(value,maxlen=2000):
  if not isinstance(value,str) or len(value)>maxlen:raise ValueError('source-field')
  return value
 if provider=='arxiv':
  if not isinstance(payload,dict) or set(payload)!={'records','total','start'} or payload['start']!=q['page']*50 or type(payload['total']) is not int or not 0<=payload['total']<=10**9:raise ValueError('paper-page')
  records=payload['records']
  if not isinstance(records,list) or len(records)>50:raise ValueError('paper-records')
  for row in records:
   if not isinstance(row,dict) or not ID.fullmatch(row.get('record_id','')) or not re.search(r'v[1-9]\d*$',row['record_id']):raise ValueError('paper-record')
   if q['target'].startswith('id:'):
    wanted=q['target'][3:];base=re.sub(r'v\d+$','',wanted)
    if re.sub(r'v\d+$','',row['record_id'])!=base or (re.search(r'v[1-9]\d*$',wanted) and wanted!=row['record_id']):raise ValueError('paper-scope')
   elif q['target'][4:] not in row.get('categories',[]):raise ValueError('paper-category')
   if set(row)!={'record_id','version','url','title','abstract','published_at','updated_at','authors','categories','doi','journal_ref','paper_license','metadata_license','coverage'}:raise ValueError('paper-fields')
   if row['url']!='https://arxiv.org/abs/'+row['record_id'] or row['version']!=row['record_id'].rsplit('v',1)[1] or row['paper_license'] is not None or row['metadata_license']!='CC0 1.0':raise ValueError('paper-fields')
   for field,cap in [('authors',100),('categories',20)]:
    if not isinstance(row[field],list) or len(row[field])>cap:raise ValueError('paper-array')
    for item in row[field]:text(item,300)
   for field,cap in [('doi',300),('journal_ref',1000)]:
    if row[field] is not None:text(row[field],cap)
   text(row['coverage'],200);text(row['title']);text(row['abstract'],20000);date(row['published_at']);date(row['updated_at'])
  more=q['target'].startswith('cat:') and payload['start']+len(records)<payload['total']
 else:
  if not isinstance(payload,list) or len(payload)>50:raise ValueError('release-page')
  for row in payload:
   if not isinstance(row,dict) or type(row.get('id')) is not int or row['id']<1 or type(row.get('draft')) is not bool or type(row.get('prerelease')) is not bool:raise ValueError('release-shape')
   if row['draft']:raise ValueError('public-draft')
   url=text(row.get('html_url'),2048);p=urlsplit(url)
   if p.scheme!='https' or p.netloc!='github.com' or not p.path.startswith('/'+q['target']+'/releases/') or p.query or p.fragment:raise ValueError('release-scope')
   records.append({'record_id':str(row['id']),'version':text(row.get('tag_name'),300),'url':url,'title':text(row.get('name') or row['tag_name']),'body':text(row.get('body') or '',30000),'published_at':date(row.get('published_at')),'created_at':date(row.get('created_at')),'prerelease':row['prerelease'],'immutable_at_source':row.get('immutable') is True,'code_license':None,'coverage':'public release metadata; no tags-only releases or assets fetched'})
  more=len(records)==50
 return {'records':records,'more':more,'truncated':more and q['page']==19,'page':q['page'],'coverage':'bounded public metadata; pagination may shift'}

def validate(provider,value,payload):
 project(provider,value,payload)
 return 'Atom 1.0 / arXiv metadata' if provider=='arxiv' else 'GitHub REST 2026-03-10'
