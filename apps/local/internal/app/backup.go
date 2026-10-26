package app

import (
	"bytes"
	"database/sql"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"time"
)

type Table struct {
	Name string  `json:"name"`
	Rows [][]any `json:"rows"`
}
type Backup struct {
	Format  string  `json:"format"`
	Version int     `json:"version"`
	Created string  `json:"created"`
	Tables  []Table `json:"tables"`
}

type tableDef = struct {
	name, cols string
	n          int
}

const preSyncTables = 18

var tableColumns = []struct {
	name, cols string
	n          int
}{
	{"folders", "id,name,position,expanded", 4},
	{"feeds", "id,folder_id,title,url,site_url,position,paused,last_fetched,last_error", 9},
	{"articles", "id,feed_id,uid,title,url,content,published,collected,is_read,starred,viewed", 11},
	{"cases", "id,title,note,revision,archived,updated", 6},
	{"note_revisions", "case_id,revision,note,created", 4},
	{"case_articles", "case_id,article_id", 2},
	{"evidence", "id,case_id,article_id,title,url,content,captured,hash", 8},
	{"settings", "id,value", 2},
	{"case_policies", "case_id,classification", 2},
	{"social_sources", "feed_id,provider,kind,target,origin,interval,window_hours,next_at,failures,ai_enabled,criteria,revision,ai_error", 13},
	{"social_runs", "id,feed_id,collected,window_start,posts", 5},
	{"service_waits", "service,until_at", 2},
	{"ai_configs", "provider,value", 2},
	{"ai_global", "id,active,daily_micro,daily_calls,revision", 5},
	{"ai_previews", "id,case_id,provider,config_revision,case_revision,input,input_hash,created", 8},
	{"ai_jobs", "id,kind,feed_id,run_id,case_id,provider,config,input,input_hash,dedupe,state,result,error,reserved,actual,created,finished", 17},
	{"ai_reservations", "job_id,day,amount", 3},
	{"ai_reviews", "job_id,revision,status,text,created", 5},
	{"sync_feed_meta", "feed_id,source,kind,target,origin,interval", 6},
}

