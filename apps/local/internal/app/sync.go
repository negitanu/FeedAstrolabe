package app

import (
	"bytes"
	"context"
	"crypto/sha256"
	"database/sql"
	_ "embed"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"net/url"
	"os"
	"path/filepath"
	"regexp"
	"strings"
	"time"
)

//go:embed sync_schema.sql
var syncSchema string

const syncBatch = 100

type SyncEvent struct {
	ID    string          `json:"id"`
	Clock int64           `json:"clock"`
	Kind  string          `json:"kind"`
	Key   []string        `json:"key"`
	Value json.RawMessage `json:"value"`
}
type SyncRequest struct {
	Version int         `json:"version"`
	Cursor  int64       `json:"cursor"`
	Hub     string      `json:"hub"`
	Events  []SyncEvent `json:"events"`
}
type SyncResponse struct {
	Version int         `json:"version"`
	Cursor  int64       `json:"cursor"`
	Hub     string      `json:"hub"`
	More    bool        `json:"more"`
	Events  []SyncEvent `json:"events"`
}
type SyncConnection struct {
	URL         string `json:"url"`
	Enabled     bool   `json:"enabled"`
	Cursor      int64  `json:"cursor"`
	Sent        int64  `json:"sent"`
	Hub         string `json:"hub"`
	LastSuccess string `json:"lastSuccess"`
	Error       string `json:"error"`
	Pending     int    `json:"pending"`
}
type SyncPrepared struct {
	Request SyncRequest `json:"request"`
	Through int64       `json:"through"`
	URL     string      `json:"url"`
}

func syncJSON(v any) string {
	var b bytes.Buffer
	e := json.NewEncoder(&b)
	e.SetEscapeHTML(false)
	_ = e.Encode(v)
	return strings.TrimSuffix(b.String(), "\n")
}
func (s *Store) migrateSync() error {
	var exists int
	if e := s.DB.QueryRow("SELECT count(*) FROM sqlite_master WHERE name='sync_meta'").Scan(&exists); e != nil {
		return e
	}
	if exists == 0 {
		// VACUUM INTO is a consistent snapshot, including committed WAL data.
		// Back up settings-only libraries as well as libraries containing feeds.
		{
			dir := filepath.Join(s.Dir, "migration-backups")
			if e := os.MkdirAll(dir, 0700); e != nil {
				return e
			}
			path := filepath.Join(dir, "before-library-sync-"+time.Now().UTC().Format("20060102T150405.000000000")+".sqlite3")
			if _, e := s.DB.Exec("VACUUM INTO ?", path); e != nil {
				return e
			}
			if e := os.Chmod(path, 0600); e != nil {
				return e
			}
		}
	}
	tx, e := s.DB.Begin()
	if e != nil {
		return e
	}
	defer tx.Rollback()
	if exists == 0 {
		if e = canonicalSocialIDs(tx); e != nil {
			return e
		}
	}
	if _, e = tx.Exec(syncSchema); e != nil {
		return fmt.Errorf("sync schema: %w", e)
	}
	return tx.Commit()
}
func (s *Store) SyncConnection() (SyncConnection, error) {
	var v SyncConnection
	e := s.DB.QueryRow("SELECT url,enabled,cursor,sent,hub,last_success,error,(SELECT count(*) FROM sync_events WHERE seq>sent) FROM sync_connection WHERE id=1").Scan(&v.URL, &v.Enabled, &v.Cursor, &v.Sent, &v.Hub, &v.LastSuccess, &v.Error, &v.Pending)
	return v, e
}
func validSyncURL(raw string) (string, error) {
	if raw == "" {
		return "", nil
	}
	u, e := url.Parse(raw)
	if e != nil || u.User != nil || u.Hostname() == "" || u.RawQuery != "" || u.Fragment != "" || (u.Path != "" && u.Path != "/") || (u.Scheme != "https" && !(u.Scheme == "http" && (u.Hostname() == "127.0.0.1" || u.Hostname() == "localhost"))) {
		return "", errors.New("同期先はHTTPSのサイトURLを指定してください（開発時のみlocalhostのHTTPを利用できます）")
	}
	return strings.TrimSuffix(u.String(), "/"), nil
}
func (s *Store) SaveSyncConnection(raw string, enabled bool) error {
	u, e := validSyncURL(raw)
	if e != nil {
		return e
	}
	if enabled && u == "" {
		return errors.New("同期先を入力してください")
	}
	old, e := s.SyncConnection()
	if e != nil {
		return e
	}
	if old.URL != u {
		_, e = s.DB.Exec("UPDATE sync_connection SET url=?,enabled=?,cursor=0,sent=0,hub='',last_success='',error='' WHERE id=1", u, enabled)
	} else {
		_, e = s.DB.Exec("UPDATE sync_connection SET enabled=?,error='' WHERE id=1", enabled)
	}
	return e
}
func (s *Store) PrepareSync() (SyncPrepared, error) {
	v, e := s.SyncConnection()
	if e != nil {
		return SyncPrepared{}, e
	}
	if !v.Enabled {
		return SyncPrepared{}, errors.New("同期は停止中です")
	}
	out := SyncPrepared{URL: v.URL, Through: v.Sent, Request: SyncRequest{Version: 1, Cursor: v.Cursor, Hub: v.Hub, Events: []SyncEvent{}}}
	rows, e := s.DB.Query("SELECT seq,event_id,clock,kind,entity_key,value FROM sync_events WHERE seq>? ORDER BY seq LIMIT ?", v.Sent, syncBatch)
	if e != nil {
		return out, e
	}
	defer rows.Close()
	size := 0
	for rows.Next() {
		var seq int64
		var ev SyncEvent
		var key, value string
		if e = rows.Scan(&seq, &ev.ID, &ev.Clock, &ev.Kind, &key, &value); e != nil {
			return out, e
		}
		if e = json.Unmarshal([]byte(key), &ev.Key); e != nil {
			return out, e
		}
		length := len(value) + len(key) + 256
		if len(out.Request.Events) > 0 && size+length > 8*1024*1024 {
			break
		}
		size += length
		out.Through = seq
		ev.Value = json.RawMessage(value)
		out.Request.Events = append(out.Request.Events, ev)
	}
	return out, rows.Err()
}

