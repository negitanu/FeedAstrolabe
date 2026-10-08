"""Owner-only transport configuration, TLS public DNS pinning and metadata-only errors."""
import json,os,stat,re,time,hmac,hashlib,smtplib,socket,ssl
from email.message import EmailMessage
from urllib.parse import urlsplit,urlunsplit
from flask import current_app
from .fetch import public_address,PinnedHTTP,normalize_url

class DeliveryError(ValueError):
 def __init__(self,code,retry=False):self.code=code;self.retry=retry;super().__init__(code)

def endpoint(value):
 url=normalize_url(value);p=urlsplit(value)
 if p.scheme!='https' or p.port not in (None,443) or p.query or p.fragment:raise ValueError('Webhook は query・fragment なし HTTPS443 です。')
 from .assistant import clean
 clean(url)
 path=urlsplit(url).path
 if not re.fullmatch(r'[A-Za-z0-9/_.-]{1,200}',path) or any(len(segment)>23 for segment in path.split('/')) or p.hostname.lower() in ('hooks.slack.com','discord.com','discordapp.com'):raise ValueError('認証tokenを含むWebhook URLは使えません。短い固定パスと署名検証の受信先を指定してください。')
 public_address(urlsplit(url).hostname,443)
 return url

def recipient(value):
 if not isinstance(value,str) or len(value)>254 or not re.fullmatch(r'[A-Za-z0-9.!#$%&\x27*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?',value) or '..' in value:raise ValueError('宛先は単一のメールアドレスです。')
 return value

def configuration():
 path=current_app.config.get('DELIVERY_CONFIG_FILE') or os.environ.get('FEEDASTROLABE_DELIVERY_CONFIG_FILE');fd=None
 if not path:raise DeliveryError('delivery-credential-unconfigured')
 try:
  fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK);info=os.fstat(fd)
  if not stat.S_ISREG(info.st_mode) or info.st_size>16384 or info.st_uid!=os.getuid() or stat.S_IMODE(info.st_mode)&0o077:raise DeliveryError('delivery-credential-policy')
  def pairs(items):
   result={}
   for key,value in items:
    if key in result:raise DeliveryError('delivery-credential-policy')
    result[key]=value
   return result
  data=json.loads(os.read(fd,16385),object_pairs_hook=pairs);return data
 except DeliveryError:raise
 except Exception:raise DeliveryError('delivery-credential-policy') from None
 finally:
  if fd is not None:os.close(fd)

def deliver(profile,wire,key):
 config=configuration();conn=None;deadline=time.monotonic()+30
 try:
  if not isinstance(config,dict):raise DeliveryError('delivery-credential-policy')
  allowed=config.get('destinations',[])
  if not isinstance(allowed,list) or profile['destination'] not in allowed:raise DeliveryError('delivery-destination-not-allowed')
  if profile['kind']=='webhook':
   url=endpoint(profile['destination']);p=urlsplit(url);secret=config.get('webhook_secret')
   if not isinstance(secret,str) or not 32<=len(secret)<=4096:raise DeliveryError('delivery-credential-policy')
   raw=wire.encode();signature=hmac.new(secret.encode(),raw,hashlib.sha256).hexdigest()
   conn=PinnedHTTP(p.hostname,443,public_address(p.hostname,443),True,10)
   conn.request('POST',urlunsplit(('','',p.path or '/','','')),body=raw,headers={'Content-Type':'application/json','Accept':'application/json','User-Agent':'FeedAstrolabe/0.14','Idempotency-Key':key,'X-FeedAstrolabe-Signature':'sha256='+signature,'Accept-Encoding':'identity'})
   res=conn.getresponse()
   if time.monotonic()>deadline:raise DeliveryError('delivery-ambiguous-timeout')
   if res.status in (429,503):raise DeliveryError('delivery-http-'+str(res.status),True)
   if not 200<=res.status<300:raise DeliveryError('delivery-http-'+str(res.status))
   # Acknowledgement only; never store/parse response data or follow redirects.
   return
  if profile['kind']!='email':raise DeliveryError('delivery-profile-policy')
  smtp=config.get('smtp',{});host=smtp.get('host');sender=recipient(smtp.get('sender'));destination=recipient(profile['destination'])
  if not isinstance(host,str) or not re.fullmatch(r'[A-Za-z0-9.-]{1,253}',host) or smtp.get('port',465)!=465:raise DeliveryError('delivery-smtp-policy')
  address=public_address(host,465)
  class PinnedSMTP(smtplib.SMTP_SSL):
   def getreply(self):
    if self.file is None:self.file=self.sock.makefile('rb')
    response=[];total=0
    for _ in range(64):
     remaining=deadline-time.monotonic()
     if remaining<=0:raise DeliveryError('delivery-ambiguous-timeout')
     self.sock.settimeout(min(10,remaining));line=self.file.readline(8193)
     total+=len(line)
     if not line or len(line)>8192 or total>65536:raise DeliveryError('delivery-smtp-response-bound')
     response.append(line[4:].strip())
     try:code=int(line[:3])
     except ValueError:raise DeliveryError('delivery-smtp-format') from None
     if line[3:4]!=b'-':return code,b'\n'.join(response)
    raise DeliveryError('delivery-smtp-response-bound')
   def _get_socket(self,host,port,timeout):
    family,kind,proto,_,target=address;sock=socket.socket(family,kind,proto)
    try:sock.settimeout(timeout);sock.connect(target);return self.context.wrap_socket(sock,server_hostname=host)
    except BaseException:sock.close();raise
  conn=PinnedSMTP(host,465,timeout=10,context=ssl.create_default_context())
  username=smtp.get('username');password=smtp.get('password')
  if not isinstance(username,str) or not isinstance(password,str) or not username or not password:raise DeliveryError('delivery-credential-policy')
  conn.login(username,password)
  message=EmailMessage();message['From']=sender;message['To']=destination;message['Subject']='FeedAstrolabe sourced report';message['Message-ID']='<'+key+'@feedastrolabe.local>';message.set_content(wire)
  if conn.send_message(message,from_addr=sender,to_addrs=[destination]):raise DeliveryError('delivery-smtp-refused')
 except DeliveryError:raise
 except Exception:raise DeliveryError('delivery-ambiguous-transport') from None
 finally:
  if conn:
   try:conn.close()
   except Exception:pass
