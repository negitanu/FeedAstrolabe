CREATE TABLE articles (
 id INTEGER PRIMARY KEY, feed_id INTEGER NOT NULL REFERENCES feeds(id) ON DELETE CASCADE,
 guid TEXT NOT NULL, title TEXT NOT NULL, link TEXT NOT NULL DEFAULT '',
 content TEXT NOT NULL, search_text TEXT NOT NULL, published_at TEXT NOT NULL,
 is_read INTEGER NOT NULL DEFAULT 0 CHECK(is_read IN (0,1)),
 is_starred INTEGER NOT NULL DEFAULT 0 CHECK(is_starred IN (0,1)), source_published_at TEXT,
 UNIQUE(feed_id, guid)
);
CREATE TABLE settings (
              id INTEGER PRIMARY KEY CHECK(id=1), poll_interval INTEGER NOT NULL DEFAULT 900,
              polling_enabled INTEGER NOT NULL DEFAULT 1, page_size INTEGER NOT NULL DEFAULT 30,
              default_view TEXT NOT NULL DEFAULT 'all', api_rate_limit INTEGER NOT NULL DEFAULT 120
            , display_timezone TEXT NOT NULL DEFAULT 'UTC' CHECK(display_timezone IN ('UTC','Asia/Tokyo')));
CREATE TABLE api_keys (
              id INTEGER PRIMARY KEY, name TEXT NOT NULL, prefix TEXT NOT NULL,
              token_hash TEXT NOT NULL UNIQUE, scope TEXT NOT NULL CHECK(scope IN ('read','write')),
              created_at TEXT NOT NULL, expires_at TEXT NOT NULL, revoked_at TEXT, last_used_at TEXT,
              rate_window INTEGER NOT NULL DEFAULT 0, rate_count INTEGER NOT NULL DEFAULT 0
            );
CREATE TABLE provider_cooldowns (provider TEXT PRIMARY KEY, retry_at TEXT NOT NULL);
CREATE TABLE "feeds" (
 id INTEGER PRIMARY KEY, url TEXT NOT NULL UNIQUE, title TEXT NOT NULL,
 folder TEXT NOT NULL DEFAULT '', etag TEXT, modified TEXT,
 checked_at TEXT, success_at TEXT, error TEXT, created_at TEXT NOT NULL
, enabled INTEGER NOT NULL DEFAULT 1 CHECK(enabled IN (0,1)), poll_interval INTEGER CHECK(poll_interval BETWEEN 60 AND 86400), failures INTEGER NOT NULL DEFAULT 0, source_type TEXT NOT NULL DEFAULT 'rss' CHECK(source_type IN ('rss','x','mastodon','page')), source_kind TEXT, target TEXT, instance_url TEXT, provider_id TEXT, since_id TEXT, page_cursor TEXT, pending_newest TEXT, retry_at TEXT, selector TEXT, settle_ms INTEGER NOT NULL DEFAULT 1000 CHECK(settle_ms BETWEEN 0 AND 10000), snapshot TEXT, observation_seq INTEGER NOT NULL DEFAULT 0, revision INTEGER NOT NULL DEFAULT 0, retention_days INTEGER NOT NULL DEFAULT 90 CHECK(retention_days BETWEEN 1 AND 365));
CREATE TABLE page_jobs (feed_id INTEGER PRIMARY KEY REFERENCES feeds(id) ON DELETE CASCADE,requested_at TEXT NOT NULL);
CREATE TABLE workspaces (
              id INTEGER PRIMARY KEY, title TEXT NOT NULL CHECK(length(title) BETWEEN 1 AND 120),
              purpose TEXT NOT NULL DEFAULT '' CHECK(length(purpose)<=10000),
              questions TEXT NOT NULL DEFAULT '' CHECK(length(questions)<=10000),
              status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','paused','completed')),
              classification TEXT NOT NULL DEFAULT 'internal' CHECK(classification IN ('public','internal','restricted')),
              archived INTEGER NOT NULL DEFAULT 0 CHECK(archived IN (0,1)),
              created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            );
CREATE TABLE workspace_feeds (
              workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
              feed_id INTEGER NOT NULL REFERENCES feeds(id) ON DELETE CASCADE,
              PRIMARY KEY(workspace_id,feed_id)
            );
CREATE TABLE workspace_articles (
              workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
              article_id INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
              PRIMARY KEY(workspace_id,article_id)
            );
