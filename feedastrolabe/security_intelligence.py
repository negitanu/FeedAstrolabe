"""Local watched-product review, immutable public record evidence and cards."""
import json
from .db import get_db
from . import research as r,evidence as e,entities as n,triage as t,connectors as c
from .security_adapters import PROVIDERS,projection,link


def cve_entity(identifier,db=None):
    item=n.find(identifier,db)
    if item['kind']!='cve':raise ValueError('CVE対象を選んでください。')
    return item


def watch(identifier,db=None):
    t.positive_id(identifier);row=(db or get_db()).execute('SELECT * FROM security_watches WHERE id=?',(identifier,)).fetchone()
    if row is None:raise r.ResearchMissing('脆弱性ウォッチが見つかりません。')
    return row


def save_watch(workspace_id,body,identifier=None):
    fields={'entity_id','product','version','outbound_public','enabled'}
    values=r.fields(body,fields|({'expected_revision'} if identifier else set()))
    if identifier:t.positive_id(values.get('expected_revision'))
    with r.transaction() as db:
        r.editable(workspace_id,db);old=watch(identifier,db) if identifier else None
        if old and (old['workspace_id']!=workspace_id or values['expected_revision']!=old['revision']):raise r.ResearchConflict('ウォッチの版が更新されています。')
        def val(key,default=None):return values.get(key,old[key] if old else default)
        eid=val('entity_id');cve_entity(eid,db)
        product=r.text(val('product',''),'product',300);version=r.text(val('version',''),'version',200)
        outbound=val('outbound_public',False);enabled=val('enabled',True)
        if old:
            if 'outbound_public' not in values:outbound=bool(outbound)
            if 'enabled' not in values:enabled=bool(enabled)
        if type(outbound) is not bool or type(enabled) is not bool:raise ValueError('outbound_public/enabled must be boolean')
        duplicate=db.execute('SELECT id FROM security_watches WHERE workspace_id=? AND entity_id=? AND product=? AND version=?',(workspace_id,eid,product,version)).fetchone()
        if duplicate and duplicate['id']!=identifier:raise r.ResearchConflict('同じウォッチがあります。')
        if identifier:
            db.execute('UPDATE security_watches SET entity_id=?,product=?,version=?,outbound_public=?,enabled=?,revision=revision+1,updated_at=? WHERE id=?',(eid,product,version,outbound,enabled,r.now(),identifier))
        else:
            if db.execute('SELECT count(*) FROM security_watches WHERE workspace_id=?',(workspace_id,)).fetchone()[0]>=100:raise ValueError('案件のウォッチは100件までです。')
            identifier=db.execute('INSERT INTO security_watches(workspace_id,entity_id,product,version,outbound_public,enabled,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)',(workspace_id,eid,product,version,outbound,enabled,r.now(),r.now())).lastrowid
        return identifier


def quote(workspace_id,qid,db):
    t.positive_id(qid);row=db.execute('SELECT * FROM quotations WHERE id=?',(qid,)).fetchone()
    if row is None:raise r.ResearchMissing('引用が見つかりません。')
    if row['workspace_id']!=workspace_id:raise ValueError('同じ案件の引用が必要です。')
    item=e.find(row['evidence_id'],db)
    if row['text_hash']!=item['text_hash'] or item['text'][row['start']:row['end']]!=row['quote'] or e.digest(item['text'].encode())!=item['text_hash']:raise ValueError('固定引用が不正です。')
    e.read_blob(item['blob_hash'],item['size']);return row


def review(identifier,body):
    values=r.fields(body,{'expected_revision','status','quotation_id','reason','author'});t.positive_id(values.get('expected_revision'))
    with e.storage_lock(),r.transaction() as db:
        item=watch(identifier,db);r.editable(item['workspace_id'],db)
        if values['expected_revision']!=item['revision']:raise r.ResearchConflict('ウォッチの版が更新されています。')
        status=values.get('status')
        if status not in ('confirmed','possible','unknown'):raise ValueError('適用性の状態が不正です。')
        qid=values.get('quotation_id')
        if status=='confirmed' and qid is None:raise ValueError('確認済みには同じ案件の固定引用が必要です。')
        if qid is not None:quote(item['workspace_id'],qid,db)
        reason=r.text(values.get('reason'),'reason',2000,True,True);author=r.text(values.get('author','local-user'),'author',100,True)
        revision=item['revision']+1
        db.execute('INSERT INTO security_reviews(watch_id,revision,status,quotation_id,reason,author,created_at) VALUES(?,?,?,?,?,?,?)',(identifier,revision,status,qid,reason,author,r.now()))
        db.execute('UPDATE security_watches SET revision=?,updated_at=? WHERE id=?',(revision,r.now(),identifier))


def reference(workspace_id,body):
    values=r.fields(body,{'entity_id','url','kind','quotation_id','author','reviewed'})
    with e.storage_lock(),r.transaction() as db:
        r.editable(workspace_id,db);cve_entity(values.get('entity_id'),db);quote(workspace_id,values.get('quotation_id'),db)
        url=link(values.get('url'));kind=values.get('kind')
        if not url or kind not in ('poc','advisory','fix') or values.get('reviewed') is not True:raise ValueError('確認済みの公開URL・種類が必要です。')
        author=r.text(values.get('author','local-user'),'author',100,True)
        old=db.execute('SELECT id FROM security_references WHERE workspace_id=? AND entity_id=? AND url=? AND kind=?',(workspace_id,values['entity_id'],url,kind)).fetchone()
        if old:return old['id']
        if db.execute('SELECT count(*) FROM security_references WHERE workspace_id=?',(workspace_id,)).fetchone()[0]>=1000:raise ValueError('案件の参照リンクは1000件までです。')
        return db.execute('INSERT INTO security_references(workspace_id,entity_id,url,kind,quotation_id,author,created_at) VALUES(?,?,?,?,?,?,?)',(workspace_id,values['entity_id'],url,kind,values['quotation_id'],author,r.now())).lastrowid


