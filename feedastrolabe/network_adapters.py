"""Passive registered public network lookups; referrals never become arbitrary URLs."""
import ipaddress,json
from urllib.parse import urlencode
from . import entities as n
from .security_adapters import text

PROVIDERS={
 'dns':{'name':'Google Public DNS JSON','url':'https://dns.google/resolve','license':'https://developers.google.com/speed/public-dns/docs/doh/json'},
 'rdap-bootstrap':{'name':'IANA RDAP bootstrap','url':'https://data.iana.org/rdap/','license':'https://www.iana.org/assignments/rdap-dns'},
 'rdap':{'name':'Reviewed registry RDAP','url':'IANA selected reviewed HTTPS authority','license':'https://www.icann.org/rdap/'},
 'routing':{'name':'RIPEstat / RIS routing','url':'https://stat.ripe.net/data/','license':'https://www.ripe.net/about-us/legal/ripestat-service-terms-and-conditions'},
 'rpki':{'name':'RIPEstat RPKI validation','url':'https://stat.ripe.net/data/rpki-validation/data.json','license':'https://www.ripe.net/about-us/legal/ripestat-service-terms-and-conditions'},
 'ct':{'name':'crt.sh / Sectigo CT metadata','url':'https://crt.sh/','license':'https://github.com/crtsh/certwatch_db/issues/56'},
}
RR={'A':1,'AAAA':28,'MX':15,'NS':2,'TXT':16,'SOA':6,'CAA':257}
BASES={'https://rdap.afrinic.net/rdap/','https://rdap.apnic.net/','https://rdap.arin.net/registry/','https://rdap.db.ripe.net/','https://rdap.lacnic.net/rdap/','https://rdap.verisign.com/com/v1/','https://rdap.verisign.com/net/v1/'}


def public(kind,value):
    result=n.normalize(kind,value)
    if kind=='ip':
        address=ipaddress.ip_address(result)
        if not address.is_global or address.is_multicast or address.is_reserved or getattr(address,'ipv4_mapped',None):raise ValueError('public-input-required')
    if kind=='domain' and result.endswith(('.localhost','.local','.internal','.test','.invalid','.example','.onion','.home.arpa')):raise ValueError('public-input-required')
    return result


def prefix(value):
    if not isinstance(value,str) or len(value)>100:raise ValueError('public-prefix-required')
    network=ipaddress.ip_network(value,strict=True)
    if network.with_prefixlen!=value or not network.network_address.is_global or not network.broadcast_address.is_global or network.is_multicast or network.is_reserved or (network.version==6 and network.network_address.ipv4_mapped):raise ValueError('public-prefix-required')
    return value


def contract(provider,value):
    if not isinstance(value,str) or len(value)>400:raise ValueError('input-policy')
    parts=value.split('|')
    if provider=='rdap-bootstrap':
        if value not in ('dns','ipv4','ipv6','asn'):raise ValueError('input-policy')
        return {'bootstrap':value}
    if provider=='dns':
        if len(parts)!=2 or parts[1] not in RR or public('domain',parts[0])!=parts[0]:raise ValueError('input-policy')
        return {'kind':'domain','value':parts[0],'rrtype':parts[1]}
    if provider=='ct':
        if public('domain',value)!=value:raise ValueError('input-policy')
        return {'kind':'domain','value':value}
    if provider in ('rdap','routing'):
        if len(parts)!=2 or parts[0] not in (('domain','ip','asn') if provider=='rdap' else ('ip','asn')) or public(parts[0],parts[1])!=parts[1]:raise ValueError('input-policy')
        return {'kind':parts[0],'value':parts[1]}
    if provider=='rpki':
        if len(parts)!=2:raise ValueError('prefix-origin-required')
        return {'kind':'asn','value':public('asn',parts[1]),'prefix':prefix(parts[0])}
    raise ValueError('provider-policy')


def bootstrap_kind(info):
    return 'dns' if info['kind']=='domain' else ('asn' if info['kind']=='asn' else 'ipv'+str(ipaddress.ip_address(info['value']).version))


