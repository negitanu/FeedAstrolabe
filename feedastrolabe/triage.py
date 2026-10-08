"""Bounded literal query AST, immutable rules and transactional in-app matching."""
from datetime import datetime
import ipaddress
import json
from urllib.parse import urlsplit,urlunsplit,parse_qsl,urlencode
from .db import get_db
from . import evidence as e,research as r

TEXT_FIELDS={'title','text','publisher','url'}
DATE_FIELDS={'published_at','captured_at'}
FIELDS=TEXT_FIELDS|DATE_FIELDS|{'source_type','tag'}
PRIORITIES=('low','normal','high','critical')
SCOPE='''(EXISTS(SELECT 1 FROM workspace_evidence x WHERE x.workspace_id=? AND x.evidence_id=e.id)
 OR EXISTS(SELECT 1 FROM note_evidence x JOIN notes n ON n.id=x.note_id WHERE n.workspace_id=? AND x.evidence_id=e.id)
 OR EXISTS(SELECT 1 FROM quotations x WHERE x.workspace_id=? AND x.evidence_id=e.id)
 OR EXISTS(SELECT 1 FROM workspace_articles x WHERE x.workspace_id=? AND x.article_id=e.article_id)
 OR EXISTS(SELECT 1 FROM workspace_feeds x WHERE x.workspace_id=? AND x.feed_id=e.feed_id))'''


def query_ast(value):
    if not isinstance(value,dict) or set(value)-{'all','any','none'} or len(json.dumps(value,ensure_ascii=False))>2000:
        raise ValueError('検索条件は all/any/none の JSON、2000文字以内で指定してください。')
    normalized={key:value.get(key,[]) for key in ('all','any','none')}
    for terms in normalized.values():
        if not isinstance(terms,list) or len(terms)>40:raise ValueError('条件は40件以内です。')
        for term in terms:
            if not isinstance(term,dict) or set(term)!={'field','op','value'}:raise ValueError('条件に field/op/value を指定してください。')
            field,op,text=term['field'],term['op'],term['value']
            if not isinstance(field,str) or field not in FIELDS or not isinstance(op,str) or not isinstance(text,str) or not 1<=len(text)<=200:
                raise ValueError('条件の項目・値が不正です。')
            allowed={'eq','gte','lte'} if field in DATE_FIELDS else ({'contains','eq'} if field in TEXT_FIELDS else {'eq'})
            if op not in allowed:raise ValueError('条件の演算子が不正です。')
            if field in DATE_FIELDS:
                try:
                    if datetime.strptime(text,'%Y-%m-%d %H:%M:%S').strftime('%Y-%m-%d %H:%M:%S')!=text:raise ValueError()
                except ValueError:raise ValueError('日時は実在する UTC YYYY-MM-DD HH:MM:SS を指定してください。') from None
            if field=='source_type' and text not in ('rss','x','mastodon','page','attachment','unknown'):raise ValueError('情報源種別が不正です。')
    if len(json.dumps(normalized,ensure_ascii=False))>2000:raise ValueError('検索条件は2000文字以内です。')
    if sum(len(x) for x in normalized.values())>40:raise ValueError('条件は合計40件以内です。')
    return normalized


def ast_count(value):return sum(len(terms) for terms in value.values())


def positive_id(identifier):
    if type(identifier) is not int or not 1<=identifier<=2**63-1:raise ValueError('ID が不正です。')
    return identifier


def find(identifier,db=None):
    positive_id(identifier)
    row=(db or get_db()).execute('SELECT w.*,v.id AS version_id,v.query,v.exclusion,v.priority,v.reason,v.cursor FROM watchlists w JOIN watchlist_versions v ON v.watchlist_id=w.id AND v.revision=w.revision WHERE w.id=?',(identifier,)).fetchone()
    if row is None:raise r.ResearchMissing('保存条件が見つかりません。')
    return row


def record(row):
    result=dict(row)
    for field in ('query','exclusion','explanation'):
        if field in result:result[field]=json.loads(result[field])
    if 'enabled' in result:result['enabled']=bool(result['enabled'])
    if 'seen' in result:result['seen']=bool(result['seen'])
    if 'included' in result:result['included']=bool(result['included'])
    return result


