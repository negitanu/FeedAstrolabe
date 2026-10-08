"""Deterministic identifiers and reviewed originals; no DNS or outbound access."""
import ipaddress,json,re,secrets,unicodedata
import idna
from urllib.parse import urlsplit
from .db import get_db
from . import evidence as e,research as r,triage as t

VERSION='rules-v1-idna2008-uts46'
IDENTIFIERS={'cve','domain','ip','asn','hash','repository'}
NAMES={'organization','product','model'}
KINDS=IDENTIFIERS|NAMES
LABELS={'fact','source-claim','hypothesis'}
CONFIDENCE={'unknown','low','medium','high'}
PATTERNS=[
 ('cve',re.compile(r'(?<![\w-])CVE-\d{4}-\d{4,32}(?![\w-])',re.I)),
 ('repository',re.compile(r'https?://github\.com/[a-z0-9-]{1,39}/[a-z0-9_.-]{1,100}(?![\w.-])',re.I)),
 ('asn',re.compile(r'(?<!\w)AS\d{1,10}(?!\w)',re.I)),
 ('hash',re.compile(r'(?<!\w)(?:[a-f0-9]{64}|[a-f0-9]{40}|[a-f0-9]{32})(?!\w)',re.I)),
 ('ip',re.compile(r'(?<![\w.])(?:[0-9]{1,3}\.){3}[0-9]{1,3}(?!\w|\.[0-9])')),
 ('ip',re.compile(r'(?<![\w:])(?:[a-f0-9]{0,4}:){2,7}[a-f0-9:.]{0,39}(?![\w:%])',re.I)),
 ('domain',re.compile(r'(?<![\w.-])(?:[\w-]{1,63}\.){1,10}(?:[a-z]{2,63}|xn--[a-z0-9-]{1,59})\.?(?![\w.-])',re.I)),
]
RELATION_SQL='''SELECT a.*,v.id AS version_id,v.source_id,v.target_id,v.predicate,v.quotation_id,v.label,v.confidence,v.author,v.observed_at,v.valid_from,v.valid_to,v.archived,v.recorded_at,q.evidence_id,q.start,q.end,q.quote,q.text_hash
 FROM relations a JOIN relation_versions v ON v.relation_id=a.id AND v.revision=a.revision JOIN quotations q ON q.id=v.quotation_id'''


