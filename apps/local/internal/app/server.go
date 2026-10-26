package app

import (
	"context"
	"crypto/subtle"
	"database/sql"
	"encoding/json"
	"errors"
	"io"
	"net/http"
	"strings"
)

type Server struct {
	Store     *Store
	Collector *Collector
	Token     string
}

func (s *Server) Handler() http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json; charset=utf-8")
		w.Header().Set("Cache-Control", "no-store")
		w.Header().Set("X-Content-Type-Options", "nosniff")
		if r.Method != "POST" {
			writeError(w, 405, errors.New("POSTのみ利用できます"))
			return
		}
		if r.Header.Get("Origin") != "" || subtle.ConstantTimeCompare([]byte(r.Header.Get("Authorization")), []byte("Bearer "+s.Token)) != 1 {
			writeError(w, 401, errors.New("認証できません"))
			return
		}
		if r.URL.Path != "/rpc" {
			writeError(w, 404, errors.New("見つかりません"))
			return
		}
		if !strings.HasPrefix(r.Header.Get("Content-Type"), "application/json") {
			writeError(w, 415, errors.New("JSONで送信してください"))
			return
		}
		r.Body = http.MaxBytesReader(w, r.Body, 70*1024*1024)
		defer r.Body.Close()
		b, err := io.ReadAll(r.Body)
		if err != nil {
			writeError(w, 413, err)
			return
		}
		var req struct {
			Op   string          `json:"op"`
			Data json.RawMessage `json:"data"`
		}
		if err = decodeStrict(b, &req); err != nil {
			writeError(w, 400, err)
			return
		}
		ctx, cancel := context.WithTimeout(r.Context(), 3*60*1000000000)
		defer cancel()
		value, err := s.Call(ctx, req.Op, req.Data)
		if err != nil {
			status := 400
			if errors.Is(err, ErrConflict) {
				status = 409
			}
			if errors.Is(err, sql.ErrNoRows) {
				status = 404
			}
			writeError(w, status, err)
			return
		}
		_ = json.NewEncoder(w).Encode(map[string]any{"data": value})
	})
}
func writeError(w http.ResponseWriter, code int, err error) {
	w.WriteHeader(code)
	_ = json.NewEncoder(w).Encode(map[string]string{"error": err.Error()})
}
func input[T any](b json.RawMessage) (T, error) {
	var v T
	if len(b) == 0 || string(b) == "null" {
		b = []byte("{}")
	}
	err := decodeStrict(b, &v)
	return v, err
}
func (s *Server) Call(ctx context.Context, op string, data json.RawMessage) (any, error) {
	if strings.HasPrefix(op, "sync.") {
		return s.syncCall(ctx, op, data)
	}
	if strings.HasPrefix(op, "social.") || strings.HasPrefix(op, "ai.") {
		return s.socialAICall(ctx, op, data)
	}
	switch op {
	case "bootstrap":
		f, e := s.Store.Folders()
		if e != nil {
			return nil, e
		}
		feeds, e := s.Store.Feeds()
		if e != nil {
			return nil, e
		}
		v, e := s.Store.Settings()
		if e != nil {
			return nil, e
		}
		n, e := s.Store.Unread()
		if e != nil {
			return nil, e
		}
		cases, e := s.Store.Cases()
		return map[string]any{"folders": f, "feeds": feeds, "settings": v, "unread": n, "cases": cases}, e
	case "articles":
		v, e := input[Filter](data)
		if e != nil {
			return nil, e
		}
		return s.Store.Articles(v)
	case "article":
		v, e := input[struct {
			ID    int64 `json:"id"`
			Visit bool  `json:"visit"`
		}](data)
		if e != nil {
			return nil, e
		}
		return s.Store.Article(v.ID, v.Visit)
	case "state":
		v, e := input[StateChange](data)
		if e != nil {
			return nil, e
		}
		return s.Store.ChangeState(v)
	case "folder.save":
		v, e := input[Folder](data)
		if e != nil {
			return nil, e
		}
		return s.Store.SaveFolder(v)
	case "feed.save":
		v, e := input[Feed](data)
		if e != nil {
			return nil, e
		}
		return nil, s.Store.SaveFeed(v)
	case "source.delete":
		v, e := input[struct {
			Kind string `json:"kind"`
			ID   int64  `json:"id"`
		}](data)
		if e != nil {
			return nil, e
		}
		if v.Kind != "folder" && v.Kind != "feed" {
			return nil, errors.New("種類が不正です")
		}
		return nil, s.Store.Delete(v.Kind, v.ID)
	case "sources.order":
		v, e := input[struct {
			Items []Order `json:"items"`
		}](data)
		if e != nil {
			return nil, e
		}
		return nil, s.Store.Reorder(v.Items)
	case "feed.preview":
		v, e := input[struct {
			URL string `json:"url"`
		}](data)
		if e != nil {
			return nil, e
		}
		return s.Collector.Preview(ctx, v.URL)
	case "feed.subscribe":
		v, e := input[struct {
			URL      string `json:"url"`
			Title    string `json:"title"`
			FolderID int64  `json:"folderId"`
		}](data)
		if e != nil {
			return nil, e
		}
		return s.Collector.Subscribe(ctx, v.URL, v.Title, v.FolderID)
	case "feeds.refresh":
		v, e := input[struct {
			ID int64 `json:"id"`
		}](data)
		if e != nil {
			return nil, e
		}
		rss, e := s.Collector.Refresh(ctx, v.ID)
		if e != nil {
			return nil, e
		}
		social, e := s.Collector.RefreshSocial(ctx, v.ID, v.ID > 0)
		if e != nil {
			return nil, e
		}
		rss["updated"] = rss["updated"].(int) + social["updated"].(int)
		rss["errors"] = append(rss["errors"].([]string), social["errors"].([]string)...)
		return rss, nil
	case "opml.preview":
		v, e := input[struct {
			Text string `json:"text"`
		}](data)
		if e != nil {
			return nil, e
		}
		return s.Store.PreviewOPML(v.Text)
	case "opml.import":
		v, e := input[struct {
			Text string `json:"text"`
		}](data)
		if e != nil {
			return nil, e
		}
		return s.Store.ImportOPML(v.Text)
	case "opml.export":
		return s.Store.ExportOPML()
	case "case.save":
		v, e := input[Case](data)
		if e != nil {
			return nil, e
		}
		return s.Store.SaveCase(v)
	case "case.revisions":
		v, e := input[struct {
			ID int64 `json:"id"`
		}](data)
		if e != nil {
			return nil, e
		}
		return s.Store.Revisions(v.ID)
	case "case.link", "case.unlink":
		v, e := input[Link](data)
		if e != nil {
			return nil, e
		}
		return nil, s.Store.Link(v, op == "case.unlink")
	case "article.links":
		v, e := input[struct {
			ID int64 `json:"id"`
		}](data)
		if e != nil {
			return nil, e
		}
		return s.Store.ArticleLinks(v.ID)
	case "evidence.capture":
		v, e := input[Link](data)
		if e != nil {
			return nil, e
		}
		return s.Store.Capture(v)
	case "case.evidence":
		v, e := input[struct {
			ID int64 `json:"id"`
		}](data)
		if e != nil {
			return nil, e
		}
		return s.Store.Evidence(v.ID)
	case "case.report":
		v, e := input[struct {
			ID int64 `json:"id"`
		}](data)
		if e != nil {
			return nil, e
		}
		return s.Store.Report(v.ID)
	case "settings.save":
		v, e := input[Settings](data)
		if e != nil {
			return nil, e
		}
		return nil, s.Store.SaveSettings(v)
	case "settings.export":
		return s.Store.ExportSettings()
	case "settings.import":
		v, e := input[SettingsExport](data)
		if e != nil {
			return nil, e
		}
		return nil, s.Store.ImportSettings(v)
	case "backup.export":
		return s.Store.Backup()
	case "backup.restore":
		v, e := input[struct {
			Text string `json:"text"`
		}](data)
		if e != nil {
			return nil, e
		}
		s.Collector.mu.Lock()
		defer s.Collector.mu.Unlock()
		return s.Store.Restore([]byte(v.Text))
	default:
		return nil, errors.New("未対応の操作です")
	}
}