CREATE TABLE notes (
              id INTEGER PRIMARY KEY, workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
              title TEXT NOT NULL CHECK(length(title) BETWEEN 1 AND 120),
              body TEXT NOT NULL DEFAULT '' CHECK(length(body)<=100000),
              label TEXT NOT NULL DEFAULT 'hypothesis' CHECK(label IN ('fact','source-claim','hypothesis')),
              archived INTEGER NOT NULL DEFAULT 0 CHECK(archived IN (0,1)),
              revision INTEGER NOT NULL CHECK(revision>=1), created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            );
CREATE TABLE note_revisions (
              note_id INTEGER NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
              revision INTEGER NOT NULL, title TEXT NOT NULL, body TEXT NOT NULL, label TEXT NOT NULL,
              archived INTEGER NOT NULL CHECK(archived IN (0,1)), created_at TEXT NOT NULL,
              PRIMARY KEY(note_id,revision)
            );
CREATE TABLE tags (id INTEGER PRIMARY KEY,name TEXT NOT NULL COLLATE NOCASE UNIQUE CHECK(length(name) BETWEEN 1 AND 80));
CREATE TABLE workspace_tags (
              workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
              tag_id INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,PRIMARY KEY(workspace_id,tag_id)
            );
CREATE TABLE article_tags (
              article_id INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
              tag_id INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,PRIMARY KEY(article_id,tag_id)
            );
CREATE TABLE note_tags (
              note_id INTEGER NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
              tag_id INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,PRIMARY KEY(note_id,tag_id)
            );
CREATE TABLE evidence_settings (id INTEGER PRIMARY KEY CHECK(id=1),quota_bytes INTEGER NOT NULL DEFAULT 524288000 CHECK(quota_bytes BETWEEN 10485760 AND 10737418240),retention_days INTEGER NOT NULL DEFAULT 90 CHECK(retention_days BETWEEN 1 AND 3650));
CREATE TABLE evidence_blobs (hash TEXT PRIMARY KEY CHECK(length(hash)=64),size INTEGER NOT NULL CHECK(size BETWEEN 0 AND 10485760));
CREATE TABLE workspace_evidence (workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,evidence_id INTEGER NOT NULL REFERENCES evidence(id) ON DELETE RESTRICT,PRIMARY KEY(workspace_id,evidence_id));
CREATE TABLE note_evidence (note_id INTEGER NOT NULL REFERENCES notes(id) ON DELETE CASCADE,evidence_id INTEGER NOT NULL REFERENCES evidence(id) ON DELETE RESTRICT,PRIMARY KEY(note_id,evidence_id));
CREATE TABLE quotations (id INTEGER PRIMARY KEY,workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,note_id INTEGER REFERENCES notes(id) ON DELETE SET NULL,evidence_id INTEGER NOT NULL REFERENCES evidence(id) ON DELETE RESTRICT,text_hash TEXT NOT NULL,start INTEGER NOT NULL,end INTEGER NOT NULL,quote TEXT NOT NULL CHECK(length(quote) BETWEEN 1 AND 10000),created_at TEXT NOT NULL,CHECK(start>=0 AND end>start),UNIQUE(workspace_id,evidence_id,start,end,note_id));
CREATE TABLE evidence_capture_errors (feed_id INTEGER PRIMARY KEY REFERENCES feeds(id) ON DELETE CASCADE,message TEXT NOT NULL,occurred_at TEXT NOT NULL);
CREATE TABLE "evidence" (
              id INTEGER PRIMARY KEY AUTOINCREMENT, source_key TEXT NOT NULL, version INTEGER NOT NULL CHECK(version>=1),
              feed_id INTEGER REFERENCES feeds(id) ON DELETE SET NULL,
              article_id INTEGER REFERENCES articles(id) ON DELETE SET NULL,
              source_url TEXT NOT NULL, publisher TEXT NOT NULL, source_guid TEXT NOT NULL,
              title TEXT NOT NULL, method TEXT NOT NULL, published_at TEXT, observed_at TEXT,
              captured_at TEXT NOT NULL, blob_hash TEXT NOT NULL REFERENCES evidence_blobs(hash),
              text_hash TEXT NOT NULL CHECK(length(text_hash)=64), text TEXT NOT NULL CHECK(length(text)<=160000),
              mime TEXT NOT NULL, filename TEXT NOT NULL DEFAULT '',UNIQUE(source_key,version)
            );
