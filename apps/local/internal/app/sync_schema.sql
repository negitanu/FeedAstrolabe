CREATE TABLE IF NOT EXISTS sync_meta(id INTEGER PRIMARY KEY CHECK(id=1),clock INTEGER NOT NULL DEFAULT 0,applying INTEGER NOT NULL DEFAULT 0,initialized INTEGER NOT NULL DEFAULT 0);
INSERT OR IGNORE INTO sync_meta(id) VALUES(1);
CREATE TABLE IF NOT EXISTS sync_events(seq INTEGER PRIMARY KEY AUTOINCREMENT,event_id TEXT NOT NULL UNIQUE,clock INTEGER NOT NULL,kind TEXT NOT NULL,entity_key TEXT NOT NULL,value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS sync_versions(kind TEXT NOT NULL,entity_key TEXT NOT NULL,clock INTEGER NOT NULL,event_id TEXT NOT NULL,value TEXT NOT NULL,PRIMARY KEY(kind,entity_key));
CREATE INDEX IF NOT EXISTS sync_versions_parent ON sync_versions(kind,json_extract(entity_key,'$[0]'));
CREATE TABLE IF NOT EXISTS sync_connection(id INTEGER PRIMARY KEY CHECK(id=1),url TEXT NOT NULL DEFAULT '',enabled INTEGER NOT NULL DEFAULT 0,cursor INTEGER NOT NULL DEFAULT 0,sent INTEGER NOT NULL DEFAULT 0,hub TEXT NOT NULL DEFAULT '',last_success TEXT NOT NULL DEFAULT '',error TEXT NOT NULL DEFAULT '');
INSERT OR IGNORE INTO sync_connection(id) VALUES(1);
CREATE TABLE IF NOT EXISTS sync_feed_meta(feed_id INTEGER PRIMARY KEY REFERENCES feeds(id) ON DELETE CASCADE,source TEXT NOT NULL,kind TEXT NOT NULL,target TEXT NOT NULL,origin TEXT NOT NULL,interval INTEGER NOT NULL);
CREATE TRIGGER IF NOT EXISTS sync_feed_insert AFTER INSERT ON feeds WHEN (SELECT applying FROM sync_meta WHERE id=1)=0 AND (1) BEGIN
UPDATE sync_meta SET clock=clock+1 WHERE id=1;
INSERT INTO sync_events(event_id,clock,kind,entity_key,value) VALUES(lower(hex(randomblob(16))),(SELECT clock FROM sync_meta WHERE id=1),'feed',json_array(NEW.url),json_object('title',NEW.title,'folder',COALESCE((SELECT name FROM folders WHERE id=NEW.folder_id),''),'enabled',1-NEW.paused,'source',COALESCE((SELECT source FROM sync_feed_meta WHERE feed_id=NEW.id),'rss'),'kind',COALESCE((SELECT kind FROM sync_feed_meta WHERE feed_id=NEW.id),''),'target',COALESCE((SELECT target FROM sync_feed_meta WHERE feed_id=NEW.id),''),'origin',COALESCE((SELECT origin FROM sync_feed_meta WHERE feed_id=NEW.id),''),'interval',COALESCE((SELECT interval FROM sync_feed_meta WHERE feed_id=NEW.id),(SELECT json_extract(value,'$.interval')*60 FROM settings WHERE id=1))));
INSERT INTO sync_versions SELECT kind,entity_key,clock,event_id,value FROM sync_events WHERE seq=last_insert_rowid() ON CONFLICT(kind,entity_key) DO UPDATE SET clock=excluded.clock,event_id=excluded.event_id,value=excluded.value;
END;
CREATE TRIGGER IF NOT EXISTS sync_feed_update AFTER UPDATE OF title,folder_id,paused ON feeds WHEN (SELECT applying FROM sync_meta WHERE id=1)=0 AND (NEW.title IS NOT OLD.title OR NEW.folder_id IS NOT OLD.folder_id OR NEW.paused IS NOT OLD.paused) BEGIN
UPDATE sync_meta SET clock=clock+1 WHERE id=1;
INSERT INTO sync_events(event_id,clock,kind,entity_key,value) VALUES(lower(hex(randomblob(16))),(SELECT clock FROM sync_meta WHERE id=1),'feed',json_array(NEW.url),json_object('title',NEW.title,'folder',COALESCE((SELECT name FROM folders WHERE id=NEW.folder_id),''),'enabled',1-NEW.paused,'source',COALESCE((SELECT source FROM sync_feed_meta WHERE feed_id=NEW.id),'rss'),'kind',COALESCE((SELECT kind FROM sync_feed_meta WHERE feed_id=NEW.id),''),'target',COALESCE((SELECT target FROM sync_feed_meta WHERE feed_id=NEW.id),''),'origin',COALESCE((SELECT origin FROM sync_feed_meta WHERE feed_id=NEW.id),''),'interval',COALESCE((SELECT interval FROM sync_feed_meta WHERE feed_id=NEW.id),(SELECT json_extract(value,'$.interval')*60 FROM settings WHERE id=1))));
INSERT INTO sync_versions SELECT kind,entity_key,clock,event_id,value FROM sync_events WHERE seq=last_insert_rowid() ON CONFLICT(kind,entity_key) DO UPDATE SET clock=excluded.clock,event_id=excluded.event_id,value=excluded.value;
END;
CREATE TRIGGER IF NOT EXISTS sync_feed_delete AFTER DELETE ON feeds WHEN (SELECT applying FROM sync_meta WHERE id=1)=0 AND (1) BEGIN
UPDATE sync_meta SET clock=clock+1 WHERE id=1;
INSERT INTO sync_events(event_id,clock,kind,entity_key,value) VALUES(lower(hex(randomblob(16))),(SELECT clock FROM sync_meta WHERE id=1),'delete',json_array(OLD.url),json_object());
INSERT INTO sync_versions SELECT kind,entity_key,clock,event_id,value FROM sync_events WHERE seq=last_insert_rowid() ON CONFLICT(kind,entity_key) DO UPDATE SET clock=excluded.clock,event_id=excluded.event_id,value=excluded.value;
END;
CREATE TRIGGER IF NOT EXISTS sync_feed_url AFTER UPDATE OF url ON feeds WHEN (SELECT applying FROM sync_meta WHERE id=1)=0 AND (NEW.url IS NOT OLD.url) BEGIN
UPDATE sync_meta SET clock=clock+1 WHERE id=1;
INSERT INTO sync_events(event_id,clock,kind,entity_key,value) VALUES(lower(hex(randomblob(16))),(SELECT clock FROM sync_meta WHERE id=1),'delete',json_array(OLD.url),json_object());
INSERT INTO sync_versions SELECT kind,entity_key,clock,event_id,value FROM sync_events WHERE seq=last_insert_rowid() ON CONFLICT(kind,entity_key) DO UPDATE SET clock=excluded.clock,event_id=excluded.event_id,value=excluded.value;
END;
CREATE TRIGGER IF NOT EXISTS sync_feed_new_url AFTER UPDATE OF url ON feeds WHEN (SELECT applying FROM sync_meta WHERE id=1)=0 AND (NEW.url IS NOT OLD.url) BEGIN
UPDATE sync_meta SET clock=clock+1 WHERE id=1;
INSERT INTO sync_events(event_id,clock,kind,entity_key,value) VALUES(lower(hex(randomblob(16))),(SELECT clock FROM sync_meta WHERE id=1),'feed',json_array(NEW.url),json_object('title',NEW.title,'folder',COALESCE((SELECT name FROM folders WHERE id=NEW.folder_id),''),'enabled',1-NEW.paused,'source',COALESCE((SELECT source FROM sync_feed_meta WHERE feed_id=NEW.id),'rss'),'kind',COALESCE((SELECT kind FROM sync_feed_meta WHERE feed_id=NEW.id),''),'target',COALESCE((SELECT target FROM sync_feed_meta WHERE feed_id=NEW.id),''),'origin',COALESCE((SELECT origin FROM sync_feed_meta WHERE feed_id=NEW.id),''),'interval',COALESCE((SELECT interval FROM sync_feed_meta WHERE feed_id=NEW.id),(SELECT json_extract(value,'$.interval')*60 FROM settings WHERE id=1))));
INSERT INTO sync_versions SELECT kind,entity_key,clock,event_id,value FROM sync_events WHERE seq=last_insert_rowid() ON CONFLICT(kind,entity_key) DO UPDATE SET clock=excluded.clock,event_id=excluded.event_id,value=excluded.value;
END;
CREATE TRIGGER IF NOT EXISTS sync_collection AFTER UPDATE OF last_fetched,last_error ON feeds WHEN (SELECT applying FROM sync_meta WHERE id=1)=0 AND (NEW.last_fetched IS NOT OLD.last_fetched OR NEW.last_error IS NOT OLD.last_error) BEGIN
UPDATE sync_meta SET clock=clock+1 WHERE id=1;
INSERT INTO sync_events(event_id,clock,kind,entity_key,value) VALUES(lower(hex(randomblob(16))),(SELECT clock FROM sync_meta WHERE id=1),'collection',json_array(NEW.url),json_object('checked',COALESCE(NEW.last_fetched,''),'error',COALESCE(NEW.last_error,'')));
INSERT INTO sync_versions SELECT kind,entity_key,clock,event_id,value FROM sync_events WHERE seq=last_insert_rowid() ON CONFLICT(kind,entity_key) DO UPDATE SET clock=excluded.clock,event_id=excluded.event_id,value=excluded.value;
END;
CREATE TRIGGER IF NOT EXISTS sync_article_insert AFTER INSERT ON articles WHEN (SELECT applying FROM sync_meta WHERE id=1)=0 AND (1) BEGIN
UPDATE sync_meta SET clock=clock+1 WHERE id=1;
INSERT INTO sync_events(event_id,clock,kind,entity_key,value) VALUES(lower(hex(randomblob(16))),(SELECT clock FROM sync_meta WHERE id=1),'article',json_array((SELECT url FROM feeds WHERE id=NEW.feed_id),NEW.uid),json_object('title',NEW.title,'url',NEW.url,'content',NEW.content,'published',NEW.published,'collected',NEW.collected));
INSERT INTO sync_versions SELECT kind,entity_key,clock,event_id,value FROM sync_events WHERE seq=last_insert_rowid() ON CONFLICT(kind,entity_key) DO UPDATE SET clock=excluded.clock,event_id=excluded.event_id,value=excluded.value;
END;
CREATE TRIGGER IF NOT EXISTS sync_article_update AFTER UPDATE OF title,url,content,published ON articles WHEN (SELECT applying FROM sync_meta WHERE id=1)=0 AND (NEW.title IS NOT OLD.title OR NEW.url IS NOT OLD.url OR NEW.content IS NOT OLD.content OR NEW.published IS NOT OLD.published) BEGIN
UPDATE sync_meta SET clock=clock+1 WHERE id=1;
INSERT INTO sync_events(event_id,clock,kind,entity_key,value) VALUES(lower(hex(randomblob(16))),(SELECT clock FROM sync_meta WHERE id=1),'article',json_array((SELECT url FROM feeds WHERE id=NEW.feed_id),NEW.uid),json_object('title',NEW.title,'url',NEW.url,'content',NEW.content,'published',NEW.published,'collected',NEW.collected));
INSERT INTO sync_versions SELECT kind,entity_key,clock,event_id,value FROM sync_events WHERE seq=last_insert_rowid() ON CONFLICT(kind,entity_key) DO UPDATE SET clock=excluded.clock,event_id=excluded.event_id,value=excluded.value;
END;
CREATE TRIGGER IF NOT EXISTS sync_read_insert AFTER INSERT ON articles WHEN (SELECT applying FROM sync_meta WHERE id=1)=0 AND (NEW.is_read=1) BEGIN
UPDATE sync_meta SET clock=clock+1 WHERE id=1;
INSERT INTO sync_events(event_id,clock,kind,entity_key,value) VALUES(lower(hex(randomblob(16))),(SELECT clock FROM sync_meta WHERE id=1),'read',json_array((SELECT url FROM feeds WHERE id=NEW.feed_id),NEW.uid),json_object('value',NEW.is_read));
INSERT INTO sync_versions SELECT kind,entity_key,clock,event_id,value FROM sync_events WHERE seq=last_insert_rowid() ON CONFLICT(kind,entity_key) DO UPDATE SET clock=excluded.clock,event_id=excluded.event_id,value=excluded.value;
END;
CREATE TRIGGER IF NOT EXISTS sync_read_update AFTER UPDATE OF is_read ON articles WHEN (SELECT applying FROM sync_meta WHERE id=1)=0 AND (1) BEGIN
UPDATE sync_meta SET clock=clock+1 WHERE id=1;
INSERT INTO sync_events(event_id,clock,kind,entity_key,value) VALUES(lower(hex(randomblob(16))),(SELECT clock FROM sync_meta WHERE id=1),'read',json_array((SELECT url FROM feeds WHERE id=NEW.feed_id),NEW.uid),json_object('value',NEW.is_read));
INSERT INTO sync_versions SELECT kind,entity_key,clock,event_id,value FROM sync_events WHERE seq=last_insert_rowid() ON CONFLICT(kind,entity_key) DO UPDATE SET clock=excluded.clock,event_id=excluded.event_id,value=excluded.value;
END;
CREATE TRIGGER IF NOT EXISTS sync_star_insert AFTER INSERT ON articles WHEN (SELECT applying FROM sync_meta WHERE id=1)=0 AND (NEW.starred=1) BEGIN
UPDATE sync_meta SET clock=clock+1 WHERE id=1;
INSERT INTO sync_events(event_id,clock,kind,entity_key,value) VALUES(lower(hex(randomblob(16))),(SELECT clock FROM sync_meta WHERE id=1),'star',json_array((SELECT url FROM feeds WHERE id=NEW.feed_id),NEW.uid),json_object('value',NEW.starred));
INSERT INTO sync_versions SELECT kind,entity_key,clock,event_id,value FROM sync_events WHERE seq=last_insert_rowid() ON CONFLICT(kind,entity_key) DO UPDATE SET clock=excluded.clock,event_id=excluded.event_id,value=excluded.value;
END;
CREATE TRIGGER IF NOT EXISTS sync_star_update AFTER UPDATE OF starred ON articles WHEN (SELECT applying FROM sync_meta WHERE id=1)=0 AND (1) BEGIN
UPDATE sync_meta SET clock=clock+1 WHERE id=1;
INSERT INTO sync_events(event_id,clock,kind,entity_key,value) VALUES(lower(hex(randomblob(16))),(SELECT clock FROM sync_meta WHERE id=1),'star',json_array((SELECT url FROM feeds WHERE id=NEW.feed_id),NEW.uid),json_object('value',NEW.starred));
INSERT INTO sync_versions SELECT kind,entity_key,clock,event_id,value FROM sync_events WHERE seq=last_insert_rowid() ON CONFLICT(kind,entity_key) DO UPDATE SET clock=excluded.clock,event_id=excluded.event_id,value=excluded.value;
END;
CREATE TRIGGER IF NOT EXISTS sync_social_insert AFTER INSERT ON social_sources WHEN (SELECT applying FROM sync_meta WHERE id=1)=0 BEGIN INSERT INTO sync_feed_meta VALUES(NEW.feed_id,NEW.provider,CASE WHEN NEW.kind='account' THEN 'account' ELSE 'topic' END,NEW.target,NEW.origin,NEW.interval*60) ON CONFLICT(feed_id) DO UPDATE SET source=excluded.source,kind=excluded.kind,target=excluded.target,origin=excluded.origin,interval=excluded.interval; END;
CREATE TRIGGER IF NOT EXISTS sync_social_update AFTER UPDATE ON social_sources WHEN (SELECT applying FROM sync_meta WHERE id=1)=0 BEGIN INSERT INTO sync_feed_meta VALUES(NEW.feed_id,NEW.provider,CASE WHEN NEW.kind='account' THEN 'account' ELSE 'topic' END,NEW.target,NEW.origin,NEW.interval*60) ON CONFLICT(feed_id) DO UPDATE SET source=excluded.source,kind=excluded.kind,target=excluded.target,origin=excluded.origin,interval=excluded.interval; END;
CREATE TRIGGER IF NOT EXISTS sync_meta_insert AFTER INSERT ON sync_feed_meta WHEN (SELECT applying FROM sync_meta WHERE id=1)=0 AND (1) BEGIN
UPDATE sync_meta SET clock=clock+1 WHERE id=1;
INSERT INTO sync_events(event_id,clock,kind,entity_key,value) VALUES(lower(hex(randomblob(16))),(SELECT clock FROM sync_meta WHERE id=1),'feed',json_array((SELECT url FROM feeds WHERE id=NEW.feed_id)),(SELECT json_object('title',f.title,'folder',COALESCE((SELECT name FROM folders WHERE id=f.folder_id),''),'enabled',1-f.paused,'source',NEW.source,'kind',NEW.kind,'target',NEW.target,'origin',NEW.origin,'interval',NEW.interval) FROM feeds f WHERE f.id=NEW.feed_id));
INSERT INTO sync_versions SELECT kind,entity_key,clock,event_id,value FROM sync_events WHERE seq=last_insert_rowid() ON CONFLICT(kind,entity_key) DO UPDATE SET clock=excluded.clock,event_id=excluded.event_id,value=excluded.value;
END;
CREATE TRIGGER IF NOT EXISTS sync_meta_update AFTER UPDATE ON sync_feed_meta WHEN (SELECT applying FROM sync_meta WHERE id=1)=0 AND (NEW.source IS NOT OLD.source OR NEW.kind IS NOT OLD.kind OR NEW.target IS NOT OLD.target OR NEW.origin IS NOT OLD.origin OR NEW.interval IS NOT OLD.interval) BEGIN
UPDATE sync_meta SET clock=clock+1 WHERE id=1;
INSERT INTO sync_events(event_id,clock,kind,entity_key,value) VALUES(lower(hex(randomblob(16))),(SELECT clock FROM sync_meta WHERE id=1),'feed',json_array((SELECT url FROM feeds WHERE id=NEW.feed_id)),(SELECT json_object('title',f.title,'folder',COALESCE((SELECT name FROM folders WHERE id=f.folder_id),''),'enabled',1-f.paused,'source',NEW.source,'kind',NEW.kind,'target',NEW.target,'origin',NEW.origin,'interval',NEW.interval) FROM feeds f WHERE f.id=NEW.feed_id));
INSERT INTO sync_versions SELECT kind,entity_key,clock,event_id,value FROM sync_events WHERE seq=last_insert_rowid() ON CONFLICT(kind,entity_key) DO UPDATE SET clock=excluded.clock,event_id=excluded.event_id,value=excluded.value;
END;
CREATE TRIGGER IF NOT EXISTS sync_folder_rename AFTER UPDATE OF name ON folders WHEN NEW.name IS NOT OLD.name AND (SELECT applying FROM sync_meta WHERE id=1)=0 BEGIN UPDATE sync_meta SET clock=clock+1; INSERT INTO sync_events(event_id,clock,kind,entity_key,value) SELECT lower(hex(randomblob(16))),(SELECT clock FROM sync_meta),'feed',json_array(f.url),json_object('title',f.title,'folder',NEW.name,'enabled',1-f.paused,'source',COALESCE(m.source,'rss'),'kind',COALESCE(m.kind,''),'target',COALESCE(m.target,''),'origin',COALESCE(m.origin,''),'interval',COALESCE(m.interval,(SELECT json_extract(value,'$.interval')*60 FROM settings WHERE id=1))) FROM feeds f LEFT JOIN sync_feed_meta m ON m.feed_id=f.id WHERE f.folder_id=NEW.id; INSERT INTO sync_versions SELECT kind,entity_key,clock,event_id,value FROM sync_events WHERE clock=(SELECT clock FROM sync_meta) AND true ON CONFLICT(kind,entity_key) DO UPDATE SET clock=excluded.clock,event_id=excluded.event_id,value=excluded.value; END;
CREATE TRIGGER IF NOT EXISTS sync_global_collection AFTER UPDATE OF value ON settings WHEN (SELECT applying FROM sync_meta WHERE id=1)=0 AND (COALESCE(json_extract(NEW.value,'$.pauseCollection'),0) IS NOT COALESCE(json_extract(OLD.value,'$.pauseCollection'),0)) BEGIN
UPDATE sync_meta SET clock=clock+1 WHERE id=1;
INSERT INTO sync_events(event_id,clock,kind,entity_key,value) VALUES(lower(hex(randomblob(16))),(SELECT clock FROM sync_meta WHERE id=1),'polling',json_array(),json_object('value',CASE WHEN json_extract(NEW.value,'$.pauseCollection') THEN 0 ELSE 1 END));
INSERT INTO sync_versions SELECT kind,entity_key,clock,event_id,value FROM sync_events WHERE seq=last_insert_rowid() ON CONFLICT(kind,entity_key) DO UPDATE SET clock=excluded.clock,event_id=excluded.event_id,value=excluded.value;
END;
CREATE TRIGGER IF NOT EXISTS sync_rekey_articles AFTER UPDATE OF url ON feeds WHEN NEW.url IS NOT OLD.url AND (SELECT applying FROM sync_meta WHERE id=1)=0 BEGIN UPDATE sync_meta SET clock=clock+1;
INSERT INTO sync_events(event_id,clock,kind,entity_key,value) SELECT lower(hex(randomblob(16))),(SELECT clock FROM sync_meta),'article',json_array(NEW.url,a.uid),json_object('title',a.title,'url',a.url,'content',a.content,'published',a.published,'collected',a.collected) FROM articles a WHERE a.feed_id=NEW.id AND 1;
INSERT INTO sync_events(event_id,clock,kind,entity_key,value) SELECT lower(hex(randomblob(16))),(SELECT clock FROM sync_meta),'read',json_array(NEW.url,a.uid),json_object('value',1) FROM articles a WHERE a.feed_id=NEW.id AND a.is_read=1;
INSERT INTO sync_events(event_id,clock,kind,entity_key,value) SELECT lower(hex(randomblob(16))),(SELECT clock FROM sync_meta),'star',json_array(NEW.url,a.uid),json_object('value',1) FROM articles a WHERE a.feed_id=NEW.id AND a.starred=1;
INSERT INTO sync_versions SELECT kind,entity_key,clock,event_id,value FROM sync_events WHERE clock=(SELECT clock FROM sync_meta) AND true ON CONFLICT(kind,entity_key) DO UPDATE SET clock=excluded.clock,event_id=excluded.event_id,value=excluded.value; END;
CREATE TRIGGER IF NOT EXISTS sync_default_interval AFTER UPDATE OF value ON settings WHEN (SELECT applying FROM sync_meta WHERE id=1)=0 AND (json_extract(NEW.value,'$.interval') IS NOT json_extract(OLD.value,'$.interval')) BEGIN
UPDATE sync_meta SET clock=clock+1;
INSERT INTO sync_events(event_id,clock,kind,entity_key,value) SELECT lower(hex(randomblob(16))),(SELECT clock FROM sync_meta),'feed',json_array(f.url),json_object('title',f.title,'folder',COALESCE((SELECT name FROM folders WHERE id=f.folder_id),''),'enabled',1-f.paused,'source','rss','kind','','target','','origin','','interval',json_extract(NEW.value,'$.interval')*60) FROM feeds f WHERE NOT EXISTS(SELECT 1 FROM sync_feed_meta WHERE feed_id=f.id);
INSERT INTO sync_versions SELECT kind,entity_key,clock,event_id,value FROM sync_events WHERE clock=(SELECT clock FROM sync_meta) AND true ON CONFLICT(kind,entity_key) DO UPDATE SET clock=excluded.clock,event_id=excluded.event_id,value=excluded.value;
END;
CREATE TRIGGER IF NOT EXISTS sync_enabled_insert AFTER INSERT ON feeds WHEN (SELECT applying FROM sync_meta WHERE id=1)=0 AND (NEW.paused=1) BEGIN
UPDATE sync_meta SET clock=clock+1;
INSERT INTO sync_events(event_id,clock,kind,entity_key,value) VALUES(lower(hex(randomblob(16))),(SELECT clock FROM sync_meta),'enabled',json_array(NEW.url),json_object('value',1-NEW.paused));
INSERT INTO sync_versions SELECT kind,entity_key,clock,event_id,value FROM sync_events WHERE seq=last_insert_rowid() ON CONFLICT(kind,entity_key) DO UPDATE SET clock=excluded.clock,event_id=excluded.event_id,value=excluded.value;
END;
CREATE TRIGGER IF NOT EXISTS sync_enabled_update AFTER UPDATE OF paused ON feeds WHEN (SELECT applying FROM sync_meta WHERE id=1)=0 AND (NEW.paused IS NOT OLD.paused) BEGIN
UPDATE sync_meta SET clock=clock+1;
INSERT INTO sync_events(event_id,clock,kind,entity_key,value) VALUES(lower(hex(randomblob(16))),(SELECT clock FROM sync_meta),'enabled',json_array(NEW.url),json_object('value',1-NEW.paused));
INSERT INTO sync_versions SELECT kind,entity_key,clock,event_id,value FROM sync_events WHERE seq=last_insert_rowid() ON CONFLICT(kind,entity_key) DO UPDATE SET clock=excluded.clock,event_id=excluded.event_id,value=excluded.value;
END;
UPDATE sync_meta SET applying=1;
INSERT OR IGNORE INTO sync_feed_meta SELECT feed_id,provider,CASE WHEN kind='account' THEN 'account' ELSE 'topic' END,target,origin,interval*60 FROM social_sources;
INSERT INTO sync_events(event_id,clock,kind,entity_key,value) SELECT lower(hex(randomblob(16))),0,'feed',json_array(f.url),json_object('title',f.title,'folder',COALESCE((SELECT name FROM folders WHERE id=f.folder_id),''),'enabled',1-f.paused,'source',COALESCE((SELECT source FROM sync_feed_meta WHERE feed_id=f.id),'rss'),'kind',COALESCE((SELECT kind FROM sync_feed_meta WHERE feed_id=f.id),''),'target',COALESCE((SELECT target FROM sync_feed_meta WHERE feed_id=f.id),''),'origin',COALESCE((SELECT origin FROM sync_feed_meta WHERE feed_id=f.id),''),'interval',COALESCE((SELECT interval FROM sync_feed_meta WHERE feed_id=f.id),(SELECT json_extract(value,'$.interval')*60 FROM settings WHERE id=1))) FROM feeds f WHERE 1 AND (SELECT initialized FROM sync_meta)=0 AND NOT EXISTS(SELECT 1 FROM sync_versions WHERE kind='feed' AND entity_key=json_array(f.url));
INSERT INTO sync_events(event_id,clock,kind,entity_key,value) SELECT lower(hex(randomblob(16))),0,'article',json_array(f.url,a.uid),json_object('title',a.title,'url',a.url,'content',a.content,'published',a.published,'collected',a.collected) FROM articles a JOIN feeds f ON f.id=a.feed_id WHERE 1 AND (SELECT initialized FROM sync_meta)=0 AND NOT EXISTS(SELECT 1 FROM sync_versions WHERE kind='article' AND entity_key=json_array(f.url,a.uid));
INSERT INTO sync_events(event_id,clock,kind,entity_key,value) SELECT lower(hex(randomblob(16))),0,'read',json_array(f.url,a.uid),json_object('value',1) FROM articles a JOIN feeds f ON f.id=a.feed_id WHERE a.is_read=1 AND (SELECT initialized FROM sync_meta)=0 AND NOT EXISTS(SELECT 1 FROM sync_versions WHERE kind='read' AND entity_key=json_array(f.url,a.uid));
INSERT INTO sync_events(event_id,clock,kind,entity_key,value) SELECT lower(hex(randomblob(16))),0,'star',json_array(f.url,a.uid),json_object('value',1) FROM articles a JOIN feeds f ON f.id=a.feed_id WHERE a.starred=1 AND (SELECT initialized FROM sync_meta)=0 AND NOT EXISTS(SELECT 1 FROM sync_versions WHERE kind='star' AND entity_key=json_array(f.url,a.uid));
INSERT INTO sync_events(event_id,clock,kind,entity_key,value) SELECT lower(hex(randomblob(16))),0,'collection',json_array(f.url),json_object('checked',COALESCE(f.last_fetched,''),'error',COALESCE(f.last_error,'')) FROM feeds f WHERE (SELECT initialized FROM sync_meta)=0 AND NOT EXISTS(SELECT 1 FROM sync_versions WHERE kind='collection' AND entity_key=json_array(f.url));
INSERT INTO sync_events(event_id,clock,kind,entity_key,value) SELECT lower(hex(randomblob(16))),0,'polling',json_array(),json_object('value',CASE WHEN COALESCE(json_extract(value,'$.pauseCollection'),0) THEN 0 ELSE 1 END) FROM settings WHERE id=1 AND (SELECT initialized FROM sync_meta)=0 AND NOT EXISTS(SELECT 1 FROM sync_versions WHERE kind='polling' AND entity_key=json_array());
INSERT INTO sync_events(event_id,clock,kind,entity_key,value) SELECT lower(hex(randomblob(16))),0,'enabled',json_array(f.url),json_object('value',0) FROM feeds f WHERE f.paused=1 AND (SELECT initialized FROM sync_meta)=0 AND NOT EXISTS(SELECT 1 FROM sync_versions WHERE kind='enabled' AND entity_key=json_array(f.url));
INSERT INTO sync_versions SELECT kind,entity_key,clock,event_id,value FROM sync_events WHERE true ON CONFLICT(kind,entity_key) DO NOTHING;
UPDATE sync_meta SET applying=0,initialized=1;
