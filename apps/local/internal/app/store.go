package app

import (
	"context"
	"database/sql"
	"encoding/json"
	"errors"
	"fmt"
	_ "modernc.org/sqlite"
	"os"
	"path/filepath"
	"strings"
	"time"
)

type Store struct {
	DB  *sql.DB
	Dir string
}
type Folder struct {
	ID       int64  `json:"id"`
	Name     string `json:"name"`
	Position int    `json:"position"`
	Expanded bool   `json:"expanded"`
}
type Feed struct {
	Interval    int    `json:"interval"`
	ID          int64  `json:"id"`
	FolderID    int64  `json:"folderId"`
	Title       string `json:"title"`
	URL         string `json:"url"`
	SiteURL     string `json:"siteUrl"`
	Position    int    `json:"position"`
	Paused      bool   `json:"paused"`
	LastFetched string `json:"lastFetched"`
	LastError   string `json:"lastError"`
}
type Article struct {
	ID        int64  `json:"id"`
	FeedID    int64  `json:"feedId"`
	FeedTitle string `json:"feedTitle"`
	UID       string `json:"uid"`
	Title     string `json:"title"`
	URL       string `json:"url"`
	Content   string `json:"content"`
	Published string `json:"published"`
	Collected string `json:"collected"`
	Read      bool   `json:"read"`
	Starred   bool   `json:"starred"`
	Viewed    string `json:"viewed"`
}
type Case struct {
	Classification string `json:"classification,omitempty"`
	ID             int64  `json:"id"`
	Title          string `json:"title"`
	Note           string `json:"note"`
	Revision       int    `json:"revision"`
	Archived       bool   `json:"archived"`
	Updated        string `json:"updated"`
}
type Revision struct {
	CaseID   int64  `json:"caseId"`
	Revision int    `json:"revision"`
	Note     string `json:"note"`
	Created  string `json:"created"`
}
type Link struct {
	CaseID    int64 `json:"caseId"`
	ArticleID int64 `json:"articleId"`
}
type Evidence struct {
	ID        int64  `json:"id"`
	CaseID    int64  `json:"caseId"`
	ArticleID int64  `json:"articleId"`
	Title     string `json:"title"`
	URL       string `json:"url"`
	Content   string `json:"content"`
	Captured  string `json:"captured"`
	Hash      string `json:"hash"`
}
type Settings struct {
	PauseCollection bool   `json:"pauseCollection,omitempty"`
	Theme           string `json:"theme"`
	Interval        int    `json:"interval"`
	Sidebar         int    `json:"sidebar"`
	View            string `json:"view"`
	Timezone        string `json:"timezone"`
}

var DefaultSettings = Settings{Theme: "system", Interval: 15, Sidebar: 260, View: "standard", Timezone: "Asia/Tokyo"}

const timestampFormat = "2006-01-02T15:04:05.000000000Z"