def authority(info,payload):
    candidates=[]
    for keys,urls in payload['services']:
        for key in keys:
            matched=False;length=0
            if info['kind']=='domain':matched=info['value']==key or info['value'].endswith('.'+key);length=len(key)
            elif info['kind']=='ip':
                network=ipaddress.ip_network(key);matched=ipaddress.ip_address(info['value']) in network;length=network.prefixlen
            else:
                lo,hi=(int(v) for v in key.split('-'));matched=lo<=int(info['value'][2:])<=hi;length=-(hi-lo)
            if matched:
                candidates.append((length,urls))
    if not candidates:raise ValueError('rdap-authority-unreviewed-or-missing')
    best=max(v[0] for v in candidates)
    urls=sorted({url for length,options in candidates if length==best for url in options if url in BASES})
    if not urls:raise ValueError('rdap-authority-unreviewed-or-missing')
    return urls[0]


def endpoint(provider,value):
    info=contract(provider,value)
    if provider=='rdap-bootstrap':return PROVIDERS[provider]['url']+value+'.json'
    if provider=='dns':return PROVIDERS[provider]['url']+'?'+urlencode({'name':info['value'],'type':info['rrtype'],'do':'true','cd':'false','edns_client_subnet':'0.0.0.0/0'})
    if provider=='ct':return PROVIDERS[provider]['url']+'?'+urlencode({'q':info['value'],'output':'json'})
    if provider=='routing':return PROVIDERS[provider]['url']+('network-info' if info['kind']=='ip' else 'announced-prefixes')+'/data.json?'+urlencode({'resource':info['value']})
    if provider=='rpki':return PROVIDERS[provider]['url']+'?'+urlencode({'resource':info['value'][2:],'prefix':info['prefix']})
    from .db import get_db
    row=get_db().execute("SELECT payload,expires_at FROM connector_cache WHERE provider='rdap-bootstrap' AND input=?",(bootstrap_kind(info),)).fetchone()
    from .research import now
    if row is None or row['expires_at']<=now():raise ValueError('rdap-bootstrap-required')
    base=authority(info,json.loads(row['payload']))
    return base+('autnum/' if info['kind']=='asn' else info['kind']+'/')+(info['value'][2:] if info['kind']=='asn' else info['value'])