CREATE TABLE watchlists (
 id INTEGER PRIMARY KEY AUTOINCREMENT,workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
 name TEXT NOT NULL CHECK(length(name) BETWEEN 1 AND 120),kind TEXT NOT NULL CHECK(kind IN ('watchlist','saved-search')),
 enabled INTEGER NOT NULL CHECK(enabled IN (0,1)),revision INTEGER NOT NULL,last_run TEXT NOT NULL DEFAULT '',
 created_at TEXT NOT NULL,updated_at TEXT NOT NULL
);
CREATE TABLE watchlist_versions (
 id INTEGER PRIMARY KEY AUTOINCREMENT,watchlist_id INTEGER NOT NULL REFERENCES watchlists(id) ON DELETE CASCADE,
 revision INTEGER NOT NULL,query TEXT NOT NULL,exclusion TEXT NOT NULL,priority TEXT NOT NULL CHECK(priority IN ('low','normal','high','critical')),
 reason TEXT NOT NULL,cursor INTEGER NOT NULL DEFAULT 0,created_at TEXT NOT NULL,UNIQUE(watchlist_id,revision)
);
CREATE TABLE watch_events (
 id INTEGER PRIMARY KEY AUTOINCREMENT,version_id INTEGER NOT NULL REFERENCES watchlist_versions(id) ON DELETE CASCADE,
 evidence_id INTEGER NOT NULL REFERENCES evidence(id) ON DELETE RESTRICT,included INTEGER NOT NULL CHECK(included IN (0,1)),
 explanation TEXT NOT NULL,seen INTEGER NOT NULL DEFAULT 0 CHECK(seen IN (0,1)),created_at TEXT NOT NULL,
 UNIQUE(version_id,evidence_id)
);
CREATE TABLE duplicate_fingerprints (
 evidence_id INTEGER NOT NULL REFERENCES evidence(id) ON DELETE CASCADE,kind TEXT NOT NULL,key TEXT NOT NULL,
 PRIMARY KEY(evidence_id,kind)
);
CREATE TABLE duplicate_groups (
 id INTEGER PRIMARY KEY AUTOINCREMENT,kind TEXT NOT NULL,key TEXT NOT NULL,suppressed INTEGER NOT NULL DEFAULT 0 CHECK(suppressed IN (0,1)),
 created_at TEXT NOT NULL,updated_at TEXT NOT NULL,UNIQUE(kind,key)
);
CREATE TABLE duplicate_members (
 group_id INTEGER NOT NULL REFERENCES duplicate_groups(id) ON DELETE CASCADE,
 evidence_id INTEGER NOT NULL REFERENCES evidence(id) ON DELETE RESTRICT,PRIMARY KEY(group_id,evidence_id)
);
CREATE TABLE triage_state (id INTEGER PRIMARY KEY CHECK(id=1),cursor INTEGER NOT NULL DEFAULT 0);
CREATE TABLE entities (
 id INTEGER PRIMARY KEY AUTOINCREMENT,kind TEXT NOT NULL CHECK(kind IN ('cve','domain','ip','asn','hash','repository','organization','product','model')),
 identity TEXT NOT NULL,canonical TEXT NOT NULL,display_name TEXT NOT NULL,
 merged_into INTEGER REFERENCES entities(id) ON DELETE RESTRICT,revision INTEGER NOT NULL DEFAULT 1,
 created_at TEXT NOT NULL,updated_at TEXT NOT NULL,UNIQUE(kind,identity),CHECK(merged_into IS NULL OR merged_into!=id)
);
CREATE TABLE entity_aliases (
 id INTEGER PRIMARY KEY AUTOINCREMENT,entity_id INTEGER NOT NULL REFERENCES entities(id) ON DELETE RESTRICT,
 value TEXT NOT NULL,normalized TEXT NOT NULL,reviewed INTEGER NOT NULL CHECK(reviewed IN (0,1)),
 author TEXT NOT NULL,created_at TEXT NOT NULL,UNIQUE(entity_id,normalized)
);
CREATE TABLE entity_mentions (
 id INTEGER PRIMARY KEY AUTOINCREMENT,evidence_id INTEGER NOT NULL REFERENCES evidence(id) ON DELETE RESTRICT,
 original_entity_id INTEGER NOT NULL REFERENCES entities(id) ON DELETE RESTRICT,entity_id INTEGER NOT NULL REFERENCES entities(id) ON DELETE RESTRICT,
 extracted_kind TEXT NOT NULL,text_hash TEXT NOT NULL,start INTEGER NOT NULL,end INTEGER NOT NULL,original TEXT NOT NULL,
 normalization TEXT NOT NULL,method TEXT NOT NULL CHECK(method IN ('auto','manual')),status TEXT NOT NULL DEFAULT 'candidate' CHECK(status IN ('candidate','confirmed','rejected')),
 revision INTEGER NOT NULL DEFAULT 1,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,
 CHECK(start>=0 AND end>start),UNIQUE(evidence_id,start,end,extracted_kind)
);
CREATE TABLE entity_extractions (
 evidence_id INTEGER PRIMARY KEY REFERENCES evidence(id) ON DELETE CASCADE,normalization TEXT NOT NULL,
 truncated INTEGER NOT NULL CHECK(truncated IN (0,1)),created_at TEXT NOT NULL
);
CREATE TABLE entity_state (id INTEGER PRIMARY KEY CHECK(id=1),cursor INTEGER NOT NULL DEFAULT 0);
CREATE TABLE relations (
 id INTEGER PRIMARY KEY AUTOINCREMENT,workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
 revision INTEGER NOT NULL DEFAULT 1,created_at TEXT NOT NULL,updated_at TEXT NOT NULL
);
CREATE TABLE relation_versions (
 id INTEGER PRIMARY KEY AUTOINCREMENT,relation_id INTEGER NOT NULL REFERENCES relations(id) ON DELETE CASCADE,revision INTEGER NOT NULL,
 source_id INTEGER NOT NULL REFERENCES entities(id) ON DELETE RESTRICT,target_id INTEGER NOT NULL REFERENCES entities(id) ON DELETE RESTRICT,
 predicate TEXT NOT NULL,quotation_id INTEGER NOT NULL REFERENCES quotations(id) ON DELETE RESTRICT,
 label TEXT NOT NULL CHECK(label IN ('fact','source-claim','hypothesis')),confidence TEXT NOT NULL CHECK(confidence IN ('unknown','low','medium','high')),
 author TEXT NOT NULL,observed_at TEXT,valid_from TEXT,valid_to TEXT,archived INTEGER NOT NULL DEFAULT 0 CHECK(archived IN (0,1)),
 recorded_at TEXT NOT NULL,UNIQUE(relation_id,revision)
);
CREATE TABLE entity_audit (
 id INTEGER PRIMARY KEY AUTOINCREMENT,kind TEXT NOT NULL,details TEXT NOT NULL,author TEXT NOT NULL,
 workspace_id INTEGER REFERENCES workspaces(id) ON DELETE SET NULL,evidence_id INTEGER REFERENCES evidence(id) ON DELETE RESTRICT,
 observed_at TEXT,recorded_at TEXT NOT NULL
);
CREATE TABLE entity_audit_entities (
 audit_id INTEGER NOT NULL REFERENCES entity_audit(id) ON DELETE CASCADE,entity_id INTEGER NOT NULL REFERENCES entities(id) ON DELETE RESTRICT,
 PRIMARY KEY(audit_id,entity_id)
);
CREATE TABLE connector_settings(provider TEXT PRIMARY KEY,enabled INTEGER NOT NULL DEFAULT 0 CHECK(enabled IN(0,1)),ttl_seconds INTEGER NOT NULL DEFAULT 86400 CHECK(ttl_seconds BETWEEN 3600 AND 604800),daily_budget INTEGER NOT NULL DEFAULT 100 CHECK(daily_budget BETWEEN 1 AND 1000),revision INTEGER NOT NULL DEFAULT 1);
CREATE TABLE connector_state(provider TEXT PRIMARY KEY REFERENCES connector_settings(provider),last_request TEXT,cooldown_until TEXT,budget_day TEXT,requests INTEGER NOT NULL DEFAULT 0);
CREATE TABLE connector_jobs(id INTEGER PRIMARY KEY AUTOINCREMENT,provider TEXT NOT NULL REFERENCES connector_settings(provider),input TEXT NOT NULL,status TEXT NOT NULL CHECK(status IN('queued','running','success','failed')),attempts INTEGER NOT NULL DEFAULT 0,next_attempt TEXT NOT NULL,error TEXT,created_at TEXT NOT NULL,finished_at TEXT);
CREATE TABLE connector_cache(provider TEXT NOT NULL REFERENCES connector_settings(provider),input TEXT NOT NULL,payload TEXT NOT NULL,response_hash TEXT NOT NULL,source_url TEXT NOT NULL,source_version TEXT NOT NULL,observed_at TEXT NOT NULL,expires_at TEXT NOT NULL,PRIMARY KEY(provider,input));
CREATE TABLE security_observations(id INTEGER PRIMARY KEY AUTOINCREMENT,entity_id INTEGER NOT NULL REFERENCES entities(id) ON DELETE RESTRICT,provider TEXT NOT NULL REFERENCES connector_settings(provider),response_hash TEXT NOT NULL,source_version TEXT NOT NULL,observed_at TEXT NOT NULL,payload TEXT NOT NULL,evidence_id INTEGER NOT NULL REFERENCES evidence(id) ON DELETE RESTRICT,UNIQUE(entity_id,provider,response_hash));
CREATE TABLE security_watches(id INTEGER PRIMARY KEY AUTOINCREMENT,workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,entity_id INTEGER NOT NULL REFERENCES entities(id) ON DELETE RESTRICT,product TEXT NOT NULL DEFAULT '',version TEXT NOT NULL DEFAULT '',outbound_public INTEGER NOT NULL CHECK(outbound_public IN(0,1)),enabled INTEGER NOT NULL DEFAULT 1 CHECK(enabled IN(0,1)),revision INTEGER NOT NULL DEFAULT 1,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,last_processed_at TEXT,UNIQUE(workspace_id,entity_id,product,version));
CREATE TABLE security_reviews(id INTEGER PRIMARY KEY AUTOINCREMENT,watch_id INTEGER NOT NULL REFERENCES security_watches(id) ON DELETE CASCADE,revision INTEGER NOT NULL,status TEXT NOT NULL CHECK(status IN('confirmed','possible','unknown')),quotation_id INTEGER REFERENCES quotations(id) ON DELETE RESTRICT,reason TEXT NOT NULL,author TEXT NOT NULL,created_at TEXT NOT NULL,UNIQUE(watch_id,revision));
CREATE TABLE security_references(id INTEGER PRIMARY KEY AUTOINCREMENT,workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,entity_id INTEGER NOT NULL REFERENCES entities(id) ON DELETE RESTRICT,url TEXT NOT NULL,kind TEXT NOT NULL CHECK(kind IN('poc','advisory','fix')),quotation_id INTEGER NOT NULL REFERENCES quotations(id) ON DELETE RESTRICT,author TEXT NOT NULL,created_at TEXT NOT NULL,UNIQUE(workspace_id,entity_id,url,kind));
CREATE TABLE network_watches(id INTEGER PRIMARY KEY AUTOINCREMENT,workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,entity_id INTEGER NOT NULL REFERENCES entities(id) ON DELETE RESTRICT,provider TEXT NOT NULL REFERENCES connector_settings(provider),input TEXT NOT NULL,outbound_public INTEGER NOT NULL CHECK(outbound_public IN(0,1)),enabled INTEGER NOT NULL DEFAULT 1 CHECK(enabled IN(0,1)),interval_seconds INTEGER NOT NULL DEFAULT 86400 CHECK(interval_seconds BETWEEN 3600 AND 604800),retention_days INTEGER NOT NULL DEFAULT 90 CHECK(retention_days BETWEEN 7 AND 3650),revision INTEGER NOT NULL DEFAULT 1,next_check TEXT NOT NULL,last_processed_at TEXT,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,UNIQUE(workspace_id,entity_id,provider,input));
CREATE TABLE network_observations(id INTEGER PRIMARY KEY AUTOINCREMENT,watch_id INTEGER NOT NULL REFERENCES network_watches(id) ON DELETE CASCADE,response_hash TEXT NOT NULL,source_url TEXT NOT NULL,source_version TEXT NOT NULL,observed_at TEXT NOT NULL,normalized TEXT NOT NULL,evidence_id INTEGER NOT NULL REFERENCES evidence(id) ON DELETE RESTRICT,UNIQUE(watch_id,response_hash,observed_at));
CREATE TABLE network_events(id INTEGER PRIMARY KEY AUTOINCREMENT,watch_id INTEGER NOT NULL REFERENCES network_watches(id) ON DELETE CASCADE,previous_id INTEGER NOT NULL REFERENCES network_observations(id) ON DELETE CASCADE,current_id INTEGER NOT NULL REFERENCES network_observations(id) ON DELETE CASCADE,changes TEXT NOT NULL,created_at TEXT NOT NULL,UNIQUE(previous_id,current_id));
CREATE TABLE ai_watches (
 id INTEGER PRIMARY KEY AUTOINCREMENT,workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
 provider TEXT NOT NULL REFERENCES connector_settings(provider),target TEXT NOT NULL,term TEXT NOT NULL DEFAULT '',
 outbound_public INTEGER NOT NULL DEFAULT 0 CHECK(outbound_public IN(0,1)),enabled INTEGER NOT NULL DEFAULT 1 CHECK(enabled IN(0,1)),
 interval_seconds INTEGER NOT NULL DEFAULT 86400 CHECK(interval_seconds BETWEEN 3600 AND 604800),revision INTEGER NOT NULL DEFAULT 1,
 page INTEGER NOT NULL DEFAULT 0 CHECK(page BETWEEN 0 AND 19),next_check TEXT NOT NULL,last_processed_at TEXT,last_success_at TEXT,last_cache_signature TEXT,truncated INTEGER NOT NULL DEFAULT 0,
 created_at TEXT NOT NULL,updated_at TEXT NOT NULL,UNIQUE(workspace_id,provider,target,term)
);
CREATE TABLE ai_versions (
 id INTEGER PRIMARY KEY AUTOINCREMENT,watch_id INTEGER NOT NULL REFERENCES ai_watches(id) ON DELETE CASCADE,
 record_id TEXT NOT NULL,version TEXT NOT NULL,projection_hash TEXT NOT NULL,response_hash TEXT NOT NULL,
 payload TEXT NOT NULL,source_url TEXT NOT NULL,source_version TEXT NOT NULL,observed_at TEXT NOT NULL,
 evidence_id INTEGER NOT NULL REFERENCES evidence(id) ON DELETE RESTRICT,UNIQUE(watch_id,record_id,projection_hash)
);
CREATE TABLE ai_cards (
 id INTEGER PRIMARY KEY AUTOINCREMENT,workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
 entity_id INTEGER NOT NULL REFERENCES entities(id) ON DELETE RESTRICT,version TEXT NOT NULL,
 quotation_id INTEGER NOT NULL REFERENCES quotations(id) ON DELETE RESTRICT,claims TEXT NOT NULL,
 author TEXT NOT NULL,created_at TEXT NOT NULL
);
CREATE TABLE ai_links (
 id INTEGER PRIMARY KEY AUTOINCREMENT,card_id INTEGER NOT NULL REFERENCES ai_cards(id) ON DELETE CASCADE,
 kind TEXT NOT NULL CHECK(kind IN('paper','repository','model-card')),url TEXT NOT NULL,
 version_id INTEGER REFERENCES ai_versions(id) ON DELETE RESTRICT,quotation_id INTEGER NOT NULL REFERENCES quotations(id) ON DELETE RESTRICT,
 author TEXT NOT NULL,created_at TEXT NOT NULL,UNIQUE(card_id,kind,url,quotation_id)
);
CREATE TABLE ai_benchmarks (
 id INTEGER PRIMARY KEY AUTOINCREMENT,card_id INTEGER NOT NULL REFERENCES ai_cards(id) ON DELETE CASCADE,
 status TEXT NOT NULL CHECK(status IN('claimed','reproduced','unverified')),conditions TEXT NOT NULL,
 result TEXT NOT NULL,notes TEXT NOT NULL,quotation_id INTEGER REFERENCES quotations(id) ON DELETE RESTRICT,
 author TEXT NOT NULL,created_at TEXT NOT NULL
);
CREATE TABLE assistant_profiles (
 id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,kind TEXT NOT NULL CHECK(kind IN('local','cloud')),model TEXT NOT NULL,
 model_digest TEXT,enabled INTEGER NOT NULL DEFAULT 0 CHECK(enabled IN(0,1)),revision INTEGER NOT NULL DEFAULT 1,
 max_output_tokens INTEGER NOT NULL DEFAULT 512,daily_calls INTEGER NOT NULL DEFAULT 10,
 input_rate INTEGER,output_rate INTEGER,price_date TEXT,max_cost INTEGER NOT NULL DEFAULT 100000,daily_cost INTEGER NOT NULL DEFAULT 1000000,
 created_at TEXT NOT NULL,updated_at TEXT NOT NULL
);
CREATE TABLE assistant_previews (
 id INTEGER PRIMARY KEY AUTOINCREMENT,workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
 profile_id INTEGER NOT NULL REFERENCES assistant_profiles(id) ON DELETE RESTRICT,profile_revision INTEGER NOT NULL,
 mode TEXT NOT NULL,question TEXT NOT NULL,input TEXT NOT NULL,input_hash TEXT NOT NULL,anchors TEXT NOT NULL,
 input_token_bound INTEGER NOT NULL,reserved_cost INTEGER NOT NULL,prompt_hash TEXT NOT NULL,expires_at TEXT NOT NULL,created_at TEXT NOT NULL
);
CREATE TABLE assistant_jobs (
 id INTEGER PRIMARY KEY AUTOINCREMENT,preview_id INTEGER NOT NULL UNIQUE REFERENCES assistant_previews(id) ON DELETE RESTRICT,
 status TEXT NOT NULL CHECK(status IN('queued','running','success','failed')),result TEXT,error TEXT,
 model_lineage TEXT,usage TEXT,cost_estimate INTEGER,review_revision INTEGER NOT NULL DEFAULT 0,
 created_at TEXT NOT NULL,finished_at TEXT
);
CREATE TABLE assistant_budget (
 profile_id INTEGER NOT NULL REFERENCES assistant_profiles(id) ON DELETE CASCADE,day TEXT NOT NULL,calls INTEGER NOT NULL DEFAULT 0,reserved_cost INTEGER NOT NULL DEFAULT 0,
 PRIMARY KEY(profile_id,day)
);
CREATE TABLE assistant_review_versions (
 id INTEGER PRIMARY KEY AUTOINCREMENT,job_id INTEGER NOT NULL REFERENCES assistant_jobs(id) ON DELETE CASCADE,
 revision INTEGER NOT NULL,status TEXT NOT NULL CHECK(status IN('reviewed','rejected','draft')),text TEXT NOT NULL,author TEXT NOT NULL,created_at TEXT NOT NULL,UNIQUE(job_id,revision)
);
CREATE TABLE assistant_sources (
 preview_id INTEGER NOT NULL REFERENCES assistant_previews(id) ON DELETE CASCADE,evidence_id INTEGER NOT NULL REFERENCES evidence(id) ON DELETE RESTRICT,
 PRIMARY KEY(preview_id,evidence_id)
);
CREATE TABLE reports(id INTEGER PRIMARY KEY AUTOINCREMENT,workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE RESTRICT,format TEXT NOT NULL,payload TEXT NOT NULL,payload_hash TEXT NOT NULL,manifest TEXT NOT NULL,include_nonpublic INTEGER NOT NULL CHECK(include_nonpublic IN(0,1)),created_at TEXT NOT NULL);
CREATE TABLE report_sources(report_id INTEGER NOT NULL REFERENCES reports(id) ON DELETE CASCADE,evidence_id INTEGER NOT NULL REFERENCES evidence(id) ON DELETE RESTRICT,PRIMARY KEY(report_id,evidence_id));
CREATE TABLE delivery_profiles(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,kind TEXT NOT NULL CHECK(kind IN('webhook','email')),destination TEXT NOT NULL,enabled INTEGER NOT NULL DEFAULT 0 CHECK(enabled IN(0,1)),revision INTEGER NOT NULL DEFAULT 1,created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
CREATE TABLE delivery_previews(id INTEGER PRIMARY KEY AUTOINCREMENT,report_id INTEGER NOT NULL REFERENCES reports(id) ON DELETE RESTRICT,profile_id INTEGER NOT NULL REFERENCES delivery_profiles(id) ON DELETE RESTRICT,profile_revision INTEGER NOT NULL,payload TEXT NOT NULL,payload_hash TEXT NOT NULL,expires_at TEXT NOT NULL,created_at TEXT NOT NULL);
CREATE TABLE delivery_jobs(id INTEGER PRIMARY KEY AUTOINCREMENT,preview_id INTEGER NOT NULL UNIQUE REFERENCES delivery_previews(id) ON DELETE RESTRICT,idempotency_key TEXT NOT NULL UNIQUE,status TEXT NOT NULL CHECK(status IN('queued','running','retry','success','failed')),attempts INTEGER NOT NULL DEFAULT 0,next_attempt TEXT NOT NULL,started_at TEXT,ended_at TEXT,error TEXT,created_at TEXT NOT NULL);
CREATE TABLE delivery_attempts(id INTEGER PRIMARY KEY AUTOINCREMENT,job_id INTEGER NOT NULL REFERENCES delivery_jobs(id) ON DELETE RESTRICT,attempt INTEGER NOT NULL,status TEXT NOT NULL,error TEXT,started_at TEXT NOT NULL,ended_at TEXT NOT NULL,UNIQUE(job_id,attempt));
CREATE TABLE operations_config(id INTEGER PRIMARY KEY CHECK(id=1),backup_enabled INTEGER NOT NULL DEFAULT 0 CHECK(backup_enabled IN(0,1)),interval_seconds INTEGER NOT NULL DEFAULT 86400 CHECK(interval_seconds BETWEEN 3600 AND 604800),generations INTEGER NOT NULL DEFAULT 7 CHECK(generations BETWEEN 1 AND 30),quota_bytes INTEGER NOT NULL DEFAULT 4294967296 CHECK(quota_bytes BETWEEN 1048576 AND 107374182400),revision INTEGER NOT NULL DEFAULT 1,last_attempt TEXT);
CREATE TABLE backup_jobs(id INTEGER PRIMARY KEY AUTOINCREMENT,status TEXT NOT NULL CHECK(status IN('queued','running','success','failed')),generation TEXT NOT NULL UNIQUE,manifest_hash TEXT,size_bytes INTEGER,error TEXT,created_at TEXT NOT NULL,ended_at TEXT,retired_at TEXT);
CREATE TABLE worker_health(name TEXT PRIMARY KEY,started_at TEXT NOT NULL,heartbeat_at TEXT NOT NULL,ended_at TEXT,status TEXT NOT NULL,error TEXT);
CREATE TABLE worker_runs(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,started_at TEXT NOT NULL,ended_at TEXT,status TEXT NOT NULL,processed INTEGER NOT NULL DEFAULT 0,error TEXT);
CREATE INDEX articles_date ON articles(published_at DESC, id DESC);
CREATE INDEX articles_feed ON articles(feed_id);
CREATE INDEX articles_read ON articles(is_read);
CREATE INDEX articles_starred ON articles(is_starred);
CREATE INDEX notes_workspace ON notes(workspace_id,archived,id);
CREATE INDEX workspace_feeds_reverse ON workspace_feeds(feed_id,workspace_id);
CREATE INDEX workspace_articles_reverse ON workspace_articles(article_id,workspace_id);
CREATE INDEX workspace_tags_reverse ON workspace_tags(tag_id,workspace_id);
CREATE INDEX article_tags_reverse ON article_tags(tag_id,article_id);
CREATE INDEX note_tags_reverse ON note_tags(tag_id,note_id);
CREATE INDEX workspace_evidence_reverse ON workspace_evidence(evidence_id);
CREATE INDEX note_evidence_reverse ON note_evidence(evidence_id);
CREATE INDEX quotations_evidence ON quotations(evidence_id);
CREATE INDEX evidence_source ON evidence(source_key,id DESC);
CREATE INDEX evidence_article ON evidence(article_id,id DESC);
CREATE INDEX watchlists_schedule ON watchlists(enabled,last_run,id);
CREATE INDEX watchlists_workspace ON watchlists(workspace_id,id);
CREATE INDEX watch_events_evidence ON watch_events(evidence_id);
CREATE INDEX watch_events_date ON watch_events(created_at,id);
CREATE INDEX duplicate_fingerprints_key ON duplicate_fingerprints(kind,key,evidence_id);
CREATE INDEX duplicate_members_evidence ON duplicate_members(evidence_id);
CREATE INDEX evidence_text_hash ON evidence(text_hash);
CREATE INDEX entities_search ON entities(kind,canonical,id);
CREATE INDEX entities_merge ON entities(merged_into,id);
CREATE INDEX entity_aliases_normalized ON entity_aliases(normalized,entity_id);
CREATE INDEX entity_mentions_entity ON entity_mentions(entity_id,status,id);
CREATE INDEX entity_mentions_original ON entity_mentions(original_entity_id,id);
CREATE INDEX entity_mentions_evidence ON entity_mentions(evidence_id,id);
CREATE INDEX relation_versions_source ON relation_versions(source_id,relation_id,revision);
CREATE INDEX relation_versions_target ON relation_versions(target_id,relation_id,revision);
CREATE INDEX relations_workspace ON relations(workspace_id,id);
CREATE INDEX entity_audit_entities_reverse ON entity_audit_entities(entity_id,audit_id);
CREATE INDEX connector_jobs_due ON connector_jobs(status,next_attempt,id);
CREATE UNIQUE INDEX connector_jobs_pending ON connector_jobs(provider,input) WHERE status IN('queued','running');
CREATE INDEX security_observations_entity ON security_observations(entity_id,provider,id);
CREATE INDEX network_observations_watch ON network_observations(watch_id,id);
CREATE INDEX network_events_watch ON network_events(watch_id,id);
CREATE INDEX ai_versions_watch ON ai_versions(watch_id,id);
CREATE INDEX ai_cards_case ON ai_cards(workspace_id,id);
CREATE INDEX ai_benchmarks_card ON ai_benchmarks(card_id,id);
CREATE INDEX assistant_job_status ON assistant_jobs(status,id);
INSERT INTO settings(id) VALUES(1);
PRAGMA user_version=14;
