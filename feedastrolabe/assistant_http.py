"""Fixed Ollama endpoints only; no generation tools, redirects, proxy or POST retry."""
import json,os,re,stat,time
from pathlib import Path
from http.client import HTTPConnection
from flask import current_app
from .fetch import public_address,PinnedHTTP

class ModelError(ValueError):
 def __init__(self,code):self.code=code;super().__init__(code)


def token():
 file=current_app.config.get('OLLAMA_TOKEN_FILE') or os.environ.get('FEEDASTROLABE_OLLAMA_TOKEN_FILE')
 if not file:raise ModelError('cloud-credential-unconfigured')
 fd=None
 try:
  fd=os.open(file,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK);info=os.fstat(fd);mounted=Path(file).absolute()==Path('/run/secrets/feedastrolabe_ollama_token')
  if not stat.S_ISREG(info.st_mode) or info.st_size>4096 or (not mounted and (info.st_uid!=os.getuid() or stat.S_IMODE(info.st_mode)&0o077)):raise ModelError('credential-file-policy')
  raw=os.read(fd,4097).decode().strip()
  if not re.fullmatch(r'[A-Za-z0-9._-]{16,4096}',raw):raise ModelError('credential-file-policy')
  return raw
 except ModelError:raise
 except Exception:raise ModelError('credential-file-policy') from None
 finally:
  if fd is not None:os.close(fd)


def request(kind,path,body=None,deadline=None):
 if path not in ('/api/chat','/api/tags','/api/status','/api/version'):raise ModelError('model-endpoint-policy')
 deadline=deadline or time.monotonic()+90;conn=None
 try:
  headers={'Content-Type':'application/json','Accept':'application/json','Accept-Encoding':'identity','User-Agent':'FeedAstrolabe/0.13'}
  if kind=='cloud':
   if path!='/api/chat':raise ModelError('model-endpoint-policy')
   secret=token();host='ollama.com';address=public_address(host,443)
   conn=PinnedHTTP(host,443,address,True,min(10,max(0.1,deadline-time.monotonic())));headers['Authorization']='Bearer '+secret
  elif kind=='local':
   host=current_app.config.get('OLLAMA_LOCAL_HOST') or os.environ.get('FEEDASTROLABE_OLLAMA_LOCAL_HOST','127.0.0.1')
   if host not in ('127.0.0.1','ollama'):raise ModelError('local-endpoint-policy')
   conn=HTTPConnection(host,11434,timeout=min(10,max(0.1,deadline-time.monotonic())))
  else:raise ModelError('model-profile-policy')
  conn.request('POST' if body is not None else 'GET',path,body=body,headers=headers);response=conn.getresponse()
  if response.status!=200:raise ModelError('model-http-'+str(response.status))
  if response.getheader('Content-Encoding','identity')!='identity':raise ModelError('model-encoding')
  raw=bytearray()
  while True:
   remaining=deadline-time.monotonic()
   if remaining<=0:raise ModelError('model-timeout')
   if conn.sock:conn.sock.settimeout(min(10,remaining))
   part=response.read1(min(65536,1048577-len(raw)))
   if not part:break
   raw.extend(part)
   if len(raw)>1048576:raise ModelError('model-response-size')
  def pairs(items):
   result={}
   for key,value in items:
    if key in result:raise ValueError()
    result[key]=value
   return result
  return json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda _:(_ for _ in ()).throw(ValueError()))
 except ModelError:raise
 except Exception:raise ModelError('model-transport-or-format') from None
 finally:
  if conn:conn.close()


def generate(profile,wire):
 deadline=time.monotonic()+90;lineage={'adapter':'ollama-chat-v1','requested_model':profile['model'],'model_digest':None,'runtime_version':None}
 if profile['kind']=='local':
  status=request('local','/api/status',deadline=deadline)
  if not isinstance(status,dict) or status.get('cloud',{}).get('disabled') is not True:raise ModelError('local-cloud-not-disabled')
  data=request('local','/api/tags',deadline=deadline)
  models=data.get('models') if isinstance(data,dict) else None
  if not isinstance(models,list) or len(models)>1000:raise ModelError('local-model-metadata')
  selected=next((x for x in models if isinstance(x,dict) and x.get('name')==profile['model']),None)
  if not selected or selected.get('remote_host') or selected.get('remote_model') or selected.get('digest')!=profile['model_digest']:raise ModelError('local-model-digest-or-remote')
  lineage['model_digest']=selected['digest'];version=request('local','/api/version',deadline=deadline)
  if not isinstance(version,dict) or not isinstance(version.get('version'),str) or len(version['version'])>100:raise ModelError('local-runtime-version')
  lineage['runtime_version']=version['version']
 response=request(profile['kind'],'/api/chat',wire.encode(),deadline)
 if not isinstance(response,dict) or response.get('done') is not True or response.get('model')!=profile['model']:raise ModelError('model-response-shape')
 message=response.get('message')
 if not isinstance(message,dict) or message.get('role')!='assistant' or message.get('tool_calls') or response.get('tool_calls'):raise ModelError('model-tools-rejected')
 if profile['kind']=='local' and (response.get('remote_host') or response.get('remote_model')):raise ModelError('local-remote-response')
 content=message.get('content')
 if not isinstance(content,str) or len(content)>16000:raise ModelError('model-output-size')
 usage={key:response.get(key) for key in ('prompt_eval_count','eval_count')}
 if any(type(x) is not int or not 0<=x<=100000 for x in usage.values()):raise ModelError('model-usage-unknown')
 if usage['eval_count']>profile['max_output_tokens']:raise ModelError('model-output-budget')
 lineage['response_model']=response['model'];lineage['created_at']=response.get('created_at')
 return content,usage,lineage