func now() string { return time.Now().UTC().Format(timestampFormat) }
func Open(dir string) (*Store, error) {
	if err := os.MkdirAll(dir, 0700); err != nil {
		return nil, err
	}
	dbPath := filepath.Join(dir, "library.sqlite3")
	file, err := os.OpenFile(dbPath, os.O_CREATE|os.O_RDWR, 0600)
	if err != nil {
		return nil, err
	}
	if err = file.Close(); err != nil {
		return nil, err
	}
	if err = os.Chmod(dbPath, 0600); err != nil {
		return nil, err
	}
	db, err := sql.Open("sqlite", dbPath)
	if err != nil {
		return nil, err
	}
	db.SetMaxOpenConns(1)
	s := &Store{db, dir}
	for _, q := range []string{"PRAGMA foreign_keys=ON", "PRAGMA busy_timeout=5000", "PRAGMA journal_mode=WAL"} {
		if _, err = db.Exec(q); err != nil {
			db.Close()
			return nil, err
		}
	}
	var version int
	if err = db.QueryRow("PRAGMA user_version").Scan(&version); err != nil {
		db.Close()
		return nil, err
	}
	if version > 2 {
		db.Close()
		return nil, errors.New("新しいバージョンのDBです")
	}
	_, err = db.Exec(`
 CREATE TABLE IF NOT EXISTS folders(id INTEGER PRIMARY KEY,name TEXT NOT NULL,position INTEGER NOT NULL,expanded INTEGER NOT NULL DEFAULT 1);
 CREATE TABLE IF NOT EXISTS feeds(id INTEGER PRIMARY KEY,folder_id INTEGER REFERENCES folders(id) ON DELETE SET NULL,title TEXT NOT NULL,url TEXT NOT NULL UNIQUE,site_url TEXT NOT NULL DEFAULT '',position INTEGER NOT NULL,paused INTEGER NOT NULL DEFAULT 0,last_fetched TEXT NOT NULL DEFAULT '',last_error TEXT NOT NULL DEFAULT '');
 CREATE TABLE IF NOT EXISTS articles(id INTEGER PRIMARY KEY,feed_id INTEGER NOT NULL REFERENCES feeds(id) ON DELETE CASCADE,uid TEXT NOT NULL,title TEXT NOT NULL,url TEXT NOT NULL,content TEXT NOT NULL,published TEXT NOT NULL,collected TEXT NOT NULL,is_read INTEGER NOT NULL DEFAULT 0,starred INTEGER NOT NULL DEFAULT 0,viewed TEXT NOT NULL DEFAULT '',UNIQUE(feed_id,uid));
 CREATE INDEX IF NOT EXISTS articles_order ON articles(published DESC,id DESC);
 CREATE INDEX IF NOT EXISTS articles_feed ON articles(feed_id);
 CREATE TABLE IF NOT EXISTS cases(id INTEGER PRIMARY KEY,title TEXT NOT NULL,note TEXT NOT NULL DEFAULT '',revision INTEGER NOT NULL DEFAULT 0,archived INTEGER NOT NULL DEFAULT 0,updated TEXT NOT NULL);
 CREATE TABLE IF NOT EXISTS note_revisions(case_id INTEGER NOT NULL REFERENCES cases(id) ON DELETE CASCADE,revision INTEGER NOT NULL,note TEXT NOT NULL,created TEXT NOT NULL,PRIMARY KEY(case_id,revision));
 CREATE TABLE IF NOT EXISTS case_articles(case_id INTEGER NOT NULL REFERENCES cases(id) ON DELETE CASCADE,article_id INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,PRIMARY KEY(case_id,article_id));
 CREATE TABLE IF NOT EXISTS evidence(id INTEGER PRIMARY KEY,case_id INTEGER NOT NULL REFERENCES cases(id) ON DELETE CASCADE,article_id INTEGER,title TEXT NOT NULL,url TEXT NOT NULL,content TEXT NOT NULL,captured TEXT NOT NULL,hash TEXT NOT NULL);
 CREATE TABLE IF NOT EXISTS settings(id INTEGER PRIMARY KEY CHECK(id=1),value TEXT NOT NULL);
`)
	if err != nil {
		db.Close()
		return nil, err
	}
	b, _ := json.Marshal(DefaultSettings)
	_, err = db.Exec("INSERT OR IGNORE INTO settings VALUES(1,?)", string(b))
	if err != nil {
		db.Close()
		return nil, err
	}
	if err = os.Chmod(filepath.Join(dir, "library.sqlite3"), 0600); err != nil {
		db.Close()
		return nil, err
	}
	if err = s.migrateSocialAI(version); err != nil {
		db.Close()
		return nil, err
	}
	if err = s.migrateSync(); err != nil {
		db.Close()
		return nil, err
	}
	return s, nil
}
func (s *Store) Close() error { return s.DB.Close() }
func (s *Store) Settings() (Settings, error) {
	var b string
	v := DefaultSettings
	err := s.DB.QueryRow("SELECT value FROM settings WHERE id=1").Scan(&b)
	if err == nil {
		err = json.Unmarshal([]byte(b), &v)
	}
	return v, err
}
func validateSettings(v Settings) error {
	if v.Theme != "system" && v.Theme != "light" && v.Theme != "dark" {
		return errors.New("テーマが不正です")
	}
	if v.Interval < 1 || v.Interval > 1440 || v.Sidebar < 180 || v.Sidebar > 520 {
		return errors.New("更新間隔または幅が範囲外です")
	}
	if v.View != "standard" && v.View != "compact" && v.View != "tiles" {
		return errors.New("表示形式が不正です")
	}
	if v.Timezone != "UTC" && v.Timezone != "Asia/Tokyo" {
		return errors.New("タイムゾーンが不正です")
	}
	return nil
}
func (s *Store) SaveSettings(v Settings) error {
	if err := validateSettings(v); err != nil {
		return err
	}
	b, _ := json.Marshal(v)
	_, err := s.DB.Exec("UPDATE settings SET value=? WHERE id=1", string(b))
	return err
}
func (s *Store) Folders() ([]Folder, error) {
	rows, err := s.DB.Query("SELECT id,name,position,expanded FROM folders ORDER BY position,id")
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := []Folder{}
	for rows.Next() {
		var v Folder
		if err = rows.Scan(&v.ID, &v.Name, &v.Position, &v.Expanded); err != nil {
			return nil, err
		}
		out = append(out, v)
	}
	return out, rows.Err()
}
func (s *Store) Feeds() ([]Feed, error) {
	rows, err := s.DB.Query("SELECT f.id,COALESCE(f.folder_id,0),f.title,f.url,f.site_url,f.position,f.paused,f.last_fetched,f.last_error,COALESCE((SELECT interval FROM sync_feed_meta WHERE feed_id=f.id),0) FROM feeds f ORDER BY f.position,f.id")
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := []Feed{}
	for rows.Next() {
		var v Feed
		if err = rows.Scan(&v.ID, &v.FolderID, &v.Title, &v.URL, &v.SiteURL, &v.Position, &v.Paused, &v.LastFetched, &v.LastError, &v.Interval); err != nil {
			return nil, err
		}
		out = append(out, v)
	}
	return out, rows.Err()
}
func validName(v string) error {
	if strings.TrimSpace(v) == "" || len(v) > 512 {
		return errors.New("名前は1〜512バイトで入力してください")
	}
	return nil
}
func (s *Store) SaveFolder(v Folder) (int64, error) {
	if err := validName(v.Name); err != nil {
		return 0, err
	}
	if v.ID == 0 {
		r, err := s.DB.Exec("INSERT INTO folders(name,position,expanded) VALUES(?,(SELECT COALESCE(MAX(position),0)+1 FROM folders),1)", strings.TrimSpace(v.Name))
		if err != nil {
			return 0, err
		}
		return r.LastInsertId()
	}
	r, err := s.DB.Exec("UPDATE folders SET name=?,expanded=? WHERE id=?", strings.TrimSpace(v.Name), v.Expanded, v.ID)
	return v.ID, affected(r, err)
}
func affected(r sql.Result, err error) error {
	if err != nil {
		return err
	}
	n, err := r.RowsAffected()
	if err == nil && n == 0 {
		return sql.ErrNoRows
	}
	return err
}
func nullableID(id int64) any {
	if id == 0 {
		return nil
	}
	return id
}
func (s *Store) SaveFeed(v Feed) error {
	if err := validName(v.Title); err != nil {
		return err
	}
	if v.Interval != 0 && (v.Interval < 60 || v.Interval > 86400) {
		return errors.New("収集間隔は60〜86400秒で指定してください")
	}
	var source string
	lookup := s.DB.QueryRow("SELECT source FROM sync_feed_meta WHERE feed_id=?", v.ID).Scan(&source)
	if lookup != nil && !errors.Is(lookup, sql.ErrNoRows) {
		return lookup
	}
	if source == "x" && !v.Paused {
		return errors.New("X収集は終了しているため再開できません")
	}
	tx, err := s.DB.Begin()
	if err != nil {
		return err
	}
	defer tx.Rollback()
	r, err := tx.Exec("UPDATE feeds SET title=?,folder_id=?,paused=? WHERE id=?", strings.TrimSpace(v.Title), nullableID(v.FolderID), v.Paused, v.ID)
	if err = affected(r, err); err != nil {
		return err
	}
	if v.Interval > 0 {
		if _, err = tx.Exec("INSERT INTO sync_feed_meta VALUES(?,'rss','','','',?) ON CONFLICT(feed_id) DO UPDATE SET interval=excluded.interval", v.ID, v.Interval); err != nil {
			return err
		}
	}
	return tx.Commit()
}
func (s *Store) Delete(kind string, id int64) error {
	table := "feeds"
	if kind == "folder" {
		table = "folders"
	}
	r, err := s.DB.Exec("DELETE FROM "+table+" WHERE id=?", id)
	return affected(r, err)
}