def save(workspace_id,body,identifier=None):
    fields={'name','kind','enabled','query','exclusion','priority','reason'}
    values=r.fields(body,fields|({'expected_revision'} if identifier is not None else set()))
    with e.storage_lock(),r.transaction() as db:
        r.editable(workspace_id,db)
        old=find(identifier,db) if identifier is not None else None
        if old and old['workspace_id']!=workspace_id:raise r.ResearchMissing('保存条件がこの案件にありません。')
        if old and (type(values.get('expected_revision')) is not int or values['expected_revision']!=old['revision']):raise r.ResearchConflict('条件が更新されています。再取得してください。')
        if not old and db.execute('SELECT count(*) FROM watchlists WHERE workspace_id=?',(workspace_id,)).fetchone()[0]>=100:raise ValueError('案件ごとの保存条件は100件までです。')
        def val(key,default):return values.get(key,old[key] if old else default)
        name=r.text(val('name',None),'name',120,True)
        kind=val('kind','watchlist');priority=val('priority','normal');enabled=values.get('enabled',bool(old['enabled']) if old else kind=='watchlist')
        if not isinstance(kind,str) or kind not in ('watchlist','saved-search') or not isinstance(priority,str) or priority not in PRIORITIES or type(enabled) is not bool:raise ValueError('種類・優先度・自動処理の指定が不正です。')
        reason=r.text(val('reason',''),'reason',500)
        query=query_ast(values.get('query',json.loads(old['query']) if old else {}))
        exclusion=query_ast(values.get('exclusion',json.loads(old['exclusion']) if old else {}))
        if ast_count(query)+ast_count(exclusion)>40:raise ValueError('包含・除外の合計は40条件までです。')
        revision=old['revision']+1 if old else 1;stamp=r.now()
        if old:
            db.execute('UPDATE watchlists SET name=?,kind=?,enabled=?,revision=?,last_run=\'\',updated_at=? WHERE id=?',(name,kind,int(enabled),revision,stamp,identifier))
        else:
            identifier=db.execute('INSERT INTO watchlists(workspace_id,name,kind,enabled,revision,created_at,updated_at) VALUES(?,?,?,?,?,?,?)',(workspace_id,name,kind,int(enabled),revision,stamp,stamp)).lastrowid
        db.execute('INSERT INTO watchlist_versions(watchlist_id,revision,query,exclusion,priority,reason,created_at) VALUES(?,?,?,?,?,?,?)',(identifier,revision,json.dumps(query,ensure_ascii=False),json.dumps(exclusion,ensure_ascii=False),priority,reason,stamp))
    return identifier


def evaluate(ast,item,db):
    facts=dict(item);facts['url']=item['source_url']
    source=db.execute('SELECT source_type FROM feeds WHERE id=?',(item['feed_id'],)).fetchone()
    facts['source_type']='attachment' if item['method'].startswith('attachment-') else ('page' if item['method']=='page-selected-text' else source[0] if source else 'unknown')
    tags=[row[0] for row in db.execute('SELECT t.name FROM tags t JOIN article_tags a ON a.tag_id=t.id WHERE a.article_id=?',(item['article_id'],))]
    tests={key:[] for key in ast};matched=[];folded={}
    folded_tags={tag.casefold() for tag in tags}
    for key,terms in ast.items():
        for term in terms:
            field,op,value=term['field'],term['op'],term['value'];actual=facts.get(field)
            if field=='tag':ok=value.casefold() in folded_tags
            elif actual is None:ok=False
            elif field in DATE_FIELDS:ok=(actual==value if op=='eq' else actual>=value if op=='gte' else actual<=value)
            else:
                if field not in folded:folded[field]=str(actual).casefold()
                ok=value.casefold() in folded[field] if op=='contains' else value.casefold()==folded[field]
            tests[key].append(ok)
            matched.append({'clause':key,'matched':ok,**term})
    return all(tests['all']) and (not tests['any'] or any(tests['any'])) and not any(tests['none']),matched


def evidence_rows(workspace_id,cursor=0,limit=100):
    return get_db().execute('SELECT e.* FROM evidence e WHERE e.id>? AND '+SCOPE+' ORDER BY e.id LIMIT ?',[cursor]+[workspace_id]*5+[limit]).fetchall()


def preview(identifier,cursor=0):
    rule=find(identifier);rows=evidence_rows(rule['workspace_id'],cursor);items=[]
    for item in rows:
        explanation,include=decision(rule,item,get_db());items.append({'evidence_id':item['id'],'included':include,'explanation':explanation})
    return {'data':items,'next_after_id':rows[-1]['id'] if rows else cursor,'batch_limit':100}


def decision(rule,item,db):
    query,exclude=json.loads(rule['query']),json.loads(rule['exclusion'])
    included,reasons=evaluate(query,item,db);excluded,explanations=evaluate(exclude,item,db)
    excluded=bool(ast_count(exclude)) and excluded
    return {'include_matches':reasons,'exclude_matches':explanations,'include_passed':included,'exclusion_passed':excluded,'priority':rule['priority'],'reason':rule['reason']},included and not excluded


def reprocess(identifier):
    with e.storage_lock(),r.transaction() as db:
        item=find(identifier,db);r.editable(item['workspace_id'],db)
        db.execute('UPDATE watchlist_versions SET cursor=0 WHERE id=?',(item['version_id'],))
        db.execute("UPDATE watchlists SET last_run='' WHERE id=?",(identifier,))
    return process(identifier)


def canonical_url(value):
    from .fetch import normalize_url
    try:parts=urlsplit(normalize_url(value))
    except (ValueError,TypeError):return None
    if parts.hostname == 'localhost' or parts.hostname.endswith(('.localhost','.local')):return None
    try:address=ipaddress.ip_address(parts.hostname)
    except ValueError:address=None
    if address is not None and (not address.is_global or (getattr(address,'ipv4_mapped',None) is not None and not address.ipv4_mapped.is_global)):return None
    query=[(key,val) for key,val in parse_qsl(parts.query,keep_blank_values=True) if not key.lower().startswith('utm_') and key.lower() not in ('fbclid','gclid')]
    return urlunsplit((parts.scheme.lower(),parts.netloc.lower(),parts.path or '/',urlencode(sorted(query)),''))


