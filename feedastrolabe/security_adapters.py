"""Read-only public projections. Unknown fields do not become applicability facts."""
from datetime import date
from decimal import Decimal,InvalidOperation
from urllib.parse import urlsplit
import ipaddress
from . import entities as n
from .fetch import safe_link

PROVIDERS={
 'kev':{'name':'CISA KEV (official mirror)','url':'https://raw.githubusercontent.com/cisagov/kev-data/develop/known_exploited_vulnerabilities.json','license':'https://github.com/cisagov/kev-data/blob/develop/LICENSE'},
 'epss':{'name':'FIRST / Empirical Security EPSS','url':'https://api.first.org/data/v1/epss','license':'https://www.first.org/epss/faq'},
 'cve':{'name':'CVE Program / CNA / ADP','url':'https://cveawg.mitre.org/api/cve/','license':'https://www.cve.org/legal/termsofuse'},
}


def text(value,maximum=10000):
    if not isinstance(value,str) or len(value)>maximum:raise ValueError('provider-format')
    return value


def day(value):
    text(value,10)
    if date.fromisoformat(value).isoformat()!=value:raise ValueError('provider-format')
    return value


def link(value):
    if not isinstance(value,str) or len(value)>2048:return ''
    value=safe_link(value)
    if not value:return ''
    host=urlsplit(value).hostname
    if host=='localhost' or host.endswith(('.localhost','.local')):return ''
    try:
        ip=ipaddress.ip_address(host)
        if not ip.is_global:return ''
    except ValueError:pass
    return value


def endpoint(provider,value):
    if provider not in PROVIDERS:raise ValueError('provider-policy')
    if provider=='kev':
        if value!='catalog':raise ValueError('input-policy')
        return PROVIDERS[provider]['url']
    if n.normalize('cve',value)!=value:raise ValueError('input-policy')
    return PROVIDERS[provider]['url']+('?'+'cve='+value if provider=='epss' else value)


def validate(provider,value,payload):
    if not isinstance(payload,dict):raise ValueError('provider-format')
    if provider=='kev':
        rows=payload.get('vulnerabilities');version=text(payload.get('catalogVersion'),100);text(payload.get('dateReleased'),100)
        if not isinstance(rows,list) or len(rows)>10000 or payload.get('count')!=len(rows):raise ValueError('provider-format')
        seen=set()
        for row in rows:
            identifier=n.normalize('cve',row.get('cveID'))
            if identifier!=row['cveID'] or identifier in seen:raise ValueError('provider-format')
            seen.add(identifier)
            for field in ('vendorProject','product','vulnerabilityName','shortDescription','requiredAction','notes'):text(row.get(field,''))
            day(row.get('dateAdded'));day(row.get('dueDate'))
        return version
    if provider=='epss':
        if payload.get('status')!='OK' or payload.get('status-code')!=200:raise ValueError('provider-format')
        rows=payload.get('data')
        if not isinstance(rows,list) or len(rows)>1 or payload.get('total')!=len(rows):raise ValueError('provider-format')
        for row in rows:
            if row.get('cve')!=value:raise ValueError('provider-format')
            day(row.get('date'))
            for name in ('epss','percentile'):
                try:number=Decimal(str(row[name]))
                except (KeyError,InvalidOperation):raise ValueError('provider-format') from None
                if not number.is_finite() or not 0<=number<=1:raise ValueError('provider-format')
        return text(payload.get('version'),100)
    if provider=='cve':
        version=text(payload.get('dataVersion'),20)
        if not version.startswith('5.') or payload.get('dataType')!='CVE_RECORD':raise ValueError('provider-format')
        metadata=payload.get('cveMetadata',{})
        if metadata.get('cveId')!=value or metadata.get('state') not in ('PUBLISHED','REJECTED'):raise ValueError('provider-format')
        if not isinstance(payload.get('containers'),dict):raise ValueError('provider-format')
        # Validate projection before replacing last-good cache.
        projection(provider,value,payload)
        return version
    raise ValueError('provider-policy')


def projection(provider,cve,payload):
    if provider=='kev':
        row=next((r for r in payload['vulnerabilities'] if r['cveID']==cve),None)
        return {'cve':cve,'listed':row is not None,'catalog_version':payload['catalogVersion'],'date_released':payload['dateReleased'],'entry':row}
    if provider=='epss':
        row=payload['data'][0] if payload['data'] else None
        return {'cve':cve,'available':row is not None,'score':float(row['epss']) if row else None,'percentile':float(row['percentile']) if row else None,'date':row['date'] if row else None,'api_version':payload['version'],'model_version':'not supplied by public API','horizon_days':30}
    metadata=payload['cveMetadata'];containers=payload['containers'];cna=containers.get('cna',{});adp=containers.get('adp',[])
    if not isinstance(cna,dict) or not isinstance(adp,list):raise ValueError('provider-format')
    result={'cve':cve,'state':metadata['state'],'data_version':payload['dataVersion'],'date_updated':metadata.get('dateUpdated'),'description':[],'affected':[],'severity':[],'references':[],'remediation':[],'truncated':len(adp)>20}
    for container in [cna]+adp[:20]:
        if not isinstance(container,dict):raise ValueError('provider-format')
        attribution=text(container.get('providerMetadata',{}).get('shortName','unknown'),100)
        for field in ('descriptions','affected','metrics','references','solutions','workarounds'):
            if not isinstance(container.get(field,[]),list):raise ValueError('provider-format')
            if len(container.get(field,[]))>50:result['truncated']=True
        for row in container.get('descriptions',[])[:50]:result['description'].append({'source':attribution,'lang':text(row.get('lang',''),20),'value':text(row.get('value',''))})
        for row in container.get('affected',[])[:50]:
            versions=row.get('versions',[])
            if not isinstance(versions,list):raise ValueError('provider-format')
            result['truncated'] |= len(versions)>50
            result['affected'].append({'source':attribution,'vendor':text(row.get('vendor',''),300),'product':text(row.get('product',''),300),'default_status':text(row.get('defaultStatus','unknown'),100),'versions':versions[:50]})
        for row in container.get('metrics',[])[:50]:
            for key,metric in row.items():
                if key in ('cvssV2_0','cvssV3_0','cvssV3_1','cvssV4_0'):
                    if not isinstance(metric,dict):raise ValueError('provider-format')
                    score=metric.get('baseScore')
                    if type(score) not in (int,float) or not 0<=score<=10:raise ValueError('provider-format')
                    result['severity'].append({'source':attribution,'version':text(metric.get('version',''),20),'score':score,'vector':text(metric.get('vectorString',''),500)})
        for row in container.get('references',[])[:50]:
            url=link(text(row.get('url',''),2048))
            if url:result['references'].append({'source':attribution,'url':url,'tags':row.get('tags',[])})
        for field in ('solutions','workarounds'):
            for row in container.get(field,[])[:50]:result['remediation'].append({'source':attribution,'kind':field,'value':text(row.get('value',''))})
    import json
    if len(json.dumps(result,ensure_ascii=False))>150000:raise ValueError('projection-size')
    return result
