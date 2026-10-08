"""Historical passive provider scope, bounded change events and local watches."""
import json
from datetime import datetime,timedelta,timezone
from .db import get_db
from . import connectors as c,evidence as e,research as r,entities as n,triage as t,network_adapters as a


def watch(identifier,db=None):
    t.positive_id(identifier);row=(db or get_db()).execute('SELECT * FROM network_watches WHERE id=?',(identifier,)).fetchone()
    if row is None:raise r.ResearchMissing('ネットワークウォッチが見つかりません。')
    return row


def watch_input(entity,provider,values):
    if provider=='dns':value=entity['canonical']+'|'+values.get('rrtype','A')
    elif provider in ('rdap','routing'):value=entity['kind']+'|'+entity['canonical']
    elif provider=='ct':value=entity['canonical']
    elif provider=='rpki':
        origin=values.get('origin',entity['canonical'] if entity['kind']=='asn' else None);value=a.prefix(values.get('prefix'))+'|'+a.public('asn',origin)
        if entity['kind']=='asn' and origin!=entity['canonical']:raise ValueError('対象ASNとoriginが異なります。')
        if entity['kind']=='ip':
            import ipaddress
            if ipaddress.ip_address(entity['canonical']) not in ipaddress.ip_network(values['prefix']):raise ValueError('対象IPがprefixに含まれません。')
    else:raise ValueError('観測用providerを選んでください。')
    info=a.contract(provider,value)
    if entity['kind'] not in ('domain','ip','asn') or (provider=='rpki' and entity['kind'] not in ('ip','asn')) or (provider!='rpki' and entity['kind']!=info['kind']):raise ValueError('対象の種類とproviderが異なります。')
    return value


def save_watch(workspace_id,body,identifier=None):
    allowed={'outbound_public','enabled','interval_seconds','retention_days'}|({'expected_revision'} if identifier else {'entity_id','provider','rrtype','prefix','origin'})
    values=r.fields(body,allowed)
    if identifier:t.positive_id(values.get('expected_revision'))
    with r.transaction() as db:
        r.editable(workspace_id,db);old=watch(identifier,db) if identifier else None
        if old and (old['workspace_id']!=workspace_id or values['expected_revision']!=old['revision']):raise r.ResearchConflict('ウォッチが更新されています。')
        def val(name,default=None):return values.get(name,old[name] if old else default)
        eid=val('entity_id');entity=n.find(eid,db);provider=val('provider')
        if old and not set(values)&{'entity_id','provider','rrtype','prefix','origin'}:value=old['input']
        else:
            options=dict(values)
            if old:
                prior=a.contract(old['provider'],old['input']);options.setdefault('rrtype',prior.get('rrtype','A'));options.setdefault('prefix',prior.get('prefix'));options.setdefault('origin',prior.get('value') if old['provider']=='rpki' else None)
            value=watch_input(entity,provider,options)
        consent=val('outbound_public',False);enabled=val('enabled',True)
        if old:
            if 'outbound_public' not in values:consent=bool(consent)
            if 'enabled' not in values:enabled=bool(enabled)
        if type(consent) is not bool or type(enabled) is not bool:raise ValueError('許可と有効状態はJSON真偽値です。')
        interval=val('interval_seconds',86400);retention=val('retention_days',90)
        if type(interval) is not int or not 3600<=interval<=604800 or type(retention) is not int or not 7<=retention<=3650:raise ValueError('観測間隔・保存期間が不正です。')
        duplicate=db.execute('SELECT id FROM network_watches WHERE workspace_id=? AND entity_id=? AND provider=? AND input=?',(workspace_id,eid,provider,value)).fetchone()
        if duplicate and duplicate['id']!=identifier:raise r.ResearchConflict('同じ観測ウォッチがあります。')
        if identifier:
            db.execute('UPDATE network_watches SET entity_id=?,provider=?,input=?,outbound_public=?,enabled=?,interval_seconds=?,retention_days=?,next_check=?,revision=revision+1,updated_at=? WHERE id=?',(eid,provider,value,consent,enabled,interval,retention,r.now(),r.now(),identifier))
        else:
            if db.execute('SELECT count(*) FROM network_watches WHERE workspace_id=?',(workspace_id,)).fetchone()[0]>=100:raise ValueError('案件のネットワークウォッチは100件までです。')
            identifier=db.execute('INSERT INTO network_watches(workspace_id,entity_id,provider,input,outbound_public,enabled,interval_seconds,retention_days,next_check,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)',(workspace_id,eid,provider,value,consent,enabled,interval,retention,r.now(),r.now(),r.now())).lastrowid
        return identifier


def lookup(identifier):
    item=watch(identifier);r.editable(item['workspace_id'],get_db())
    if not item['enabled'] or not item['outbound_public']:raise r.ResearchConflict('観測の有効化と公開識別子の送信許可が必要です。')
    if item['provider']=='rdap':
        kind=a.bootstrap_kind(a.contract('rdap',item['input']))
        row=get_db().execute("SELECT expires_at FROM connector_cache WHERE provider='rdap-bootstrap' AND input=?",(kind,)).fetchone()
        if row is None or row['expires_at']<=r.now():return {'bootstrap_job_id':c.enqueue('rdap-bootstrap',{'input':kind,'public_identifier':True}),'job_id':None}
    return {'job_id':c.enqueue(item['provider'],{'input':item['input'],'public_identifier':True}),'bootstrap_job_id':None}


def semantic(value,provider):
    result=dict(value)
    for key in ('scope','input','coverage','truncated','source_timestamp','query_starttime','query_endtime','data_call_status'):result.pop(key,None)
    if provider=='dns':result.pop('records',None)
    return result


