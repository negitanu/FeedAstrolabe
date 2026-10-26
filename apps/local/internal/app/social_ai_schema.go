package app

import (
	"database/sql"
	"encoding/json"
	"path/filepath"
)

const legacyTables = 8

var aiProviders = []string{"openrouter", "orcarouter", "ollama-local", "ollama-cloud"}

func (s *Store) migrateSocialAI(version int) error {
	tx, err := s.DB.Begin()
	if err != nil {
		return err
	}
	defer tx.Rollback()
	if version == 1 {
		before, e := snapshotTables(tx, tableColumns[:legacyTables], 1)
		if e != nil {
			return e
		}
		if _, e = writeBackup(filepath.Join(s.Dir, "migration-backups"), before); e != nil {
			return e
		}
	}
	_, err = tx.Exec(`
 CREATE TABLE IF NOT EXISTS case_policies(case_id INTEGER PRIMARY KEY REFERENCES cases(id) ON DELETE CASCADE,classification TEXT NOT NULL CHECK(classification IN ('public','internal','restricted')));
 CREATE TABLE IF NOT EXISTS social_sources(feed_id INTEGER PRIMARY KEY REFERENCES feeds(id) ON DELETE CASCADE,provider TEXT NOT NULL CHECK(provider IN ('mastodon','bluesky')),kind TEXT NOT NULL CHECK(kind IN ('tag','account','search')),target TEXT NOT NULL,origin TEXT NOT NULL,interval INTEGER NOT NULL CHECK(interval BETWEEN 15 AND 1440),window_hours INTEGER NOT NULL CHECK(window_hours BETWEEN 1 AND 168),next_at TEXT NOT NULL DEFAULT '',failures INTEGER NOT NULL DEFAULT 0,ai_enabled INTEGER NOT NULL DEFAULT 0 CHECK(ai_enabled IN (0,1)),criteria TEXT NOT NULL DEFAULT '',revision INTEGER NOT NULL DEFAULT 1,ai_error TEXT NOT NULL DEFAULT '');
 CREATE TABLE IF NOT EXISTS social_runs(id INTEGER PRIMARY KEY,feed_id INTEGER NOT NULL REFERENCES social_sources(feed_id) ON DELETE CASCADE,collected TEXT NOT NULL,window_start TEXT NOT NULL,posts TEXT NOT NULL);
 CREATE TABLE IF NOT EXISTS service_waits(service TEXT PRIMARY KEY,until_at TEXT NOT NULL);
 CREATE TABLE IF NOT EXISTS ai_configs(provider TEXT PRIMARY KEY,value TEXT NOT NULL);
 CREATE TABLE IF NOT EXISTS ai_global(id INTEGER PRIMARY KEY CHECK(id=1),active TEXT NOT NULL,daily_micro INTEGER NOT NULL CHECK(daily_micro BETWEEN 1 AND 100000000),daily_calls INTEGER NOT NULL CHECK(daily_calls BETWEEN 1 AND 1000),revision INTEGER NOT NULL DEFAULT 1);
 CREATE TABLE IF NOT EXISTS ai_previews(id INTEGER PRIMARY KEY,case_id INTEGER NOT NULL REFERENCES cases(id) ON DELETE CASCADE,provider TEXT NOT NULL,config_revision INTEGER NOT NULL,case_revision INTEGER NOT NULL,input TEXT NOT NULL,input_hash TEXT NOT NULL,created TEXT NOT NULL);
 CREATE TABLE IF NOT EXISTS ai_jobs(id INTEGER PRIMARY KEY,kind TEXT NOT NULL CHECK(kind IN ('topics','assistant')),feed_id INTEGER,run_id INTEGER,case_id INTEGER,provider TEXT NOT NULL,config TEXT NOT NULL,input TEXT NOT NULL,input_hash TEXT NOT NULL,dedupe TEXT NOT NULL UNIQUE,state TEXT NOT NULL CHECK(state IN ('queued','running','succeeded','failed')),result TEXT NOT NULL DEFAULT '{}',error TEXT NOT NULL DEFAULT '',reserved INTEGER NOT NULL CHECK(reserved>=0),actual INTEGER,created TEXT NOT NULL,finished TEXT NOT NULL DEFAULT '');
 CREATE TABLE IF NOT EXISTS ai_reservations(job_id INTEGER NOT NULL REFERENCES ai_jobs(id) ON DELETE CASCADE,day TEXT NOT NULL,amount INTEGER NOT NULL CHECK(amount>=0),PRIMARY KEY(job_id,day));
 CREATE INDEX IF NOT EXISTS ai_jobs_queue ON ai_jobs(state,id);
 CREATE TABLE IF NOT EXISTS ai_reviews(job_id INTEGER NOT NULL REFERENCES ai_jobs(id) ON DELETE CASCADE,revision INTEGER NOT NULL,status TEXT NOT NULL CHECK(status IN ('draft','reviewed','rejected')),text TEXT NOT NULL,created TEXT NOT NULL,PRIMARY KEY(job_id,revision));
 INSERT OR IGNORE INTO ai_global VALUES(1,'openrouter',1000000,24,1);
 PRAGMA user_version=2;`)
	if err != nil {
		return err
	}
	for _, provider := range aiProviders {
		v := DefaultAIConfig(provider)
		b, _ := json.Marshal(v)
		if _, err = tx.Exec("INSERT OR IGNORE INTO ai_configs(provider,value) VALUES(?,?)", provider, string(b)); err != nil {
			return err
		}
	}
	if _, err = tx.Exec("UPDATE ai_jobs SET state='failed',error='処理が中断しました。生成は再送しません。',finished=? WHERE state='running'", now()); err != nil {
		return err
	}
	return tx.Commit()
}
func queryPolicy(tx *sql.Tx, id int64) (string, error) {
	var policy string
	err := tx.QueryRow("SELECT COALESCE((SELECT classification FROM case_policies WHERE case_id=c.id),'public') FROM cases c WHERE c.id=?", id).Scan(&policy)
	return policy, err
}