def normalize(kind,value):
    if not isinstance(kind,str) or kind not in KINDS or not isinstance(value,str) or not 1<=len(value)<=253 or any(ord(c)<32 for c in value):raise ValueError('対象の種類・表記が不正です。')
    value=value.strip()
    if not value:raise ValueError('対象の表記が空です。')
    if kind in NAMES:return unicodedata.normalize('NFKC',value).casefold()
    if kind=='cve':
        if not re.fullmatch(r'CVE-[0-9]{4}-[0-9]{4,32}',value,re.I):raise ValueError('CVE の形式が不正です。')
        return value.upper()
    if kind=='ip':
        if '%' in value or '/' in value:raise ValueError('IP は zone／network prefix なしで指定します。')
        try:return ipaddress.ip_address(value).compressed
        except ValueError:raise ValueError('IP アドレスが不正です。') from None
    if kind=='asn':
        if not re.fullmatch(r'AS[0-9]{1,10}',value,re.I) or int(value[2:])>4294967295:raise ValueError('ASN が不正です。')
        return 'AS'+str(int(value[2:]))
    if kind=='hash':
        if not re.fullmatch(r'(?:[a-f0-9]{32}|[a-f0-9]{40}|[a-f0-9]{64})',value,re.I):raise ValueError('ハッシュ表記が不正です。')
        return value.lower()
    if kind=='repository':
        if not value.lower().startswith(('https://','http://')):value='https://'+value
        try:parts=urlsplit(value)
        except ValueError:raise ValueError('repository URL が不正です。') from None
        if parts.scheme not in ('http','https') or parts.netloc.lower()!='github.com' or parts.query or parts.fragment or parts.username:raise ValueError('GitHub の owner/repo URL を指定してください。')
        path=parts.path.strip('/')
        if path.lower().endswith('.git'):path=path[:-4]
        if not re.fullmatch(r'[a-z0-9-]{1,39}/[a-z0-9_.-]{1,100}',path,re.I) or any(part in ('.','..') for part in path.split('/')):raise ValueError('owner/repo が不正です。')
        return 'github.com/'+path.lower()
    try:canonical=idna.encode(value[:-1] if value.endswith('.') else value,uts46=True,std3_rules=True,transitional=False).decode('ascii').lower()
    except UnicodeError:raise ValueError('IDNA domain が不正です。') from None
    labels=canonical.split('.')
    if len(canonical)>253 or len(labels)<2 or any(not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?',part) for part in labels) or not re.fullmatch(r'(?:[a-z]{2,63}|xn--[a-z0-9-]{1,59})',labels[-1]):raise ValueError('domain のラベルが不正です。')
    try:
        if idna.encode(idna.decode(canonical),uts46=True,std3_rules=True,transitional=False).decode()!=canonical:raise ValueError()
    except (UnicodeError,ValueError):raise ValueError('IDNA の往復検証に失敗しました。') from None
    return canonical


def find(identifier,db=None):
    t.positive_id(identifier)
    row=(db or get_db()).execute('SELECT * FROM entities WHERE id=?',(identifier,)).fetchone()
    if row is None:raise r.ResearchMissing('対象が見つかりません。')
    return row


def root(identifier,db=None):
    db=db or get_db();visited=set()
    for _ in range(21):
        if identifier in visited:raise r.ResearchConflict('統合参照が循環しています。')
        visited.add(identifier);item=find(identifier,db)
        if item['merged_into'] is None:return item['id']
        identifier=item['merged_into']
    raise r.ResearchConflict('統合の深さ上限を超えています。')


def family(identifier,db=None):
    db=db or get_db();identifier=root(identifier,db)
    rows=db.execute('''WITH RECURSIVE family(id,depth) AS (SELECT ?,0 UNION ALL SELECT e.id,f.depth+1 FROM entities e JOIN family f ON e.merged_into=f.id WHERE f.depth<20) SELECT id FROM family LIMIT 501''',(identifier,)).fetchall()
    return [row[0] for row in rows[:500]],len(rows)>500


def audit(db,kind,entity_ids,details,author='local-user',workspace_id=None,evidence_id=None,observed_at=None):
    identifier=db.execute('INSERT INTO entity_audit(kind,details,author,workspace_id,evidence_id,observed_at,recorded_at) VALUES(?,?,?,?,?,?,?)',(kind,json.dumps(details,ensure_ascii=False),author,workspace_id,evidence_id,observed_at,r.now())).lastrowid
    db.executemany('INSERT INTO entity_audit_entities(audit_id,entity_id) VALUES(?,?)',[(identifier,x) for x in set(entity_ids)])
    return identifier


def ensure(db,kind,value,display_name=None):
    canonical=normalize(kind,value);identity=canonical if kind in IDENTIFIERS else secrets.token_hex(16)
    old=db.execute('SELECT id FROM entities WHERE kind=? AND identity=?',(kind,identity)).fetchone()
    if old:return old[0]
    display_name=r.text(display_name if display_name is not None else value,'display_name',253,True)
    stamp=r.now()
    return db.execute('INSERT INTO entities(kind,identity,canonical,display_name,created_at,updated_at) VALUES(?,?,?,?,?,?)',(kind,identity,canonical,display_name,stamp,stamp)).lastrowid


def create(body):
    values=r.fields(body,{'kind','value','display_name','author'})
    normalize(values.get('kind'),values.get('value'))
    if 'display_name' in values:r.text(values['display_name'],'display_name',253,True)
    author=r.text(values.get('author','local-user'),'author',100,True)
    with e.storage_lock(),r.transaction() as db:
        identifier=ensure(db,values['kind'],values['value'],values.get('display_name'))
        audit(db,'entity-created',[identifier],{'kind':values['kind'],'value':values['value']},author)
    return identifier


def alias(identifier,body):
    values=r.fields(body,{'value','reviewed','author'})
    value=r.text(values.get('value'),'value',200,True);author=r.text(values.get('author','local-user'),'author',100,True)
    if type(values.get('reviewed')) is not bool:raise ValueError('reviewed は明示的な boolean です。')
    normalized=unicodedata.normalize('NFKC',value).casefold()
    with e.storage_lock(),r.transaction() as db:
        find(identifier,db)
        old=db.execute('SELECT * FROM entity_aliases WHERE entity_id=? AND normalized=?',(identifier,normalized)).fetchone()
        if old:
            if old['reviewed']!=int(values['reviewed']):
                db.execute('UPDATE entity_aliases SET reviewed=?,author=? WHERE id=?',(int(values['reviewed']),author,old['id']))
                audit(db,'alias-reviewed',[identifier],{'alias_id':old['id'],'before':bool(old['reviewed']),'after':values['reviewed']},author)
            return old['id']
        if db.execute('SELECT count(*) FROM entity_aliases WHERE entity_id=?',(identifier,)).fetchone()[0]>=100:raise ValueError('別名は対象ごとに100件までです。')
        aid=db.execute('INSERT INTO entity_aliases(entity_id,value,normalized,reviewed,author,created_at) VALUES(?,?,?,?,?,?)',(identifier,value,normalized,int(values['reviewed']),author,r.now())).lastrowid
        audit(db,'alias-added',[identifier],{'alias_id':aid,'value':value,'reviewed':values['reviewed']},author)
    return aid


def anchor(db,evidence_id,start,end,original):
    if type(start) is not int or type(end) is not int or not 0<=start<end<=160000 or not isinstance(original,str) or len(original)>253:raise ValueError('表記と文字位置が不正です。')
    item=e.find(evidence_id,db)
    if end>len(item['text']) or item['text'][start:end]!=original or e.digest(item['text'].encode())!=item['text_hash']:raise ValueError('表記の位置と固定本文が一致しません。')
    e.read_blob(item['blob_hash'],item['size'])
    return item


def mention(identifier,db=None):
    t.positive_id(identifier);row=(db or get_db()).execute('SELECT * FROM entity_mentions WHERE id=?',(identifier,)).fetchone()
    if row is None:raise r.ResearchMissing('言及が見つかりません。')
    return row


def add_mention(body):
    values=r.fields(body,{'entity_id','evidence_id','start','end','original','status','author'})
    author=r.text(values.get('author','local-user'),'author',100,True);status=values.get('status','confirmed')
    if not isinstance(status,str) or status not in ('candidate','confirmed','rejected'):raise ValueError('言及の状態が不正です。')
    with e.storage_lock(),r.transaction() as db:
        entity=find(values.get('entity_id'),db);item=anchor(db,values.get('evidence_id'),values.get('start'),values.get('end'),values.get('original'))
        if db.execute('SELECT count(*) FROM entity_mentions WHERE evidence_id=?',(item['id'],)).fetchone()[0]>=500:raise ValueError('根拠ごとの言及は500件までです。')
        old=db.execute('SELECT id FROM entity_mentions WHERE evidence_id=? AND start=? AND end=? AND extracted_kind=?',(item['id'],values['start'],values['end'],entity['kind'])).fetchone()
        if old:raise r.ResearchConflict('同じ位置の言及は既存記録を訂正してください。')
        stamp=r.now();mid=db.execute('INSERT INTO entity_mentions(evidence_id,original_entity_id,entity_id,extracted_kind,text_hash,start,end,original,normalization,method,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(item['id'],entity['id'],entity['id'],entity['kind'],item['text_hash'],values['start'],values['end'],values['original'],VERSION,'manual',status,stamp,stamp)).lastrowid
        audit(db,'mention-added',[entity['id']],{'mention_id':mid,'original':values['original'],'start':values['start'],'end':values['end'],'status':status},author,evidence_id=item['id'],observed_at=item['observed_at'])
    return mid


def correct_mention(identifier,body):
    values=r.fields(body,{'expected_revision','entity_id','status','author'})
    author=r.text(values.get('author','local-user'),'author',100,True)
    t.positive_id(values.get('expected_revision'))
    with e.storage_lock(),r.transaction() as db:
        old=mention(identifier,db)
        if type(values.get('expected_revision')) is not int or values['expected_revision']!=old['revision']:raise r.ResearchConflict('言及の版が更新されています。')
        entity_id=values.get('entity_id',old['entity_id']);find(entity_id,db)
        status=values.get('status',old['status'])
        if not isinstance(status,str) or status not in ('candidate','confirmed','rejected'):raise ValueError('言及の状態が不正です。')
        db.execute('UPDATE entity_mentions SET entity_id=?,status=?,revision=revision+1,updated_at=? WHERE id=?',(entity_id,status,r.now(),identifier))
        audit(db,'mention-corrected',[old['entity_id'],entity_id],{'mention_id':identifier,'before':{'entity_id':old['entity_id'],'status':old['status'],'revision':old['revision']},'after':{'entity_id':entity_id,'status':status,'revision':old['revision']+1}},author,evidence_id=old['evidence_id'])


def extract_one(db,item):
    if db.execute('SELECT 1 FROM entity_extractions WHERE evidence_id=? AND normalization=?',(item['id'],VERSION)).fetchone():return 0
    if e.digest(item['text'].encode())!=item['text_hash']:raise ValueError('抽出対象の本文ハッシュが不正です。')
    e.read_blob(item['blob_hash'],item['size'])
    existing_count=db.execute('SELECT count(*) FROM entity_mentions WHERE evidence_id=?',(item['id'],)).fetchone()[0]
    total=0;attempts=0;truncated=False
    for kind,pattern in PATTERNS:
        for match in pattern.finditer(item['text']):
            attempts+=1
            if existing_count+total>=500 or attempts>2000:truncated=True;break
            original=match.group();end=match.end()
            if kind=='ip':trimmed=original.rstrip('.');end-=len(original)-len(trimmed);original=trimmed
            try:normalize(kind,original)
            except ValueError:continue
            # Human correction and rejection survive explicit extraction retries.
            old=db.execute('SELECT 1 FROM entity_mentions WHERE evidence_id=? AND start=? AND end=? AND extracted_kind=?',(item['id'],match.start(),end,kind)).fetchone()
            if old:continue
            identifier=ensure(db,kind,original);stamp=r.now()
            mid=db.execute('INSERT INTO entity_mentions(evidence_id,original_entity_id,entity_id,extracted_kind,text_hash,start,end,original,normalization,method,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(item['id'],identifier,identifier,kind,item['text_hash'],match.start(),end,original,VERSION,'auto',stamp,stamp)).lastrowid
            audit(db,'mention-extracted',[identifier],{'mention_id':mid,'original':original,'start':match.start(),'end':end,'normalization':VERSION},'rules-v1',evidence_id=item['id'],observed_at=item['observed_at']);total+=1
        if truncated:break
    db.execute('INSERT OR REPLACE INTO entity_extractions(evidence_id,normalization,truncated,created_at) VALUES(?,?,?,?)',(item['id'],VERSION,int(truncated),r.now()))
    return total


def extract(identifier=None,reprocess=False):
    with e.storage_lock(),r.transaction() as db:
        if identifier is not None:
            item=e.find(identifier,db)
            if reprocess:db.execute('DELETE FROM entity_extractions WHERE evidence_id=?',(identifier,))
            rows=[item]
        else:
            cursor=db.execute('SELECT cursor FROM entity_state WHERE id=1').fetchone()[0]
            rows=db.execute('SELECT e.*,b.size FROM evidence e JOIN evidence_blobs b ON b.hash=e.blob_hash WHERE e.id>? ORDER BY e.id LIMIT 20',(cursor,)).fetchall()
        count=sum(extract_one(db,item) for item in rows)
        if identifier is None and rows:db.execute('UPDATE entity_state SET cursor=? WHERE id=1',(rows[-1]['id'],))
    return {'evidence_scanned':len(rows),'mentions_created':count}


def merge(identifier,body,undo=False):
    allowed={'expected_revision','reason','author'}|({'target_id','reviewed'} if not undo else set())
    values=r.fields(body,allowed);t.positive_id(values.get('expected_revision'));reason=r.text(values.get('reason'),'reason',500,True);author=r.text(values.get('author','local-user'),'author',100,True)
    with e.storage_lock(),r.transaction() as db:
        source=find(identifier,db)
        if type(values.get('expected_revision')) is not int or values['expected_revision']!=source['revision']:raise r.ResearchConflict('対象の版が更新されています。')
        previous=source['merged_into']
        if undo:
            if previous is None:raise r.ResearchConflict('この対象は統合されていません。')
            target=None;ids=[identifier,previous]
        else:
            target=find(values.get('target_id'),db)
            if values.get('reviewed') is not True:raise ValueError('統合の手動確認 reviewed=true が必要です。')
            if source['kind']!=target['kind'] or target['id']==identifier:raise ValueError('統合は異なるIDの同じ種類だけです。')
            if source['merged_into'] is not None or target['merged_into'] is not None:raise r.ResearchConflict('統合元・先は未統合の代表対象を選んでください。')
            depth=db.execute('''WITH RECURSIVE children(id,depth) AS (SELECT ?,0 UNION ALL SELECT x.id,c.depth+1 FROM entities x JOIN children c ON x.merged_into=c.id WHERE c.depth<20) SELECT max(depth) FROM children''',(identifier,)).fetchone()[0]
            if depth>=20:raise ValueError('統合参照の深さは20までです。')
            ids=[identifier,target['id']]
        target_id=target['id'] if target is not None else None
        db.execute('UPDATE entities SET merged_into=?,revision=revision+1,updated_at=? WHERE id=?',(target_id,r.now(),identifier))
        audit(db,'entity-unmerged' if undo else 'entity-merged',ids,{'source_id':identifier,'before':previous,'after':target_id,'reason':reason,'revision':source['revision']+1},author)


def relation(identifier,db=None):
    t.positive_id(identifier);row=(db or get_db()).execute(RELATION_SQL+' WHERE a.id=?',(identifier,)).fetchone()
    if row is None:raise r.ResearchMissing('関係の記録が見つかりません。')
    return row


def timestamp(value):
    from datetime import datetime
    if value is None:return None
    try:
        if not isinstance(value,str) or datetime.strptime(value,'%Y-%m-%d %H:%M:%S').strftime('%Y-%m-%d %H:%M:%S')!=value:raise ValueError()
    except ValueError:raise ValueError('日時は実在する UTC YYYY-MM-DD HH:MM:SS または null です。') from None
    return value


def save_relation(workspace_id,body,identifier=None):
    allowed={'source_id','target_id','predicate','quotation_id','label','confidence','author','observed_at','valid_from','valid_to','archived'}
    values=r.fields(body,allowed|({'expected_revision'} if identifier is not None else set()))
    if identifier is not None:t.positive_id(values.get('expected_revision'))
    with e.storage_lock(),r.transaction() as db:
        r.editable(workspace_id,db);old=relation(identifier,db) if identifier is not None else None
        if old and old['workspace_id']!=workspace_id:raise r.ResearchMissing('関係がこの案件にありません。')
        if old and (type(values.get('expected_revision')) is not int or values['expected_revision']!=old['revision']):raise r.ResearchConflict('関係の版が更新されています。')
        def val(name,default=None):return values.get(name,old[name] if old else default)
        source_id=val('source_id');target_id=val('target_id');find(source_id,db);find(target_id,db)
        predicate=r.text(val('predicate'),'predicate',80,True);author=r.text(val('author','local-user'),'author',100,True)
        quotation_id=val('quotation_id');t.positive_id(quotation_id)
        quote=db.execute('SELECT * FROM quotations WHERE id=?',(quotation_id,)).fetchone()
        if quote is None:raise r.ResearchMissing('引用が見つかりません。')
        if quote['workspace_id']!=workspace_id:raise ValueError('引用は同じ案件から選んでください。')
        item=e.find(quote['evidence_id'],db)
        if quote['text_hash']!=item['text_hash'] or e.digest(item['text'].encode())!=item['text_hash'] or item['text'][quote['start']:quote['end']]!=quote['quote']:raise ValueError('引用の固定本文が不正です。')
        e.read_blob(item['blob_hash'],item['size'])
        label=val('label','source-claim');confidence=val('confidence','unknown');archived=values.get('archived',bool(old['archived']) if old else False)
        if not isinstance(label,str) or label not in LABELS or not isinstance(confidence,str) or confidence not in CONFIDENCE or type(archived) is not bool:raise ValueError('評価・確度・アーカイブが不正です。')
        dates={name:timestamp(val(name)) for name in ['observed_at','valid_from','valid_to']}
        if dates['valid_from'] and dates['valid_to'] and dates['valid_from']>dates['valid_to']:raise ValueError('有効期間の終了は開始以降です。')
        stamp=r.now();revision=old['revision']+1 if old else 1
        if old:db.execute('UPDATE relations SET revision=?,updated_at=? WHERE id=?',(revision,stamp,identifier))
        else:identifier=db.execute('INSERT INTO relations(workspace_id,created_at,updated_at) VALUES(?,?,?)',(workspace_id,stamp,stamp)).lastrowid
        db.execute('INSERT INTO relation_versions(relation_id,revision,source_id,target_id,predicate,quotation_id,label,confidence,author,observed_at,valid_from,valid_to,archived,recorded_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(identifier,revision,source_id,target_id,predicate,quotation_id,label,confidence,author,dates['observed_at'],dates['valid_from'],dates['valid_to'],int(archived),stamp))
        details={'relation_id':identifier,'revision':revision,'source_id':source_id,'target_id':target_id,'predicate':predicate,'quotation_id':quotation_id,'label':label,'confidence':confidence,**dates,'archived':archived}
        audit(db,'relation-edited' if old else 'relation-added',[source_id,target_id],details,author,workspace_id,item['id'],dates['observed_at'])
    return identifier


def workspace_clause(identifier,entity_column='x.id'):
    # A filtered entity is backed by associated evidence, an asserted relation, or its audit.
    r.find('workspace',identifier)
    members=f'(WITH RECURSIVE members(id,depth) AS (SELECT {entity_column},0 UNION ALL SELECT child.id,m.depth+1 FROM entities child JOIN members m ON child.merged_into=m.id WHERE m.depth<20) SELECT id FROM members LIMIT 500)'
    return f'''(EXISTS(SELECT 1 FROM entity_mentions m JOIN evidence e ON e.id=m.evidence_id WHERE (m.entity_id IN {members} OR m.original_entity_id IN {members}) AND {t.SCOPE})
     OR EXISTS(SELECT 1 FROM relations a JOIN relation_versions v ON v.relation_id=a.id WHERE a.workspace_id=? AND (v.source_id IN {members} OR v.target_id IN {members}))
     OR EXISTS(SELECT 1 FROM entity_audit z JOIN entity_audit_entities az ON az.audit_id=z.id WHERE z.workspace_id=? AND az.entity_id IN {members}))''',[identifier]*7



def audit_record(row):
    item=dict(row);item['details']=json.loads(item['details']);return item


def graph(identifier,workspace_id=None,depth=2,limit=200):
    if type(depth) is not int or not 0<=depth<=2 or type(limit) is not int or not 1<=limit<=200:raise ValueError('グラフはdepth0〜2、limit1〜200です。')
    db=get_db();find(identifier,db)
    if workspace_id is not None:
        clause,params=workspace_clause(workspace_id)
        if not db.execute('SELECT 1 FROM entities x WHERE x.id=? AND '+clause,[identifier]+params).fetchone():raise r.ResearchMissing('対象がこの案件の根拠にありません。')
    family_ids,family_truncated=family(identifier,db)
    nodes={identifier:dict(find(identifier,db))};edges={};frontier={identifier}|set(x for x in family_ids[:199] if x!=identifier);truncated=family_truncated or len(family_ids)>200
    for _ in range(depth):
        if not frontier:break
        placeholders=','.join('?' for _ in frontier)
        sql=RELATION_SQL+f' WHERE v.archived=0 AND (v.source_id IN ({placeholders}) OR v.target_id IN ({placeholders}))'
        params=list(frontier)*2
        if workspace_id is not None:sql+=' AND a.workspace_id=?';params.append(workspace_id)
        rows=db.execute(sql+' ORDER BY a.id DESC LIMIT 401',params).fetchall()
        if len(rows)>400:truncated=True
        next_frontier=set()
        for row in rows[:400]:
            pair=[row['source_id'],row['target_id']];new=[x for x in pair if x not in nodes]
            if len(nodes)+len(set(new))>limit or (row['id'] not in edges and len(edges)>=400):truncated=True;continue
            edges[row['id']]=r.record(row)
            for entity_id in pair:
                if entity_id not in nodes:
                    nodes[entity_id]=dict(find(entity_id,db));next_frontier.add(entity_id)
        frontier=next_frontier
    return {'nodes':list(nodes.values()),'edges':list(edges.values()),'truncated':truncated,'depth':depth,'node_limit':limit,'edge_limit':400,'inference':'Only manually assessed, quoted assertions; no inferred ownership'}