var syncID = regexp.MustCompile(`^[0-9a-f]{32}$`)

func validateSyncEvent(ev SyncEvent) error {
	if !syncID.MatchString(ev.ID) || ev.Clock < 0 || ev.Clock >= 9007199254739991 {
		return errors.New("同期イベントIDまたはclockが不正です")
	}
	n := 1
	switch ev.Kind {
	case "article", "read", "star":
		n = 2
	case "polling":
		n = 0
	case "feed", "delete", "collection", "enabled":
	default:
		return errors.New("未対応の同期イベントです")
	}
	if ev.Key == nil || len(ev.Key) != n {
		return errors.New("同期キーが不正です")
	}
	for _, p := range ev.Key {
		if p == "" || len(p) > 8192 || strings.ContainsRune(p, 0) {
			return errors.New("同期キーが不正です")
		}
	}
	if len(ev.Key) > 0 {
		u, e := url.Parse(ev.Key[0])
		if e != nil || u.User != nil || !((u.Scheme == "http" || u.Scheme == "https") && u.Host != "" || (u.Scheme == "social" || u.Scheme == "social-topic") && regexp.MustCompile(`^[0-9a-f]{64}$`).MatchString(u.Opaque)) {
			return errors.New("購読識別子が不正です")
		}
	}
	var fields map[string]json.RawMessage
	if e := decodeStrict(ev.Value, &fields); e != nil {
		return e
	}
	var stringsRequired []string
	switch ev.Kind {
	case "feed":
		stringsRequired = []string{"title", "folder", "source", "kind", "target", "origin"}
	case "article":
		stringsRequired = []string{"title", "url", "content", "published", "collected"}
	case "collection":
		stringsRequired = []string{"checked", "error"}
	}
	for _, name := range stringsRequired {
		raw := bytes.TrimSpace(fields[name])
		if len(raw) == 0 || raw[0] != '"' {
			return errors.New("同期文字列の型が不正です")
		}
	}
	var target any
	switch ev.Kind {
	case "feed":
		target = &syncFeed{}
	case "article":
		target = &syncArticle{}
	case "collection":
		target = &syncCollection{}
	case "read", "star", "polling", "enabled":
		var v struct {
			Value *int `json:"value"`
		}
		if e := decodeStrict(ev.Value, &v); e != nil {
			return e
		}
		if v.Value == nil || (*v.Value != 0 && *v.Value != 1) || len(fields) != 1 {
			return errors.New("同期状態が不正です")
		}
		return nil
	case "delete":
		if len(fields) != 0 {
			return errors.New("削除イベントが不正です")
		}
		return nil
	}
	if e := decodeStrict(ev.Value, target); e != nil {
		return e
	}
	switch v := target.(type) {
	case *syncFeed:
		if len(fields) != 8 || v.Enabled < 0 || v.Enabled > 1 || v.Interval < 60 || v.Interval > 86400 || len([]rune(v.Title)) > 1000 || len([]rune(v.Folder)) > 80 || len(v.Target) > 8192 || len(v.Origin) > 8192 {
			return errors.New("同期購読設定が不正です")
		}
		if !strings.Contains("|rss|mastodon|bluesky|page|x|", "|"+v.Source+"|") || !strings.Contains("||account|topic|tag|search|", "|"+v.Kind+"|") {
			return errors.New("同期情報源が不正です")
		}
	case *syncArticle:
		if len(fields) != 5 || len(v.Content) > 2*1024*1024 || len(v.Title) > 8192 || len(v.URL) > 8192 {
			return errors.New("同期記事が大きすぎます")
		}
		if _, e := syncTime(v.Published); e != nil || v.Published == "" {
			return errors.New("公開日時が不正です")
		}
		if _, e := syncTime(v.Collected); e != nil {
			return e
		}
		if v.URL != "" {
			u, e := url.Parse(v.URL)
			if e != nil || u.User != nil || (u.Scheme != "https" && u.Scheme != "http") {
				return errors.New("記事URLが不正です")
			}
		}
	case *syncCollection:
		if len(fields) != 2 || len(v.Error) > 8192 {
			return errors.New("収集結果が不正です")
		}
		if _, e := syncTime(v.Checked); e != nil {
			return e
		}
	}
	return nil
}