def sync(identifier):
    item=watch(identifier);db=get_db();cache=db.execute('SELECT * FROM connector_cache WHERE provider=? AND input=?',(item['provider'],item['input'])).fetchone()
    if cache is None:return None
    normalized=a.project(item['provider'],item['input'],json.loads(cache['payload']))
    with e.storage_lock(),r.transaction() as tx:
        existing=tx.execute('SELECT id FROM network_observations WHERE watch_id=? AND response_hash=? AND observed_at=?',(identifier,cache['response_hash'],cache['observed_at'])).fetchone()
        if existing:return existing['id']
        prior=tx.execute('SELECT * FROM network_observations WHERE watch_id=? ORDER BY id DESC LIMIT 1',(identifier,)).fetchone()
        text=c.dumps({'queried_at':cache['observed_at'],'provider':a.PROVIDERS[item['provider']]['name'],'source_version':cache['source_version'],'response_hash':cache['response_hash'],'normalized':normalized})
        eid=e.save(tx,source_key='network:'+item['provider']+':'+item['input'],title='受動的観測 · '+item['input'],text=text,method='passive-network-projection',source_url=cache['source_url'],publisher=a.PROVIDERS[item['provider']]['name'],source_guid=item['input'],observed_at=cache['observed_at'])
        current=tx.execute('INSERT INTO network_observations(watch_id,response_hash,source_url,source_version,observed_at,normalized,evidence_id) VALUES(?,?,?,?,?,?,?)',(identifier,cache['response_hash'],cache['source_url'],cache['source_version'],cache['observed_at'],c.dumps(normalized),eid)).lastrowid
        tx.execute('INSERT OR IGNORE INTO workspace_evidence VALUES(?,?)',(item['workspace_id'],eid))
        if prior:
            before=semantic(json.loads(prior['normalized']),item['provider']);after=semantic(normalized,item['provider'])
            changes={field:{'before':before.get(field),'after':after.get(field)} for field in sorted(before.keys()|after.keys()) if before.get(field)!=after.get(field)}
            if changes:tx.execute('INSERT INTO network_events(watch_id,previous_id,current_id,changes,created_at) VALUES(?,?,?,?,?)',(identifier,prior['id'],current,c.dumps(changes),r.now()))
        return current


def card(identifier):
    item=watch(identifier);entity=n.find(item['entity_id']);db=get_db()
    row=db.execute('SELECT * FROM network_observations WHERE watch_id=? ORDER BY id DESC LIMIT 1',(identifier,)).fetchone()
    cache=db.execute('SELECT * FROM connector_cache WHERE provider=? AND input=?',(item['provider'],item['input'])).fetchone()
    job=db.execute('SELECT * FROM connector_jobs WHERE provider=? AND input=? ORDER BY id DESC LIMIT 1',(item['provider'],item['input'])).fetchone()
    observed=None
    if row:observed=dict(row);observed['normalized']=json.loads(row['normalized'])
    ttl_expired=False
    if observed and item['provider']=='dns':
        records=observed['normalized']['records']
        if records:ttl_expired=datetime.strptime(row['observed_at'],'%Y-%m-%d %H:%M:%S')+timedelta(seconds=min(v['ttl'] for v in records))<=datetime.now(timezone.utc).replace(tzinfo=None)
    stale=bool(row and (not cache or cache['response_hash']!=row['response_hash'] or cache['expires_at']<=r.now() or (job and job['error']) or ttl_expired))
    return {'watch':dict(item),'entity':dict(entity),'observation':observed,'state':'unknown' if not row else ('stale' if stale else 'observed'),'ttl_expired':ttl_expired,'last_job':dict(job) if job else None,'provider':a.PROVIDERS[item['provider']]}


def prune(identifier):
    item=watch(identifier);cutoff=c.later(-86400*item['retention_days'])
    with r.transaction() as db:
        db.execute('DELETE FROM network_events WHERE watch_id=? AND created_at<?',(identifier,cutoff))
        return db.execute('''DELETE FROM network_observations WHERE watch_id=? AND observed_at<? AND id!=(SELECT max(id) FROM network_observations WHERE watch_id=?) AND NOT EXISTS(SELECT 1 FROM network_events v WHERE v.previous_id=network_observations.id OR v.current_id=network_observations.id) AND NOT EXISTS(SELECT 1 FROM quotations q WHERE q.evidence_id=network_observations.evidence_id) AND NOT EXISTS(SELECT 1 FROM note_evidence n WHERE n.evidence_id=network_observations.evidence_id)''',(identifier,cutoff,identifier)).rowcount


def schedule():
    items=get_db().execute("SELECT s.* FROM network_watches s JOIN workspaces w ON w.id=s.workspace_id WHERE s.enabled=1 AND w.archived=0 ORDER BY coalesce(s.last_processed_at,''),s.id LIMIT 20").fetchall()
    for item in items:
        if item['outbound_public'] and item['next_check']<=r.now() and c.setting(item['provider'])['enabled']:
            try:
                result=lookup(item['id'])
                if result['job_id']:
                    with r.transaction() as db:db.execute('UPDATE network_watches SET next_check=? WHERE id=?',(c.later(item['interval_seconds']),item['id']))
            except (ValueError,r.ResearchConflict):pass
        sync(item['id']);prune(item['id'])
        with r.transaction() as db:db.execute('UPDATE network_watches SET last_processed_at=? WHERE id=?',(r.now(),item['id']))
    return {'watches':len(items)}