type Order struct {
	Kind     string `json:"kind"`
	ID       int64  `json:"id"`
	FolderID int64  `json:"folderId"`
}

func (s *Store) Reorder(items []Order) error {
	if len(items) > 10000 {
		return errors.New("並び順の件数が多すぎます")
	}
	tx, err := s.DB.Begin()
	if err != nil {
		return err
	}
	defer tx.Rollback()
	seen := map[string]bool{}
	for i, v := range items {
		k := fmt.Sprintf("%s:%d", v.Kind, v.ID)
		if seen[k] {
			return errors.New("並び順が重複しています")
		}
		seen[k] = true
		var r sql.Result
		if v.Kind == "folder" {
			r, err = tx.Exec("UPDATE folders SET position=? WHERE id=?", i, v.ID)
		} else if v.Kind == "feed" {
			r, err = tx.Exec("UPDATE feeds SET position=?,folder_id=? WHERE id=?", i, nullableID(v.FolderID), v.ID)
		} else {
			return errors.New("並び順の種類が不正です")
		}
		if err = affected(r, err); err != nil {
			return err
		}
	}
	return tx.Commit()
}

type Filter struct {
	FeedID   int64   `json:"feedId"`
	FolderID int64   `json:"folderId"`
	CaseID   int64   `json:"caseId"`
	FeedIDs  []int64 `json:"feedIds"`
	Mode     string  `json:"mode"`
	Query    string  `json:"query"`
	Any      string  `json:"any"`
	Exclude  string  `json:"exclude"`
	Target   string  `json:"target"`
	From     string  `json:"from"`
	To       string  `json:"to"`
	Sort     string  `json:"sort"`
	Offset   int     `json:"offset"`
}