def group_batch(db):
    cursor=db.execute('SELECT cursor FROM triage_state WHERE id=1').fetchone()[0]
    rows=db.execute('SELECT * FROM evidence WHERE id>? ORDER BY id LIMIT 100',(cursor,)).fetchall()
    for item in rows:
        url=canonical_url(item['source_url']);keys=[]
        if item['text'].strip():keys.append(('content',item['text_hash']))
        if url:keys.append(('url',e.digest(url.encode())))
        for kind,key in keys:
            db.execute('INSERT OR IGNORE INTO duplicate_fingerprints(evidence_id,kind,key) VALUES(?,?,?)',(item['id'],kind,key))
            distinct=db.execute('SELECT count(DISTINCT e.source_key) FROM duplicate_fingerprints f JOIN evidence e ON e.id=f.evidence_id WHERE f.kind=? AND f.key=?',(kind,key)).fetchone()[0]
            if distinct<2:continue
            stamp=r.now();created=db.execute('INSERT OR IGNORE INTO duplicate_groups(kind,key,created_at,updated_at) VALUES(?,?,?,?)',(kind,key,stamp,stamp)).rowcount
            group=db.execute('SELECT id FROM duplicate_groups WHERE kind=? AND key=?',(kind,key)).fetchone()[0]
            if created:
                db.execute('INSERT OR IGNORE INTO duplicate_members(group_id,evidence_id) SELECT ?,evidence_id FROM duplicate_fingerprints WHERE kind=? AND key=?',(group,kind,key))
            else:
                db.execute('INSERT OR IGNORE INTO duplicate_members(group_id,evidence_id) VALUES(?,?)',(group,item['id']))
    if rows:db.execute('UPDATE triage_state SET cursor=? WHERE id=1',(rows[-1]['id'],))
    return len(rows)


def process(identifier=None):
    with e.storage_lock(),r.transaction() as db:
        if identifier is not None:
            current=find(identifier,db);r.editable(current['workspace_id'],db);rules=[current]
        else:
            identifiers=db.execute('SELECT w.id FROM watchlists w JOIN workspaces s ON s.id=w.workspace_id WHERE w.enabled=1 AND s.archived=0 ORDER BY w.last_run,w.id LIMIT 20').fetchall()
            rules=[find(row[0],db) for row in identifiers]
        created=0;scanned=0
        for rule in rules:
            rows=evidence_rows(rule['workspace_id'],rule['cursor'])
            for item in rows:
                explanation,included=decision(rule,item,db)
                # Record meaningful include/exclude results, including a losing inclusion.
                if explanation['include_passed'] or explanation['exclusion_passed']:
                    result=db.execute('INSERT OR IGNORE INTO watch_events(version_id,evidence_id,included,explanation,created_at) VALUES(?,?,?,?,?)',(rule['version_id'],item['id'],int(included),json.dumps(explanation,ensure_ascii=False),r.now()))
                    created+=result.rowcount
            cursor=rows[-1]['id'] if rows else rule['cursor']
            db.execute('UPDATE watchlist_versions SET cursor=? WHERE id=?',(cursor,rule['version_id']))
            db.execute('UPDATE watchlists SET last_run=? WHERE id=?',(r.now(),rule['id']))
            scanned+=len(rows)
        grouped=group_batch(db)
    return {'events_created':created,'evidence_scanned':scanned,'duplicate_records_scanned':grouped}


def group(identifier,db=None):
    positive_id(identifier)
    db=db or get_db();row=db.execute('SELECT * FROM duplicate_groups WHERE id=?',(identifier,)).fetchone()
    if row is None:raise r.ResearchMissing('重複グループが見つかりません。')
    return row


def toggle_group(identifier,body):
    values=r.fields(body,{'suppressed'})
    if type(values.get('suppressed')) is not bool:raise ValueError('suppressed は boolean です。')
    with e.storage_lock(),r.transaction() as db:
        group(identifier,db);db.execute('UPDATE duplicate_groups SET suppressed=?,updated_at=? WHERE id=?',(int(values['suppressed']),r.now(),identifier))


def date(value):
    try:
        if datetime.strptime(value,'%Y-%m-%d').strftime('%Y-%m-%d')!=value:raise ValueError()
    except (ValueError,TypeError):raise ValueError('日付は実在する UTC YYYY-MM-DD です。') from None
    return value

EVENT_SQL='''SELECT x.*,w.workspace_id,w.name AS watchlist_name,w.id AS watchlist_id,v.revision,e.title,e.publisher,e.version AS evidence_version,e.article_id
 FROM watch_events x JOIN watchlist_versions v ON v.id=x.version_id JOIN watchlists w ON w.id=v.watchlist_id JOIN evidence e ON e.id=x.evidence_id'''
