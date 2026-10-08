"""Entity originals and explicit review history, schema eight."""
SCHEMA="""
CREATE TABLE entities (
 id INTEGER PRIMARY KEY AUTOINCREMENT,kind TEXT NOT NULL CHECK(kind IN ('cve','domain','ip','asn','hash','repository','organization','product','model')),
 identity TEXT NOT NULL,canonical TEXT NOT NULL,display_name TEXT NOT NULL,
 merged_into INTEGER REFERENCES entities(id) ON DELETE RESTRICT,revision INTEGER NOT NULL DEFAULT 1,
 created_at TEXT NOT NULL,updated_at TEXT NOT NULL,UNIQUE(kind,identity),CHECK(merged_into IS NULL OR merged_into!=id)
);
CREATE INDEX entities_search ON entities(kind,canonical,id);
CREATE INDEX entities_merge ON entities(merged_into,id);
CREATE TABLE entity_aliases (
 id INTEGER PRIMARY KEY AUTOINCREMENT,entity_id INTEGER NOT NULL REFERENCES entities(id) ON DELETE RESTRICT,
 value TEXT NOT NULL,normalized TEXT NOT NULL,reviewed INTEGER NOT NULL CHECK(reviewed IN (0,1)),
 author TEXT NOT NULL,created_at TEXT NOT NULL,UNIQUE(entity_id,normalized)
);
CREATE INDEX entity_aliases_normalized ON entity_aliases(normalized,entity_id);
CREATE TABLE entity_mentions (
 id INTEGER PRIMARY KEY AUTOINCREMENT,evidence_id INTEGER NOT NULL REFERENCES evidence(id) ON DELETE RESTRICT,
 original_entity_id INTEGER NOT NULL REFERENCES entities(id) ON DELETE RESTRICT,entity_id INTEGER NOT NULL REFERENCES entities(id) ON DELETE RESTRICT,
 extracted_kind TEXT NOT NULL,text_hash TEXT NOT NULL,start INTEGER NOT NULL,end INTEGER NOT NULL,original TEXT NOT NULL,
 normalization TEXT NOT NULL,method TEXT NOT NULL CHECK(method IN ('auto','manual')),status TEXT NOT NULL DEFAULT 'candidate' CHECK(status IN ('candidate','confirmed','rejected')),
 revision INTEGER NOT NULL DEFAULT 1,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,
 CHECK(start>=0 AND end>start),UNIQUE(evidence_id,start,end,extracted_kind)
);
CREATE INDEX entity_mentions_entity ON entity_mentions(entity_id,status,id);
CREATE INDEX entity_mentions_original ON entity_mentions(original_entity_id,id);
CREATE INDEX entity_mentions_evidence ON entity_mentions(evidence_id,id);
CREATE TABLE entity_extractions (
 evidence_id INTEGER PRIMARY KEY REFERENCES evidence(id) ON DELETE CASCADE,normalization TEXT NOT NULL,
 truncated INTEGER NOT NULL CHECK(truncated IN (0,1)),created_at TEXT NOT NULL
);
CREATE TABLE entity_state (id INTEGER PRIMARY KEY CHECK(id=1),cursor INTEGER NOT NULL DEFAULT 0);
INSERT INTO entity_state(id) VALUES(1);
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
CREATE INDEX relation_versions_source ON relation_versions(source_id,relation_id,revision);
CREATE INDEX relation_versions_target ON relation_versions(target_id,relation_id,revision);
CREATE INDEX relations_workspace ON relations(workspace_id,id);
CREATE TABLE entity_audit (
 id INTEGER PRIMARY KEY AUTOINCREMENT,kind TEXT NOT NULL,details TEXT NOT NULL,author TEXT NOT NULL,
 workspace_id INTEGER REFERENCES workspaces(id) ON DELETE SET NULL,evidence_id INTEGER REFERENCES evidence(id) ON DELETE RESTRICT,
 observed_at TEXT,recorded_at TEXT NOT NULL
);
CREATE TABLE entity_audit_entities (
 audit_id INTEGER NOT NULL REFERENCES entity_audit(id) ON DELETE CASCADE,entity_id INTEGER NOT NULL REFERENCES entities(id) ON DELETE RESTRICT,
 PRIMARY KEY(audit_id,entity_id)
);
CREATE INDEX entity_audit_entities_reverse ON entity_audit_entities(entity_id,audit_id);
"""