func where(f Filter) (string, []any, error) {
	clauses := []string{"1=1"}
	args := []any{}
	add := func(q string, v any) { clauses = append(clauses, q); args = append(args, v) }
	if f.FeedID > 0 {
		add("a.feed_id=?", f.FeedID)
	}
	if f.FolderID > 0 {
		add("f.folder_id=?", f.FolderID)
	}
	if f.CaseID > 0 {
		add("EXISTS(SELECT 1 FROM case_articles ca WHERE ca.article_id=a.id AND ca.case_id=?)", f.CaseID)
	}
	if len(f.FeedIDs) > 1000 {
		return "", nil, errors.New("情報源が多すぎます")
	}
	if len(f.FeedIDs) > 0 {
		ps := []string{}
		for _, id := range f.FeedIDs {
			ps = append(ps, "?")
			args = append(args, id)
		}
		clauses = append(clauses, "a.feed_id IN ("+strings.Join(ps, ",")+")")
	}
	switch f.Mode {
	case "unread":
		clauses = append(clauses, "a.is_read=0")
	case "starred":
		clauses = append(clauses, "a.starred=1")
	case "history":
		clauses = append(clauses, "a.viewed<>''")
	case "", "all":
	default:
		return "", nil, errors.New("表示条件が不正です")
	}
	target := "(a.title||char(10)||a.content)"
	if f.Target == "title" {
		target = "a.title"
	}
	if f.Target == "content" {
		target = "a.content"
	}
	if f.Query != "" {
		add("instr(lower("+target+"),lower(?))>0", f.Query)
	}
	anyClauses := []string{}
	for _, term := range strings.Split(f.Any, ",") {
		if term = strings.TrimSpace(term); term != "" {
			anyClauses = append(anyClauses, "instr(lower("+target+"),lower(?))>0")
			args = append(args, term)
		}
	}
	if len(anyClauses) > 0 {
		clauses = append(clauses, "("+strings.Join(anyClauses, " OR ")+")")
	}
	for _, term := range strings.Split(f.Exclude, ",") {
		if term = strings.TrimSpace(term); term != "" {
			add("instr(lower("+target+"),lower(?))=0", term)
		}
	}
	for _, v := range []struct {
		s   string
		end bool
	}{{f.From, false}, {f.To, true}} {
		if v.s != "" {
			d, err := time.Parse("2006-01-02", v.s)
			if err != nil {
				return "", nil, errors.New("日付が不正です")
			}
			if v.end {
				add("a.published<?", d.AddDate(0, 0, 1).Format(timestampFormat))
			} else {
				add("a.published>=?", d.Format(timestampFormat))
			}
		}
	}
	if f.From != "" && f.To != "" && f.From > f.To {
		return "", nil, errors.New("日付の範囲が逆です")
	}
	return strings.Join(clauses, " AND "), args, nil
}

