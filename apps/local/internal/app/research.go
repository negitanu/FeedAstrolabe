package app

import (
	"crypto/sha256"
	"database/sql"
	"encoding/hex"
	"errors"
	"fmt"
	"strings"
)

var ErrConflict = errors.New("別の更新が保存されています。再読み込みして確認してください")

func (s *Store) Cases() ([]Case, error) {
	rows, err := s.DB.Query("SELECT id,title,note,revision,archived,updated,COALESCE((SELECT classification FROM case_policies WHERE case_id=cases.id),'public') FROM cases ORDER BY archived,updated DESC,id DESC")
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := []Case{}
	for rows.Next() {
		var c Case
		if err = rows.Scan(&c.ID, &c.Title, &c.Note, &c.Revision, &c.Archived, &c.Updated, &c.Classification); err != nil {
			return nil, err
		}
		out = append(out, c)
	}
	return out, rows.Err()
}
func (s *Store) SaveCase(c Case) (int64, error) {
	if err := validName(c.Title); err != nil {
		return 0, err
	}
	if len(c.Note) > 2*1024*1024 {
		return 0, errors.New("メモが大きすぎます")
	}
	tx, err := s.DB.Begin()
	if err != nil {
		return 0, err
	}
	defer tx.Rollback()
	if c.Classification == "" {
		c.Classification = "public"
		if c.ID > 0 {
			p, e := queryPolicy(tx, c.ID)
			if e != nil {
				return 0, e
			}
			c.Classification = p
		}
	}
	if c.Classification != "public" && c.Classification != "internal" && c.Classification != "restricted" {
		return 0, errors.New("公開区分が不正です")
	}
	stamp := now()
	if c.ID == 0 {
		r, e := tx.Exec("INSERT INTO cases(title,note,revision,archived,updated) VALUES(?,?,1,?,?)", strings.TrimSpace(c.Title), c.Note, c.Archived, stamp)
		if e != nil {
			return 0, e
		}
		c.ID, e = r.LastInsertId()
		if e != nil {
			return 0, e
		}
		c.Revision = 1
	} else {
		r, e := tx.Exec("UPDATE cases SET title=?,note=?,revision=revision+1,archived=?,updated=? WHERE id=? AND revision=?", strings.TrimSpace(c.Title), c.Note, c.Archived, stamp, c.ID, c.Revision)
		if e != nil {
			return 0, e
		}
		n, e := r.RowsAffected()
		if e != nil {
			return 0, e
		}
		if n == 0 {
			return 0, ErrConflict
		}
		c.Revision++
	}
	if _, err = tx.Exec("INSERT INTO note_revisions(case_id,revision,note,created) VALUES(?,?,?,?)", c.ID, c.Revision, c.Note, stamp); err != nil {
		return 0, err
	}
	if _, err = tx.Exec("INSERT INTO case_policies(case_id,classification) VALUES(?,?) ON CONFLICT(case_id) DO UPDATE SET classification=excluded.classification", c.ID, c.Classification); err != nil {
		return 0, err
	}
	return c.ID, tx.Commit()
}
func (s *Store) Revisions(id int64) ([]Revision, error) {
	rows, err := s.DB.Query("SELECT case_id,revision,note,created FROM note_revisions WHERE case_id=? ORDER BY revision DESC", id)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := []Revision{}
	for rows.Next() {
		var v Revision
		if err = rows.Scan(&v.CaseID, &v.Revision, &v.Note, &v.Created); err != nil {
			return nil, err
		}
		out = append(out, v)
	}
	return out, rows.Err()
}
func (s *Store) Link(l Link, remove bool) error {
	if remove {
		_, err := s.DB.Exec("DELETE FROM case_articles WHERE case_id=? AND article_id=?", l.CaseID, l.ArticleID)
		return err
	}
	_, err := s.DB.Exec("INSERT OR IGNORE INTO case_articles(case_id,article_id) VALUES(?,?)", l.CaseID, l.ArticleID)
	return err
}
func (s *Store) ArticleLinks(id int64) ([]int64, error) {
	rows, err := s.DB.Query("SELECT case_id FROM case_articles WHERE article_id=? ORDER BY case_id", id)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := []int64{}
	for rows.Next() {
		var v int64
		if err = rows.Scan(&v); err != nil {
			return nil, err
		}
		out = append(out, v)
	}
	return out, rows.Err()
}
func hashEvidence(title, url, content string) string {
	h := sha256.Sum256([]byte(title + "\n" + url + "\n" + content))
	return hex.EncodeToString(h[:])
}
func (s *Store) Capture(l Link) (int64, error) {
	a, err := s.Article(l.ArticleID, false)
	if err != nil {
		return 0, err
	}
	tx, err := s.DB.Begin()
	if err != nil {
		return 0, err
	}
	defer tx.Rollback()
	if _, err = tx.Exec("INSERT OR IGNORE INTO case_articles(case_id,article_id) VALUES(?,?)", l.CaseID, l.ArticleID); err != nil {
		return 0, err
	}
	r, err := tx.Exec("INSERT INTO evidence(case_id,article_id,title,url,content,captured,hash) VALUES(?,?,?,?,?,?,?)", l.CaseID, l.ArticleID, a.Title, a.URL, a.Content, now(), hashEvidence(a.Title, a.URL, a.Content))
	if err != nil {
		return 0, err
	}
	id, err := r.LastInsertId()
	if err != nil {
		return 0, err
	}
	return id, tx.Commit()
}
func (s *Store) Evidence(id int64) ([]Evidence, error) {
	rows, err := s.DB.Query("SELECT id,case_id,COALESCE(article_id,0),title,url,content,captured,hash FROM evidence WHERE (?=0 OR case_id=?) ORDER BY id DESC", id, id)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := []Evidence{}
	for rows.Next() {
		var v Evidence
		if err = rows.Scan(&v.ID, &v.CaseID, &v.ArticleID, &v.Title, &v.URL, &v.Content, &v.Captured, &v.Hash); err != nil {
			return nil, err
		}
		out = append(out, v)
	}
	return out, rows.Err()
}
func markdownText(s string) string {
	r := strings.NewReplacer("\\", "\\\\", "[", "\\[", "]", "\\]", "<", "&lt;", ">", "&gt;", "#", "\\#", "*", "\\*", "_", "\\_")
	return r.Replace(s)
}
func (s *Store) Report(id int64) (string, error) {
	var c Case
	if err := s.DB.QueryRow("SELECT id,title,note,revision,archived,updated FROM cases WHERE id=?", id).Scan(&c.ID, &c.Title, &c.Note, &c.Revision, &c.Archived, &c.Updated); err != nil {
		return "", err
	}
	evidence, err := s.Evidence(id)
	if err != nil {
		return "", err
	}
	var b strings.Builder
	fmt.Fprintf(&b, "# %s\n\n更新: %s / メモ版: %d\n\n## 調査メモ\n\n%s\n\n## 根拠\n", markdownText(c.Title), c.Updated, c.Revision, c.Note)
	for _, e := range evidence {
		fmt.Fprintf(&b, "\n### [E%d] %s\n\n出典: <%s>\n\n保存: %s\n\nSHA-256: `%s`\n\n", e.ID, markdownText(e.Title), strings.ReplaceAll(e.URL, ">", "%3E"), e.Captured, e.Hash)
		for _, line := range strings.Split(e.Content, "\n") {
			fmt.Fprintf(&b, "> %s\n", markdownText(line))
		}
	}
	return b.String(), nil
}
func isNotFound(err error) bool { return errors.Is(err, sql.ErrNoRows) }