type syncFeed struct {
	Title    string `json:"title"`
	Folder   string `json:"folder"`
	Enabled  int    `json:"enabled"`
	Source   string `json:"source"`
	Kind     string `json:"kind"`
	Target   string `json:"target"`
	Origin   string `json:"origin"`
	Interval int    `json:"interval"`
}
type syncArticle struct {
	Title     string `json:"title"`
	URL       string `json:"url"`
	Content   string `json:"content"`
	Published string `json:"published"`
	Collected string `json:"collected"`
}
type syncCollection struct {
	Checked string `json:"checked"`
	Error   string `json:"error"`
}

func syncTime(raw string) (string, error) {
	if raw == "" {
		return "", nil
	}
	for _, f := range []string{time.RFC3339Nano, "2006-01-02 15:04:05"} {
		if t, e := time.Parse(f, raw); e == nil {
			return t.UTC().Format(timestampFormat), nil
		}
	}
	return "", errors.New("同期日時が不正です")
}
func newerSync(clock int64, id string, previousClock int64, previousID string) bool {
	return clock > previousClock || (clock == previousClock && id > previousID)
}
func materializeSync(tx *sql.Tx, ev SyncEvent) error {
	if ev.Kind == "polling" {
		var v struct {
			Value int `json:"value"`
		}
		_ = json.Unmarshal(ev.Value, &v)
		_, e := tx.Exec("UPDATE settings SET value=json_set(value,'$.pauseCollection',json(?)) WHERE id=1", map[bool]string{true: "true", false: "false"}[v.Value == 0])
		return e
	}
	identity := syncJSON(ev.Key[:1])
	var dc, fc int64
	var di, fi string
	de := tx.QueryRow("SELECT clock,event_id FROM sync_versions WHERE kind='delete' AND entity_key=?", identity).Scan(&dc, &di)
	fe := tx.QueryRow("SELECT clock,event_id FROM sync_versions WHERE kind='feed' AND entity_key=?", identity).Scan(&fc, &fi)
	if de != nil && !errors.Is(de, sql.ErrNoRows) {
		return de
	}
	if fe != nil && !errors.Is(fe, sql.ErrNoRows) {
		return fe
	}
	if ev.Kind != "delete" && de == nil && (fe != nil || !newerSync(fc, fi, dc, di)) {
		return nil
	}
	if ev.Kind != "feed" && ev.Kind != "delete" && de == nil && !newerSync(ev.Clock, ev.ID, dc, di) {
		return nil
	}
	if ev.Kind == "delete" {
		if _, e := tx.Exec("DELETE FROM feeds WHERE url=?", ev.Key[0]); e != nil {
			return e
		}
		if fe == nil && !newerSync(ev.Clock, ev.ID, fc, fi) {
			var value string
			if e := tx.QueryRow("SELECT value FROM sync_versions WHERE kind='feed' AND entity_key=?", identity).Scan(&value); e != nil {
				return e
			}
			return materializeSync(tx, SyncEvent{ID: fi, Clock: fc, Kind: "feed", Key: ev.Key, Value: json.RawMessage(value)})
		}
		return nil
	}
	var id int64
	e := tx.QueryRow("SELECT id FROM feeds WHERE url=?", ev.Key[0]).Scan(&id)
	if ev.Kind == "feed" {
		var v syncFeed
		_ = json.Unmarshal(ev.Value, &v)
		var enabledValue, stateID string
		var stateClock int64
		stateErr := tx.QueryRow("SELECT value,clock,event_id FROM sync_versions WHERE kind='enabled' AND entity_key=?", identity).Scan(&enabledValue, &stateClock, &stateID)
		if stateErr == nil && (de != nil || newerSync(stateClock, stateID, dc, di)) {
			var state struct {
				Value int `json:"value"`
			}
			_ = json.Unmarshal([]byte(enabledValue), &state)
			v.Enabled = state.Value
		} else if stateErr != nil && !errors.Is(stateErr, sql.ErrNoRows) {
			return stateErr
		}
		var folder any
		if v.Folder != "" {
			var fid int64
			err := tx.QueryRow("SELECT id FROM folders WHERE name=? ORDER BY id LIMIT 1", v.Folder).Scan(&fid)
			if errors.Is(err, sql.ErrNoRows) {
				r, err := tx.Exec("INSERT INTO folders(name,position,expanded) VALUES(?,(SELECT COALESCE(max(position),0)+1 FROM folders),0)", v.Folder)
				if err != nil {
					return err
				}
				fid, _ = r.LastInsertId()
			} else if err != nil {
				return err
			}
			folder = fid
		}
		if errors.Is(e, sql.ErrNoRows) {
			r, err := tx.Exec("INSERT INTO feeds(title,url,folder_id,position,paused) VALUES(?,?,?,(SELECT COALESCE(max(position),0)+1 FROM feeds),?)", v.Title, ev.Key[0], folder, v.Enabled == 0 || v.Source == "x")
			if err != nil {
				return err
			}
			id, _ = r.LastInsertId()
		} else if e != nil {
			return e
		} else {
			if _, e = tx.Exec("UPDATE feeds SET title=?,folder_id=?,paused=? WHERE id=?", v.Title, folder, v.Enabled == 0 || v.Source == "x", id); e != nil {
				return e
			}
		}
		if _, e = tx.Exec("INSERT INTO sync_feed_meta VALUES(?,?,?,?,?,?) ON CONFLICT(feed_id) DO UPDATE SET source=excluded.source,kind=excluded.kind,target=excluded.target,origin=excluded.origin,interval=excluded.interval", id, v.Source, v.Kind, v.Target, v.Origin, v.Interval); e != nil {
			return e
		}
		if v.Source == "mastodon" || v.Source == "bluesky" {
			kind := v.Kind
			if kind == "topic" {
				if v.Source == "mastodon" {
					kind = "tag"
				} else {
					kind = "search"
				}
			}
			if _, e = tx.Exec("INSERT INTO social_sources(feed_id,provider,kind,target,origin,interval,window_hours) VALUES(?,?,?,?,?,?,24) ON CONFLICT(feed_id) DO UPDATE SET provider=excluded.provider,kind=excluded.kind,target=excluded.target,origin=excluded.origin,interval=excluded.interval", id, v.Source, kind, v.Target, v.Origin, max(15, v.Interval/60)); e != nil {
				return e
			}
		}
		rows, err := tx.Query("SELECT event_id,clock,kind,entity_key,value FROM sync_versions WHERE kind IN ('article','collection') AND json_extract(entity_key,'$[0]')=?", ev.Key[0])
		if err != nil {
			return err
		}
		pending := []SyncEvent{}
		for rows.Next() {
			var p SyncEvent
			var key, value string
			if err = rows.Scan(&p.ID, &p.Clock, &p.Kind, &key, &value); err != nil {
				rows.Close()
				return err
			}
			_ = json.Unmarshal([]byte(key), &p.Key)
			p.Value = json.RawMessage(value)
			if len(p.Key) > 0 && p.Key[0] == ev.Key[0] {
				pending = append(pending, p)
			}
		}
		err = rows.Err()
		rows.Close()
		if err != nil {
			return err
		}
		for _, p := range pending {
			if err = materializeSync(tx, p); err != nil {
				return err
			}
		}
		return nil
	}
	if errors.Is(e, sql.ErrNoRows) {
		return nil
	}
	if e != nil {
		return e
	}
	switch ev.Kind {
	case "enabled":
		var v struct {
			Value int `json:"value"`
		}
		_ = json.Unmarshal(ev.Value, &v)
		_, e = tx.Exec("UPDATE feeds SET paused=CASE WHEN (SELECT source FROM sync_feed_meta WHERE feed_id=feeds.id)='x' THEN 1 ELSE ? END WHERE id=?", v.Value == 0, id)
	case "collection":
		var v syncCollection
		_ = json.Unmarshal(ev.Value, &v)
		checked, _ := syncTime(v.Checked)
		_, e = tx.Exec("UPDATE feeds SET last_fetched=?,last_error=? WHERE id=?", checked, v.Error, id)
	case "article":
		var v syncArticle
		_ = json.Unmarshal(ev.Value, &v)
		pub, _ := syncTime(v.Published)
		collected, _ := syncTime(v.Collected)
		if collected == "" {
			collected = pub
		}
		_, e = tx.Exec("INSERT INTO articles(feed_id,uid,title,url,content,published,collected) VALUES(?,?,?,?,?,?,?) ON CONFLICT(feed_id,uid) DO UPDATE SET title=excluded.title,url=excluded.url,content=excluded.content,published=excluded.published", id, ev.Key[1], v.Title, v.URL, SanitizeRichHTML(v.Content, nil), pub, collected)
		if e != nil {
			return e
		}
		for _, state := range []struct{ kind, col string }{{"read", "is_read"}, {"star", "starred"}} {
			var value string
			var stateClock int64
			var stateID string
			err := tx.QueryRow("SELECT value,clock,event_id FROM sync_versions WHERE kind=? AND entity_key=?", state.kind, syncJSON(ev.Key)).Scan(&value, &stateClock, &stateID)
			if err == nil && de == nil && !newerSync(stateClock, stateID, dc, di) {
				continue
			}
			if err == nil {
				var v struct {
					Value int `json:"value"`
				}
				_ = json.Unmarshal([]byte(value), &v)
				if _, e = tx.Exec("UPDATE articles SET "+state.col+"=? WHERE feed_id=? AND uid=?", v.Value, id, ev.Key[1]); e != nil {
					return e
				}
			} else if !errors.Is(err, sql.ErrNoRows) {
				return err
			}
		}
	case "read", "star":
		var v struct {
			Value int `json:"value"`
		}
		_ = json.Unmarshal(ev.Value, &v)
		col := "is_read"
		if ev.Kind == "star" {
			col = "starred"
		}
		_, e = tx.Exec("UPDATE articles SET "+col+"=? WHERE feed_id=? AND uid=?", v.Value, id, ev.Key[1])
	}
	return e
}
func (s *Store) AcceptSync(prepared SyncPrepared, response SyncResponse) error {
	if response.Version != 1 || !syncID.MatchString(response.Hub) || response.Cursor < prepared.Request.Cursor || response.Events == nil || len(response.Events) > syncBatch || response.Cursor-prepared.Request.Cursor != int64(len(response.Events)) || (response.More && len(response.Events) == 0) {
		return errors.New("同期応答が不正です")
	}
	if prepared.Request.Hub != "" && prepared.Request.Hub != response.Hub {
		return errors.New("同期先のライブラリが変更されています")
	}
	for _, ev := range response.Events {
		if e := validateSyncEvent(ev); e != nil {
			return e
		}
	}
	tx, e := s.DB.Begin()
	if e != nil {
		return e
	}
	defer tx.Rollback()
	var u string
	var enabled bool
	var cursor, sent int64
	if e = tx.QueryRow("SELECT url,enabled,cursor,sent FROM sync_connection WHERE id=1").Scan(&u, &enabled, &cursor, &sent); e != nil {
		return e
	}
	if !enabled || u != prepared.URL || cursor != prepared.Request.Cursor || sent > prepared.Through {
		return errors.New("同期設定または状態が変更されました。再実行してください")
	}
	if _, e = tx.Exec("UPDATE sync_meta SET applying=1"); e != nil {
		return e
	}
	for _, ev := range response.Events {
		var pc int64
		var pk, pkey, pvalue string
		e = tx.QueryRow("SELECT clock,kind,entity_key,value FROM sync_events WHERE event_id=?", ev.ID).Scan(&pc, &pk, &pkey, &pvalue)
		if e == nil {
			var old, new any
			_ = json.Unmarshal([]byte(pvalue), &old)
			_ = json.Unmarshal(ev.Value, &new)
			if pc != ev.Clock || pk != ev.Kind || pkey != syncJSON(ev.Key) || syncJSON(old) != syncJSON(new) {
				return errors.New("同じイベントIDの内容が一致しません")
			}
			continue
		}
		if !errors.Is(e, sql.ErrNoRows) {
			return e
		}
		key := syncJSON(ev.Key)
		if _, e = tx.Exec("INSERT INTO sync_events(event_id,clock,kind,entity_key,value) VALUES(?,?,?,?,?)", ev.ID, ev.Clock, ev.Kind, key, string(ev.Value)); e != nil {
			return e
		}
		if _, e = tx.Exec("UPDATE sync_meta SET clock=max(clock,?)", ev.Clock); e != nil {
			return e
		}
		var clock int64
		var id string
		e = tx.QueryRow("SELECT clock,event_id FROM sync_versions WHERE kind=? AND entity_key=?", ev.Kind, key).Scan(&clock, &id)
		if e == nil && !newerSync(ev.Clock, ev.ID, clock, id) {
			continue
		}
		if e != nil && !errors.Is(e, sql.ErrNoRows) {
			return e
		}
		if _, e = tx.Exec("INSERT INTO sync_versions VALUES(?,?,?,?,?) ON CONFLICT(kind,entity_key) DO UPDATE SET clock=excluded.clock,event_id=excluded.event_id,value=excluded.value", ev.Kind, key, ev.Clock, ev.ID, string(ev.Value)); e != nil {
			return e
		}
		if e = materializeSync(tx, ev); e != nil {
			return e
		}
	}
	if _, e = tx.Exec("UPDATE sync_meta SET applying=0"); e != nil {
		return e
	}
	if _, e = tx.Exec("UPDATE sync_connection SET cursor=?,sent=?,hub=?,last_success=?,error='' WHERE id=1", response.Cursor, prepared.Through, response.Hub, now()); e != nil {
		return e
	}
	return tx.Commit()
}
func (s *Server) syncCall(_ context.Context, op string, data json.RawMessage) (any, error) {
	switch op {
	case "sync.status":
		return s.Store.SyncConnection()
	case "sync.settings":
		v, e := input[struct {
			URL     string `json:"url"`
			Enabled bool   `json:"enabled"`
		}](data)
		if e != nil {
			return nil, e
		}
		return nil, s.Store.SaveSyncConnection(v.URL, v.Enabled)
	case "sync.prepare":
		return s.Store.PrepareSync()
	case "sync.accept":
		v, e := input[struct {
			Prepared SyncPrepared `json:"prepared"`
			Response SyncResponse `json:"response"`
		}](data)
		if e != nil {
			return nil, e
		}
		return nil, s.Store.AcceptSync(v.Prepared, v.Response)
	case "sync.error":
		v, e := input[struct {
			Error string `json:"error"`
		}](data)
		if e != nil {
			return nil, e
		}
		if len(v.Error) > 1000 {
			v.Error = v.Error[:1000]
		}
		_, e = s.Store.DB.Exec("UPDATE sync_connection SET error=? WHERE id=1", v.Error)
		return nil, e
	}
	return nil, errors.New("未対応の同期操作です")
}

func canonicalSocialIDs(tx *sql.Tx) error {
	rows, err := tx.Query("SELECT feed_id,provider,kind,target,origin FROM social_sources")
	if err != nil {
		return err
	}
	type change struct {
		id  int64
		url string
	}
	changes := []change{}
	for rows.Next() {
		var id int64
		var provider, kind, target, origin string
		if err = rows.Scan(&id, &provider, &kind, &target, &origin); err != nil {
			rows.Close()
			return err
		}
		h := sha256.Sum256([]byte(provider + "\n" + origin + "\n" + target))
		identity := "social-topic:" + hex.EncodeToString(h[:])
		if kind == "account" {
			identity = origin + "/@" + strings.ToLower(target)
		}
		changes = append(changes, change{id, identity})
	}
	err = rows.Err()
	rows.Close()
	if err != nil {
		return err
	}
	for _, v := range changes {
		if _, err = tx.Exec("UPDATE feeds SET url=? WHERE id=? AND url LIKE 'social:%'", v.url, v.id); err != nil {
			return err
		}
	}
	return nil
}