const articleCols = "a.id,a.feed_id,f.title,a.uid,a.title,a.url,a.content,a.published,a.collected,a.is_read,a.starred,a.viewed"

func scanArticle(rows interface{ Scan(...any) error }) (Article, error) {
	var a Article
	err := rows.Scan(&a.ID, &a.FeedID, &a.FeedTitle, &a.UID, &a.Title, &a.URL, &a.Content, &a.Published, &a.Collected, &a.Read, &a.Starred, &a.Viewed)
	return a, err
}
func (s *Store) Articles(f Filter) (map[string]any, error) {
	w, args, err := where(f)
	if err != nil {
		return nil, err
	}
	var total int
	if err = s.DB.QueryRow("SELECT count(*) FROM articles a JOIN feeds f ON f.id=a.feed_id WHERE "+w, args...).Scan(&total); err != nil {
		return nil, err
	}
	order := "a.published DESC,a.id DESC"
	if f.Sort == "oldest" {
		order = "a.published ASC,a.id ASC"
	}
	if f.Sort == "history" {
		order = "a.viewed DESC,a.id DESC"
	}
	if f.Offset < 0 {
		return nil, errors.New("offsetが不正です")
	}
	args = append(args, 60, f.Offset)
	rows, err := s.DB.Query("SELECT "+articleCols+" FROM articles a JOIN feeds f ON f.id=a.feed_id WHERE "+w+" ORDER BY "+order+" LIMIT ? OFFSET ?", args...)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := []Article{}
	for rows.Next() {
		a, e := scanArticle(rows)
		if e != nil {
			return nil, e
		}
		out = append(out, a)
	}
	return map[string]any{"items": out, "total": total, "hasMore": f.Offset+len(out) < total}, rows.Err()
}
func (s *Store) Article(id int64, visit bool) (Article, error) {
	if visit {
		if _, err := s.DB.Exec("UPDATE articles SET is_read=1,viewed=? WHERE id=?", now(), id); err != nil {
			return Article{}, err
		}
	}
	return scanArticle(s.DB.QueryRow("SELECT "+articleCols+" FROM articles a JOIN feeds f ON f.id=a.feed_id WHERE a.id=?", id))
}

type StateChange struct {
	IDs     []int64 `json:"ids"`
	Filter  *Filter `json:"filter"`
	Read    *bool   `json:"read"`
	Starred *bool   `json:"starred"`
}

func (s *Store) ChangeState(v StateChange) (int64, error) {
	if v.Read == nil && v.Starred == nil {
		return 0, errors.New("変更内容がありません")
	}
	sets := []string{}
	args := []any{}
	if v.Read != nil {
		sets = append(sets, "is_read=?")
		args = append(args, *v.Read)
	}
	if v.Starred != nil {
		sets = append(sets, "starred=?")
		args = append(args, *v.Starred)
	}
	var clause string
	if v.Filter != nil {
		w, vals, err := where(*v.Filter)
		if err != nil {
			return 0, err
		}
		clause = "id IN (SELECT a.id FROM articles a JOIN feeds f ON f.id=a.feed_id WHERE " + w + ")"
		args = append(args, vals...)
	} else {
		if len(v.IDs) == 0 || len(v.IDs) > 100 {
			return 0, errors.New("記事を1〜100件選択してください")
		}
		ps := []string{}
		for _, id := range v.IDs {
			ps = append(ps, "?")
			args = append(args, id)
		}
		clause = "id IN (" + strings.Join(ps, ",") + ")"
	}
	r, err := s.DB.Exec("UPDATE articles SET "+strings.Join(sets, ",")+" WHERE "+clause, args...)
	if err != nil {
		return 0, err
	}
	return r.RowsAffected()
}
func (s *Store) Unread() (int, error) {
	var n int
	err := s.DB.QueryRow("SELECT count(*) FROM articles WHERE is_read=0").Scan(&n)
	return n, err
}
func (s *Store) Ping(ctx context.Context) error { return s.DB.PingContext(ctx) }