def project(provider,value,payload):
    info=contract(provider,value)
    if provider=='rdap-bootstrap':
        if not isinstance(payload,dict) or not isinstance(payload.get('services'),list) or len(payload['services'])>5000:raise ValueError('provider-format')
        text(payload.get('version'),30);text(payload.get('publication'),100)
        for row in payload['services']:
            if not isinstance(row,list) or len(row)!=2 or any(not isinstance(v,list) for v in row) or sum(map(len,row))>5000:raise ValueError('provider-format')
            for key in row[0]:text(key,300)
            for url in row[1]:text(url,2048)
        return payload
    result={'scope':PROVIDERS[provider]['name'],'input':info,'coverage':'provider-scoped','truncated':False}
    if provider=='dns':
        if not isinstance(payload,dict) or type(payload.get('Status')) is not int or payload['Status'] not in (0,3):raise ValueError('dns-failure-or-format')
        questions=payload.get('Question',[])
        if len(questions)!=1 or n.normalize('domain',questions[0].get('name'))!=info['value'] or questions[0].get('type')!=RR[info['rrtype']]:raise ValueError('dns-question-mismatch')
        rows=payload.get('Answer',[])
        if not isinstance(rows,list):raise ValueError('provider-format')
        records=[]
        for row in rows[:200]:
            name=text(row.get('name'),253);kind=row.get('type');ttl=row.get('TTL');data=text(row.get('data'),10000)
            if type(kind) is not int or type(ttl) is not int or not 0<=ttl<=2147483647:raise ValueError('provider-format')
            records.append({'name':name.lower(),'type':kind,'data':data,'ttl':ttl})
        records.sort(key=lambda v:(v['name'],v['type'],v['data']))
        result.update(rcode=payload['Status'],dnssec_validated=payload.get('AD') is True,records=records,rrset=[{k:v[k] for k in ('name','type','data')} for v in records],absence='nxdomain' if payload['Status']==3 else ('nodata' if not any(v['type']==RR[info['rrtype']] for v in records) else None),truncated=payload.get('TC') is True or len(rows)>200)
    elif provider=='rdap':
        expected={'domain':'domain','ip':'ip network','asn':'autnum'}[info['kind']]
        if not isinstance(payload,dict) or payload.get('objectClassName')!=expected:raise ValueError('rdap-class-mismatch')
        if info['kind']=='domain' and n.normalize('domain',payload.get('ldhName'))!=info['value']:raise ValueError('rdap-resource-mismatch')
        if info['kind']=='ip' and not ipaddress.ip_address(payload['startAddress'])<=ipaddress.ip_address(info['value'])<=ipaddress.ip_address(payload['endAddress']):raise ValueError('rdap-resource-mismatch')
        if info['kind']=='asn' and not payload['startAutnum']<=int(info['value'][2:])<=payload['endAutnum']:raise ValueError('rdap-resource-mismatch')
        for field in ('status','events','nameservers','links','rdapConformance','notices'):
            rows=payload.get(field,[])
            if not isinstance(rows,list):raise ValueError('provider-format')
            result[field]=rows[:100];result['truncated']|=len(rows)>100
        result.update(handle=text(payload.get('handle',''),300),name=text(payload.get('name',payload.get('ldhName','')),300),start=payload.get('startAddress',payload.get('startAutnum')),end=payload.get('endAddress',payload.get('endAutnum')),referrals_followed=False)
    elif provider in ('routing','rpki'):
        if not isinstance(payload,dict) or payload.get('status')!='ok' or not isinstance(payload.get('data'),dict):raise ValueError('provider-format')
        data=payload['data'];result['source_timestamp']=payload.get('time');result['data_call_status']=payload.get('data_call_status')
        if provider=='rpki':
            if str(data.get('resource')).removeprefix('AS')!=info['value'][2:] or data.get('prefix')!=info['prefix'] or data.get('status') not in ('valid','invalid_asn','invalid_length','unknown'):raise ValueError('rpki-pair-mismatch')
            result.update(status=data['status'],description=text(data.get('description',''),10000),prefix=info['prefix'],origin=info['value'])
        elif info['kind']=='ip':
            network=data.get('prefix');asns=data.get('asns',[])
            if not isinstance(asns,list):raise ValueError('provider-format')
            if network and ipaddress.ip_address(info['value']) not in ipaddress.ip_network(network):raise ValueError('routing-prefix-mismatch')
            result.update(prefix=network,origins=sorted({n.normalize('asn','AS'+str(v)) for v in asns[:100]}),truncated=len(asns)>100,absence='not-visible-at-RIS' if not network else None)
        else:
            if n.normalize('asn','AS'+str(data.get('resource')).removeprefix('AS'))!=info['value']:raise ValueError('routing-resource-mismatch')
            rows=data.get('prefixes',[])
            if not isinstance(rows,list):raise ValueError('provider-format')
            result.update(prefixes=sorted({str(ipaddress.ip_network(row['prefix'])) for row in rows[:500]}),query_starttime=data.get('query_starttime'),query_endtime=data.get('query_endtime'),truncated=len(rows)>500,absence='not-visible-at-RIS' if not rows else None)
    elif provider=='ct':
        if not isinstance(payload,list):raise ValueError('provider-format')
        rows=[];seen=set()
        for row in payload[:1000]:
            if not isinstance(row,dict) or type(row.get('id')) is not int:raise ValueError('provider-format')
            names=text(row.get('name_value',''),10000).splitlines()
            if not any(v.lower().removeprefix('*.').rstrip('.')==info['value'] for v in names):continue
            if row['id'] in seen:continue
            seen.add(row['id']);rows.append({key:row.get(key) for key in ('id','issuer_name','common_name','name_value','not_before','not_after','entry_timestamp','serial_number')})
            if len(rows)>=200:break
        result.update(certificates=sorted(rows,key=lambda v:v['id']),truncated=len(payload)>1000 or len(rows)>=200,absence='not-seen-in-this-query' if not rows else None,interpretation='certificate issuance/log inclusion only; serving endpoint not verified')
    if len(json.dumps(result,ensure_ascii=False))>150000:raise ValueError('projection-size')
    return result


def validate(provider,value,payload):
    project(provider,value,payload)
    if provider=='rdap-bootstrap':return payload['version']+' / '+payload['publication']
    if provider in ('routing','rpki'):return text(payload.get('version','not provided'),100)
    return 'provider protocol; revision not supplied'
