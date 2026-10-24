"""Read-only, allowlisted settings export. Never enumerate environment or secret files."""
from datetime import datetime, timezone
import json
import re
from urllib.parse import urlsplit, parse_qsl
from flask import request
from .db import get_db, SCHEMA_VERSION
from .presentation import THEME_COOKIE, THEMES

FIELDS = {
 'collection':('settings','poll_interval polling_enabled default_view api_rate_limit display_timezone'),
 'subscriptions':('feeds','id source_type source_kind url title folder enabled poll_interval target instance_url selector settle_ms retention_days'),
 'connectors':('connector_settings','provider enabled ttl_seconds daily_budget'),
 'models':('assistant_profiles','id name kind model model_digest enabled max_output_tokens daily_calls input_rate output_rate price_date max_cost daily_cost'),
 'notifications':('delivery_profiles','id name kind destination enabled'),
 'backup':('operations_config','backup_enabled interval_seconds generations quota_bytes'),
 'security_watches':('security_watches','id workspace_id entity_id product version outbound_public enabled'),
 'network_watches':('network_watches','id workspace_id entity_id provider input outbound_public enabled interval_seconds retention_days'),
 'ai_watches':('ai_watches','id workspace_id provider target term outbound_public enabled interval_seconds'),
}
SECRET = re.compile(r'(?:\b(?:Bearer\s+|sk-[A-Za-z0-9_-]*|api[_-]?key\s*[:=]|token\s*[:=]|password\s*[:=]|secret\s*[:=]))',re.I)


def presentation(raw):
    if not isinstance(raw,dict) or set(raw)-{'width','layout','disclosure'}:
        raise ValueError('表示設定が不正です。')
    result = {}
    if 'width' in raw:
        if type(raw['width']) is not int or not 200<=raw['width']<=480:
            raise ValueError('左ペインの幅が不正です。')
        result['width'] = raw['width']
    if 'layout' in raw:
        if raw['layout'] not in ('standard','line','tiles'):
            raise ValueError('記事の表示形式が不正です。')
        result['layout'] = raw['layout']
    if 'disclosure' in raw:
        states=raw['disclosure']
        if not isinstance(states,dict) or len(states)>2000 or any(not isinstance(k,str) or len(k)>80 or type(v) is not bool for k,v in states.items()):
            raise ValueError('フォルダーの開閉設定が不正です。')
        result['disclosure'] = states
    theme=request.cookies.get(THEME_COOKIE,'system')
    result['appearance'] = theme if theme in THEMES else 'system'
    return result


def export_settings(browser):
    from .social_ai import provider_settings, settings, LIMITS
    from .ai_providers import PROVIDERS, configured
    from .folders import feed_rows, feed_groups
    from .triage import find, record
    db=get_db();omissions=[]

    def scrub(value,path):
        if isinstance(value,str):
            parsed=urlsplit(value) if value.startswith(('http://','https://')) else None
            credential = bool(SECRET.search(value))
            if parsed:
                credential |= bool(parsed.username or parsed.password)
                credential |= any(re.search(r'(?:key|token|secret|password|signature|authorization|credential)',key,re.I) for key,_ in parse_qsl(parsed.query))
            if credential:
                omissions.append({'field':path,'reason':'credential-bearing value omitted'})
                return None
        if isinstance(value,dict):return {k:scrub(v,path+'.'+k) for k,v in value.items()}
        if isinstance(value,list):return [scrub(v,path+f'[{i}]') for i,v in enumerate(value)]
        return value

    data={}
    # A single database snapshot, including provider profiles and ordering.
    db.execute('BEGIN')
    try:
        for section,(table,fields) in FIELDS.items():
            rows=[dict(row) for row in db.execute('SELECT '+','.join(fields.split())+' FROM '+table)]
            data[section]=rows[0] if section in ('collection','backup') else rows
        topics = [dict(row) for row in db.execute('SELECT feed_id,window_hours,ai_enabled,ai_criteria FROM social_topics')]
        data['topic_settings'] = topics
        active=settings()
        data['ai']={'provider':active['provider'],'daily_calls':active['daily_calls'],'daily_cost':active['daily_cost'],'providers':{}}
        for provider in PROVIDERS:
            cfg=provider_settings(provider)
            data['ai']['providers'][provider]={k:cfg[k] for k in ('enabled','model','max_output_tokens','input_rate','output_rate','max_cost')}
            data['ai']['providers'][provider]['credential_configured']=configured(provider)
        data['library_order']=[{'folder':group['name'],'feeds':[f['id'] for f in group['feeds']]} for group in feed_groups(feed_rows())]
        data['watchlists']=[]
        for row in db.execute('SELECT id FROM watchlists ORDER BY id'):
            item=record(find(row['id']))
            data['watchlists'].append({k:item[k] for k in ('id','workspace_id','name','kind','enabled','query','exclusion','priority','reason')})
        references={
            'workspaces':[dict(row) for row in db.execute('SELECT id,title FROM workspaces')],
            'entities':[dict(row) for row in db.execute('SELECT id,kind,canonical FROM entities WHERE merged_into IS NULL')],
        }
        data['presentation']=presentation(browser)
        result={'format':'feedastrolabe-settings','format_version':1,'app_version':'0.16.0',
                'db_schema_version':SCHEMA_VERSION,'exported_at':datetime.now(timezone.utc).isoformat(),
                'settings':scrub(data,'settings'),'references':scrub(references,'references'),'omissions':omissions}
        db.rollback()  # Read-only snapshot; do not retain a lock after download.
        return result
    except BaseException:
        db.rollback();raise