def sync(identifier):
    item=cve_entity(identifier);db=get_db();created=0
    for provider in PROVIDERS:
        value='catalog' if provider=='kev' else item['canonical']
        cache=db.execute('SELECT * FROM connector_cache WHERE provider=? AND input=?',(provider,value)).fetchone()
        if not cache:continue
        selected=projection(provider,item['canonical'],json.loads(cache['payload']))
        with e.storage_lock(),r.transaction() as tx:
            previous=tx.execute('SELECT * FROM security_observations WHERE entity_id=? AND provider=? AND response_hash=?',(identifier,provider,cache['response_hash'])).fetchone()
            if previous:eid=previous['evidence_id']
            else:
                text=c.dumps({'provider':PROVIDERS[provider]['name'],'source_version':cache['source_version'],'response_hash':cache['response_hash'],'record':selected})
                eid=e.save(tx,source_key='security:'+provider+':'+item['canonical'],title=item['canonical']+' · '+PROVIDERS[provider]['name'],text=text,method='public-connector-projection',source_url=cache['source_url'],publisher=PROVIDERS[provider]['name'],source_guid=item['canonical'],observed_at=cache['observed_at'])
                tx.execute('INSERT INTO security_observations(entity_id,provider,response_hash,source_version,observed_at,payload,evidence_id) VALUES(?,?,?,?,?,?,?)',(identifier,provider,cache['response_hash'],cache['source_version'],cache['observed_at'],c.dumps(selected),eid));created+=1
            tx.execute('INSERT OR IGNORE INTO workspace_evidence(workspace_id,evidence_id) SELECT s.workspace_id,? FROM security_watches s JOIN workspaces w ON w.id=s.workspace_id WHERE s.entity_id=? AND s.enabled=1 AND w.archived=0',(eid,identifier))
    return created


def observations(identifier):
    item=cve_entity(identifier);db=get_db();result={}
    for provider,info in PROVIDERS.items():
        value='catalog' if provider=='kev' else item['canonical']
        cache=db.execute('SELECT * FROM connector_cache WHERE provider=? AND input=?',(provider,value)).fetchone()
        # Read projection from immutable captured evidence, not unreviewed raw response.
        row=db.execute('SELECT * FROM security_observations WHERE entity_id=? AND provider=? ORDER BY id DESC LIMIT 1',(identifier,provider)).fetchone()
        latest=db.execute('SELECT error FROM connector_jobs WHERE provider=? AND input=? ORDER BY id DESC LIMIT 1',(provider,value)).fetchone()
        stale=bool(row and (not cache or cache['response_hash']!=row['response_hash'] or cache['expires_at']<=r.now() or (latest and latest['error'])))
        result[provider]={'attribution':info['name'],'license_url':info['license'],'state':'unknown' if not row else ('stale' if stale else 'current'),'data':json.loads(row['payload']) if row else None,'evidence_id':row['evidence_id'] if row else None,'observed_at':row['observed_at'] if row else None,'last_checked_at':cache['observed_at'] if cache else None,'source_version':row['source_version'] if row else None,'error':latest['error'] if latest else None}
    return result


def card(identifier):
    item=watch(identifier);entity=cve_entity(item['entity_id']);signals=observations(entity['id'])
    db=get_db();manual=db.execute('SELECT * FROM security_reviews WHERE watch_id=? ORDER BY id DESC LIMIT 1',(identifier,)).fetchone()
    # A later watch edit invalidates a review of its old product/version/CVE configuration.
    if manual and manual['revision']==item['revision']:applicability={'status':manual['status'],'reason':manual['reason'],'review':dict(manual)}
    else:
        data=signals['cve']['data'];names=[]
        if data:
            for affected in data['affected']:names.extend([affected['product'],affected['vendor']+' '+affected['product']])
        kev=signals['kev']['data']
        if kev and kev['entry']:names.extend([kev['entry']['product'],kev['entry']['vendorProject']+' '+kev['entry']['product']])
        matched=bool(item['product'] and item['product'].casefold() in {v.casefold() for v in names})
        applicability={'status':'possible' if matched else 'unknown','reason':'製品名のみ一致。バージョン・実資産の適用性は未確認。' if matched else '適用性を判断できる根拠が未確認。','review':None}
    return {'watch':dict(item),'entity':dict(entity),'signals':signals,'applicability':applicability}


def schedule():
    db=get_db();items=db.execute('SELECT s.* FROM security_watches s JOIN workspaces w ON w.id=s.workspace_id WHERE s.enabled=1 AND w.archived=0 ORDER BY coalesce(s.last_processed_at,\'\'),s.id LIMIT 20').fetchall()
    for item in items:
        entity=cve_entity(item['entity_id'])
        if item['outbound_public']:
            for provider in PROVIDERS:
                if c.setting(provider)['enabled']:
                    try:c.enqueue(provider,{'input':'catalog' if provider=='kev' else entity['canonical'],'public_identifier':True})
                    except ValueError:pass  # bounded queue/cache limits; existing state remains visible
        sync(entity['id'])
        with r.transaction() as tx:tx.execute('UPDATE security_watches SET last_processed_at=? WHERE id=?',(r.now(),item['id']))
    return {'watches':len(items)}