func snapshot(tx *sql.Tx) (Backup, error) { return snapshotTables(tx, tableColumns, 3) }
func snapshotTables(tx *sql.Tx, defs []tableDef, version int) (Backup, error) {
	out := Backup{Format: "feedastrolabe-local-backup", Version: version, Created: now(), Tables: []Table{}}
	for _, def := range defs {
		rows, err := tx.Query("SELECT " + def.cols + " FROM " + def.name)
		if err != nil {
			return out, err
		}
		t := Table{Name: def.name, Rows: [][]any{}}
		for rows.Next() {
			vals := make([]any, def.n)
			ptrs := make([]any, def.n)
			for i := range vals {
				ptrs[i] = &vals[i]
			}
			if err = rows.Scan(ptrs...); err != nil {
				rows.Close()
				return out, err
			}
			for i, v := range vals {
				if b, ok := v.([]byte); ok {
					vals[i] = string(b)
				}
			}
			t.Rows = append(t.Rows, vals)
		}
		err = rows.Err()
		rows.Close()
		if err != nil {
			return out, err
		}
		out.Tables = append(out.Tables, t)
	}
	return out, nil
}
func (s *Store) Backup() (Backup, error) {
	tx, err := s.DB.Begin()
	if err != nil {
		return Backup{}, err
	}
	defer tx.Rollback()
	out, err := snapshot(tx)
	if err != nil {
		return out, err
	}
	return out, tx.Commit()
}
func decodeStrict(data []byte, out any) error {
	if err := uniqueJSON(data); err != nil {
		return err
	}
	d := json.NewDecoder(bytes.NewReader(data))
	d.DisallowUnknownFields()
	d.UseNumber()
	if err := d.Decode(out); err != nil {
		return err
	}
	if err := d.Decode(new(any)); err != io.EOF {
		return errors.New("JSON末尾が不正です")
	}
	return nil
}
func writeBackup(dir string, v Backup) (string, error) {
	if err := os.MkdirAll(dir, 0700); err != nil {
		return "", err
	}
	b, err := json.MarshalIndent(v, "", "  ")
	if err != nil {
		return "", err
	}
	f, err := os.CreateTemp(dir, "pre-restore-"+time.Now().UTC().Format("20060102T150405")+"-*.json")
	if err != nil {
		return "", err
	}
	name := f.Name()
	if err = f.Chmod(0600); err != nil {
		f.Close()
		os.Remove(name)
		return "", err
	}
	if _, err = f.Write(b); err != nil {
		f.Close()
		os.Remove(name)
		return "", err
	}
	if err = f.Sync(); err != nil {
		f.Close()
		return "", err
	}
	return name, f.Close()
}
func (s *Store) Restore(data []byte) (string, error) {
	if len(data) > 64*1024*1024 {
		return "", errors.New("バックアップは64MiBまでです")
	}
	var v Backup
	if err := decodeStrict(data, &v); err != nil {
		return "", errors.New("バックアップJSONが不正です")
	}
	if v.Version == 1 && len(v.Tables) == legacyTables {
		for _, def := range tableColumns[legacyTables:preSyncTables] {
			v.Tables = append(v.Tables, Table{Name: def.name, Rows: [][]any{}})
		}
		v.Version = 2
	}
	if v.Version == 2 && len(v.Tables) == preSyncTables {
		for _, def := range tableColumns[preSyncTables:] {
			v.Tables = append(v.Tables, Table{Name: def.name, Rows: [][]any{}})
		}
		v.Version = 3
	}
	if v.Format != "feedastrolabe-local-backup" || v.Version != 3 || len(v.Tables) != len(tableColumns) {
		return "", errors.New("未対応のバックアップ形式です")
	}
	total := 0
	for i, t := range v.Tables {
		if t.Name != tableColumns[i].name {
			return "", errors.New("バックアップのテーブル構成が不正です")
		}
		total += len(t.Rows)
		if total > 200000 {
			return "", errors.New("バックアップの行数が多すぎます")
		}
		for _, row := range t.Rows {
			if len(row) != tableColumns[i].n {
				return "", errors.New("バックアップの列数が不正です")
			}
			for j, val := range row {
				switch x := val.(type) {
				case json.Number:
					n, err := x.Int64()
					if err != nil {
						return "", errors.New("整数が不正です")
					}
					row[j] = n
				case nil, string:
				default:
					return "", errors.New("値の型が不正です")
				}
			}
		}
	}

	// Canonical UTC timestamps keep text ordering and inclusive date filters correct.
	for _, table := range v.Tables {
		for _, row := range table.Rows {
			var indices []int
			switch table.Name {
			case "feeds":
				indices = []int{7}
			case "articles":
				indices = []int{6, 7, 10}
			case "cases":
				indices = []int{5}
			case "note_revisions":
				indices = []int{3}
			case "evidence":
				indices = []int{6}
			}
			for _, index := range indices {
				raw, ok := row[index].(string)
				if !ok {
					return "", errors.New("日時の型が不正です")
				}
				if raw == "" && (table.Name == "feeds" || (table.Name == "articles" && index == 10)) {
					continue
				}
				parsed, err := time.Parse(time.RFC3339Nano, raw)
				if err != nil {
					return "", errors.New("日時が不正です")
				}
				row[index] = parsed.UTC().Format(timestampFormat)
			}
		}
	}
	tx, err := s.DB.Begin()
	if err != nil {
		return "", err
	}
	defer tx.Rollback()
	before, err := snapshot(tx)
	if err != nil {
		return "", err
	}
	if _, err = tx.Exec("UPDATE sync_meta SET applying=1"); err != nil {
		return "", err
	}
	for i := len(tableColumns) - 1; i >= 0; i-- {
		if _, err = tx.Exec("DELETE FROM " + tableColumns[i].name); err != nil {
			return "", err
		}
	}
	for i, t := range v.Tables {
		def := tableColumns[i]
		ps := "?"
		for j := 1; j < def.n; j++ {
			ps += ",?"
		}
		for _, row := range t.Rows {
			if _, err = tx.Exec("INSERT INTO "+def.name+" ("+def.cols+") VALUES("+ps+")", row...); err != nil {
				return "", fmt.Errorf("復元データの参照・制約が不正です: %w", err)
			}
		}
	}
	// Validate semantic invariants before committing; invalid input rolls back the whole library.
	var settingsJSON string
	var settings Settings
	if err = tx.QueryRow("SELECT value FROM settings WHERE id=1").Scan(&settingsJSON); err != nil {
		return "", err
	}
	if err = json.Unmarshal([]byte(settingsJSON), &settings); err != nil {
		return "", err
	}
	if err = validateSettings(settings); err != nil {
		return "", err
	}
	for _, q := range []string{
		"SELECT count(*) FROM folders WHERE id<=0 OR length(trim(name))=0 OR expanded NOT IN (0,1)",
		"SELECT count(*) FROM feeds WHERE id<=0 OR length(trim(title))=0 OR paused NOT IN (0,1)",
		"SELECT count(*) FROM articles WHERE id<=0 OR uid='' OR is_read NOT IN (0,1) OR starred NOT IN (0,1)",
		"SELECT count(*) FROM sync_feed_meta WHERE source NOT IN ('rss','mastodon','bluesky','page','x') OR interval<60 OR interval>86400",
		"SELECT count(*) FROM cases WHERE id<=0 OR length(trim(title))=0 OR revision<1 OR archived NOT IN (0,1)",
		"SELECT count(*) FROM cases c WHERE NOT EXISTS(SELECT 1 FROM note_revisions n WHERE n.case_id=c.id AND n.revision=c.revision AND n.note=c.note)",
	} {
		var n int
		if err = tx.QueryRow(q).Scan(&n); err != nil {
			return "", err
		}
		if n > 0 {
			return "", errors.New("バックアップの値またはメモ版が不正です")
		}
	}
	rows, err := tx.Query("SELECT url FROM feeds WHERE id NOT IN (SELECT feed_id FROM social_sources)")
	if err != nil {
		return "", err
	}
	for rows.Next() {
		var u string
		if err = rows.Scan(&u); err != nil {
			rows.Close()
			return "", err
		}
		if _, err = parseURL(u); err != nil {
			rows.Close()
			return "", err
		}
	}
	err = rows.Err()
	rows.Close()
	if err != nil {
		return "", err
	}
	rows, err = tx.Query("SELECT title,url,content,hash FROM evidence")
	if err != nil {
		return "", err
	}
	for rows.Next() {
		var title, u, content, h string
		if err = rows.Scan(&title, &u, &content, &h); err != nil {
			rows.Close()
			return "", err
		}
		if hashEvidence(title, u, content) != h {
			rows.Close()
			return "", errors.New("根拠のハッシュが一致しません")
		}
	}
	err = rows.Err()
	rows.Close()
	if err != nil {
		return "", err
	}
	rows, err = tx.Query("PRAGMA foreign_key_check")
	if err != nil {
		return "", err
	}
	invalid := rows.Next()
	err = rows.Err()
	rows.Close()
	if err != nil {
		return "", err
	}
	if invalid {
		return "", errors.New("参照整合性が不正です")
	}
	if err = canonicalSocialIDs(tx); err != nil {
		return "", err
	}
	// Restored data starts disconnected; old cursors/events must not escape to a peer.
	if _, err = tx.Exec("UPDATE sync_meta SET applying=1,initialized=0; DELETE FROM sync_events; DELETE FROM sync_versions; UPDATE sync_connection SET url='',enabled=0,cursor=0,sent=0,hub='',last_success='',error='';"); err != nil {
		return "", err
	}
	if _, err = tx.Exec(syncSchema); err != nil {
		return "", err
	}
	if err = resetRestoredAI(tx); err != nil {
		return "", err
	}
	path, err := writeBackup(filepath.Join(s.Dir, "backups"), before)
	if err != nil {
		return "", err
	}
	if err = tx.Commit(); err != nil {
		return "", err
	}
	return path, nil
}
