package app

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"golang.org/x/text/unicode/norm"
	"net/url"
	"regexp"
	"sort"
	"strings"
	"time"
	"unicode"
)

func jsonValid(b []byte) bool { return json.Valid(b) }
func jsonString(v any) string { b, _ := json.Marshal(v); return string(b) }

type SocialSource struct {
	AIError     string `json:"aiError"`
	FeedID      int64  `json:"feedId"`
	Provider    string `json:"provider"`
	Kind        string `json:"kind"`
	Target      string `json:"target"`
	Origin      string `json:"origin"`
	Interval    int    `json:"interval"`
	WindowHours int    `json:"windowHours"`
	NextAt      string `json:"nextAt"`
	Failures    int    `json:"failures"`
	AIEnabled   bool   `json:"aiEnabled"`
	Criteria    string `json:"criteria"`
	Revision    int    `json:"revision"`
	Title       string `json:"title,omitempty"`
	FolderID    int64  `json:"folderId,omitempty"`
}
type SocialPost struct {
	ArticleID int64    `json:"articleId"`
	UID       string   `json:"uid"`
	Title     string   `json:"title"`
	URL       string   `json:"url"`
	Content   string   `json:"content"`
	Published string   `json:"published"`
	Likes     int64    `json:"likes"`
	Reposts   int64    `json:"reposts"`
	Replies   int64    `json:"replies"`
	Score     int64    `json:"score"`
	Tags      []string `json:"tags"`
}
type SocialTag struct {
	Tag   string `json:"tag"`
	Posts int    `json:"posts"`
}
type SocialSnapshot struct {
	Posts       []SocialPost `json:"posts"`
	Tags        []SocialTag  `json:"tags"`
	SampleCount int          `json:"sampleCount"`
}
type SocialRun struct {
	ID          int64          `json:"id"`
	FeedID      int64          `json:"feedId"`
	Collected   string         `json:"collected"`
	WindowStart string         `json:"windowStart"`
	Snapshot    SocialSnapshot `json:"snapshot"`
}

var numericID = regexp.MustCompile(`^[0-9]{1,40}$`)
var bskyURI = regexp.MustCompile(`^at://(did:[a-z]+:[A-Za-z0-9:._%-]{1,256})/app\.bsky\.feed\.post/([A-Za-z0-9._~-]{1,128})$`)

func tagValue(raw string) string {
	v := strings.ToLower(strings.TrimPrefix(norm.NFKC.String(strings.TrimSpace(raw)), "#"))
	if len([]rune(v)) < 1 || len([]rune(v)) > 64 {
		return ""
	}
	for _, r := range v {
		if !unicode.IsLetter(r) && !unicode.IsDigit(r) && r != '_' {
			return ""
		}
	}
	return v
}
func validateSocial(v *SocialSource) error {
	if v.Interval < 15 || v.Interval > 1440 || v.WindowHours < 1 || v.WindowHours > 168 || len([]rune(v.Criteria)) > 2000 {
		return errors.New("SNSの間隔・期間・評価観点が範囲外です")
	}
	v.Target = strings.TrimSpace(v.Target)
	if len([]rune(v.Target)) == 0 || len([]rune(v.Target)) > 200 {
		return errors.New("検索条件は1〜200文字で入力してください")
	}
	for _, r := range v.Target {
		if unicode.IsControl(r) {
			return errors.New("検索条件に制御文字は使えません")
		}
	}
	if v.Provider == "bluesky" {
		if v.Kind != "search" || v.Origin != "" && v.Origin != "https://api.bsky.app" {
			return errors.New("Blueskyは固定サーバーのキーワード検索です")
		}
		v.Origin = "https://api.bsky.app"
	} else if v.Provider == "mastodon" {
		u, e := parseURL(v.Origin)
		if e != nil || u.Scheme != "https" || u.RawQuery != "" || (u.Path != "" && u.Path != "/") {
			return errors.New("Mastodonの公開HTTPSサーバーを指定してください")
		}
		v.Origin = "https://" + u.Host
		if v.Kind == "tag" {
			seen := map[string]bool{}
			tags := []string{}
			parts := strings.Split(strings.ReplaceAll(v.Target, "、", ","), ",")
			if len(parts) > 3 {
				return errors.New("タグは1〜3個です")
			}
			for _, v := range parts {
				tag := tagValue(v)
				if tag == "" {
					return errors.New("タグは文字・数字・_のみ利用できます")
				}
				if !seen[tag] {
					tags = append(tags, tag)
					seen[tag] = true
				}
			}
			sort.Strings(tags)
			v.Target = strings.Join(tags, ",")
		} else if v.Kind == "account" {
			if !regexp.MustCompile(`^[A-Za-z0-9_][A-Za-z0-9_.-]{0,63}$`).MatchString(v.Target) {
				return errors.New("サーバー内のローカルアカウント名を指定してください")
			}
		} else {
			return errors.New("Mastodonの種類が不正です")
		}
	} else {
		return errors.New("SNSはMastodonまたはBlueskyを指定してください")
	}
	return nil
}

const socialCols = "feed_id,provider,kind,target,origin,interval,window_hours,next_at,failures,ai_enabled,criteria,revision,ai_error"

func (s *Store) SocialSources() ([]SocialSource, error) {
	rows, e := s.DB.Query("SELECT " + socialCols + " FROM social_sources ORDER BY feed_id")
	if e != nil {
		return nil, e
	}
	defer rows.Close()
	out := []SocialSource{}
	for rows.Next() {
		var v SocialSource
		if e = rows.Scan(&v.FeedID, &v.Provider, &v.Kind, &v.Target, &v.Origin, &v.Interval, &v.WindowHours, &v.NextAt, &v.Failures, &v.AIEnabled, &v.Criteria, &v.Revision, &v.AIError); e != nil {
			return nil, e
		}
		out = append(out, v)
	}
	return out, rows.Err()
}
func (s *Store) SaveSocial(v SocialSource) (int64, error) {
	if e := validateSocial(&v); e != nil {
		return 0, e
	}
	if v.FeedID != 0 {
		r, e := s.DB.Exec("UPDATE social_sources SET interval=?,window_hours=?,ai_enabled=?,criteria=?,revision=revision+1 WHERE feed_id=? AND revision=? AND provider=? AND kind=? AND target=? AND origin=?", v.Interval, v.WindowHours, v.AIEnabled, v.Criteria, v.FeedID, v.Revision, v.Provider, v.Kind, v.Target, v.Origin)
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
		return v.FeedID, nil
	}
	if e := validName(v.Title); e != nil {
		return 0, e
	}
	tx, e := s.DB.Begin()
	if e != nil {
		return 0, e
	}
	defer tx.Rollback()
	h := sha256.Sum256([]byte(v.Provider + "\n" + v.Origin + "\n" + v.Target))
	identity := "social-topic:" + hex.EncodeToString(h[:])
	if v.Kind == "account" {
		identity = v.Origin + "/@" + strings.ToLower(v.Target)
	}
	r, e := tx.Exec("INSERT INTO feeds(folder_id,title,url,site_url,position) VALUES(?,?,?,?,(SELECT COALESCE(MAX(position),0)+1 FROM feeds))", nullableID(v.FolderID), v.Title, identity, v.Origin)
	if e != nil {
		return 0, errors.New("登録済み条件またはフォルダー指定が不正です")
	}
	id, e := r.LastInsertId()
	if e != nil {
		return 0, e
	}
	_, e = tx.Exec("INSERT INTO social_sources(feed_id,provider,kind,target,origin,interval,window_hours,ai_enabled,criteria) VALUES(?,?,?,?,?,?,?,?,?)", id, v.Provider, v.Kind, v.Target, v.Origin, v.Interval, v.WindowHours, v.AIEnabled, v.Criteria)
	if e != nil {
		return 0, e
	}
	return id, tx.Commit()
}
func (s *Store) SocialRuns(feed int64) ([]SocialRun, error) {
	rows, e := s.DB.Query("SELECT id,feed_id,collected,window_start,posts FROM social_runs WHERE feed_id=? ORDER BY id DESC LIMIT 30", feed)
	if e != nil {
		return nil, e
	}
	defer rows.Close()
	out := []SocialRun{}
	for rows.Next() {
		var r SocialRun
		var data string
		if e = rows.Scan(&r.ID, &r.FeedID, &r.Collected, &r.WindowStart, &data); e != nil {
			return nil, e
		}
		if e = json.Unmarshal([]byte(data), &r.Snapshot); e != nil {
			return nil, e
		}
		out = append(out, r)
	}
	return out, rows.Err()
}
func counter(v map[string]json.RawMessage, name string) (int64, error) {
	if len(v[name]) == 0 {
		return 0, nil
	}
	var n int64
	if e := json.Unmarshal(v[name], &n); e != nil || string(v[name]) == "null" || n < 0 || n > 2147483647 {
		return 0, errors.New("SNS反応数が不正です")
	}
	return n, nil
}
func str(v map[string]json.RawMessage, k string) string {
	var s string
	_ = json.Unmarshal(v[k], &s)
	return s
}
func decodePosts(data []byte, provider string) ([]map[string]json.RawMessage, error) {
	var posts []map[string]json.RawMessage
	if provider == "bluesky" {
		var env struct {
			Posts []map[string]json.RawMessage `json:"posts"`
		}
		if e := json.Unmarshal(data, &env); e != nil || env.Posts == nil || len(env.Posts) > 100 {
			return nil, errors.New("Bluesky応答が不正です")
		}
		return env.Posts, nil
	}
	if e := json.Unmarshal(data, &posts); e != nil || posts == nil || len(posts) > 40 {
		return nil, errors.New("Mastodon応答が不正です")
	}
	return posts, nil
}
func normalizePost(row map[string]json.RawMessage, provider string, start, end time.Time) (SocialPost, bool, error) {
	var p SocialPost
	var date string
	p.Tags = []string{}
	var keys []string
	if provider == "mastodon" {
		if str(row, "visibility") != "public" && str(row, "visibility") != "unlisted" {
			return p, false, nil
		}
		if v := row["reblog"]; len(v) > 0 && string(v) != "null" {
			return p, false, nil
		}
		id := str(row, "id")
		if !numericID.MatchString(id) {
			return p, false, errors.New("Mastodon投稿IDが不正です")
		}
		p.UID = "mastodon:" + id
		p.Content = textHTML(str(row, "content"))
		p.Title = firstRunes(p.Content, 160)
		p.URL = httpLink(str(row, "url"), nil)
		date = str(row, "created_at")
		keys = []string{"favourites_count", "reblogs_count", "replies_count"}
		var tags []struct {
			Name string `json:"name"`
		}
		if raw := row["tags"]; len(raw) > 0 {
			if e := json.Unmarshal(raw, &tags); e != nil || len(tags) > 100 {
				return p, false, errors.New("SNSタグが不正です")
			}
		}
		for _, t := range tags {
			p.Tags = append(p.Tags, t.Name)
		}
	} else {
		uri := str(row, "uri")
		m := bskyURI.FindStringSubmatch(uri)
		var author map[string]json.RawMessage
		var record map[string]json.RawMessage
		if len(m) != 3 || json.Unmarshal(row["author"], &author) != nil || json.Unmarshal(row["record"], &record) != nil || str(author, "did") != m[1] || str(record, "$type") != "app.bsky.feed.post" {
			return p, false, errors.New("Bluesky投稿IDが不正です")
		}
		p.UID = "bluesky:" + uri
		p.Content = str(record, "text")
		p.Title = firstRunes(p.Content, 160)
		p.URL = "https://bsky.app/profile/" + url.PathEscape(m[1]) + "/post/" + url.PathEscape(m[2])
		date = str(record, "createdAt")
		keys = []string{"likeCount", "repostCount", "replyCount"}
		if raw := record["tags"]; len(raw) > 0 {
			if e := json.Unmarshal(raw, &p.Tags); e != nil || len(p.Tags) > 100 {
				return p, false, errors.New("SNSタグが不正です")
			}
		}
		var facets []struct {
			Features []struct {
				Type string `json:"$type"`
				Tag  string `json:"tag"`
			} `json:"features"`
		}
		if raw := record["facets"]; len(raw) > 0 {
			if e := json.Unmarshal(raw, &facets); e != nil || len(facets) > 1000 {
				return p, false, errors.New("SNSタグが不正です")
			}
		}
		for _, f := range facets {
			if len(f.Features) > 100 {
				return p, false, errors.New("SNSタグが多すぎます")
			}
			for _, v := range f.Features {
				if v.Type == "app.bsky.richtext.facet#tag" {
					p.Tags = append(p.Tags, v.Tag)
				}
			}
		}
	}
	d, e := time.Parse(time.RFC3339Nano, date)
	if e != nil || d.Before(start) || d.After(end) {
		return p, false, nil
	}
	if len(p.Content) > 100000 || p.URL == "" {
		return p, false, errors.New("SNS投稿本文・URLが不正です")
	}
	metrics := []*int64{&p.Likes, &p.Reposts, &p.Replies}
	for i, key := range keys {
		n, e := counter(row, key)
		if e != nil {
			return p, false, e
		}
		*metrics[i] = n
	}
	p.Score = p.Likes + 2*p.Reposts + p.Replies
	p.Published = d.UTC().Format(timestampFormat)
	seen := map[string]bool{}
	tags := []string{}
	for _, raw := range p.Tags {
		if tag := tagValue(raw); tag != "" && !seen[tag] {
			tags = append(tags, tag)
			seen[tag] = true
		}
	}
	p.Tags = tags
	if p.Title == "" {
		p.Title = "SNS投稿"
	}
	return p, true, nil
}
func firstRunes(v string, n int) string {
	r := []rune(v)
	if len(r) > n {
		r = r[:n]
	}
	return string(r)
}
func (c *Collector) socialRows(ctx context.Context, v SocialSource, start, end time.Time) ([]map[string]json.RawMessage, error) {
	paths := []string{}
	if v.Provider == "bluesky" {
		for _, order := range []string{"top", "latest"} {
			q := url.Values{"q": {v.Target}, "sort": {order}, "limit": {"100"}, "since": {start.Format(time.RFC3339)}, "until": {end.Format(time.RFC3339)}}
			paths = append(paths, v.Origin+"/xrpc/app.bsky.feed.searchPosts?"+q.Encode())
		}
	} else if v.Kind == "tag" {
		for _, tag := range strings.Split(v.Target, ",") {
			paths = append(paths, v.Origin+"/api/v1/timelines/tag/"+url.PathEscape(tag)+"?limit=40")
		}
	} else {
		b, _, e := requestJSON(ctx, c.client, "GET", v.Origin+"/api/v1/accounts/lookup?acct="+url.QueryEscape(v.Target), nil, "", maxDownload, false)
		if e != nil {
			return nil, e
		}
		var account struct {
			ID string `json:"id"`
		}
		if json.Unmarshal(b, &account) != nil || !numericID.MatchString(account.ID) {
			return nil, errors.New("Mastodonアカウントが不正です")
		}
		var count int
		if e = c.Store.DB.QueryRow("SELECT count(*) FROM social_runs WHERE feed_id=?", v.FeedID).Scan(&count); e != nil {
			return nil, e
		}
		out := []map[string]json.RawMessage{}
		maxPages := 3
		if count == 0 {
			maxPages = 1
		}
		maxID := ""
		for page := 0; page < maxPages; page++ {
			path := v.Origin + "/api/v1/accounts/" + account.ID + "/statuses?limit=40&exclude_reblogs=true"
			if maxID != "" {
				path += "&max_id=" + maxID
			}
			b, _, e := requestJSON(ctx, c.client, "GET", path, nil, "", maxDownload, false)
			if e != nil {
				return nil, e
			}
			posts, e := decodePosts(b, v.Provider)
			if e != nil {
				return nil, e
			}
			out = append(out, posts...)
			if len(posts) < 40 {
				break
			}
			maxID = str(posts[len(posts)-1], "id")
			if !numericID.MatchString(maxID) {
				return nil, errors.New("SNSページ境界が不正です")
			}
		}
		return out, nil
	}
	out := []map[string]json.RawMessage{}
	for _, path := range paths {
		b, _, e := requestJSON(ctx, c.client, "GET", path, nil, "", maxDownload, false)
		if e != nil {
			return nil, e
		}
		posts, e := decodePosts(b, v.Provider)
		if e != nil {
			return nil, e
		}
		out = append(out, posts...)
	}
	return out, nil
}
func (c *Collector) RefreshSocial(ctx context.Context, id int64, manual bool) (map[string]any, error) {
	if !c.mu.TryLock() {
		return nil, errors.New("更新は実行中です")
	}
	defer c.mu.Unlock()
	sources, e := c.Store.SocialSources()
	if e != nil {
		return nil, e
	}
	feeds, e := c.Store.Feeds()
	if e != nil {
		return nil, e
	}
	byID := map[int64]Feed{}
	for _, f := range feeds {
		byID[f.ID] = f
	}
	updated := 0
	failures := []string{}
	for _, v := range sources {
		f, ok := byID[v.FeedID]
		if !ok || (id > 0 && id != v.FeedID) || (!manual && (f.Paused || v.NextAt > now())) {
			continue
		}
		service := v.Origin
		if e = c.Store.checkWait(service); e != nil {
			if manual {
				failures = append(failures, e.Error())
			}
			continue
		}
		end := time.Now().UTC()
		start := end.Add(-time.Duration(v.WindowHours) * time.Hour)
		rows, e := c.socialRows(ctx, v, start, end)
		posts := map[string]SocialPost{}
		if e == nil {
			for _, r := range rows {
				p, keep, err := normalizePost(r, v.Provider, start, end)
				if err != nil {
					e = err
					break
				}
				if keep {
					posts[p.UID] = p
				}
			}
		}
		if e != nil {
			if err := c.Store.setWait(service, e); err != nil {
				return nil, err
			}
			backoff := 15 * (1 << min(v.Failures, 6))
			next := end.Add(time.Duration(backoff) * time.Minute).Format(timestampFormat)
			tx, err := c.Store.DB.Begin()
			if err != nil {
				return nil, err
			}
			_, err = tx.Exec("UPDATE feeds SET last_error=? WHERE id=?", e.Error(), v.FeedID)
			if err == nil {
				_, err = tx.Exec("UPDATE social_sources SET failures=failures+1,next_at=? WHERE feed_id=?", next, v.FeedID)
			}
			if err != nil {
				tx.Rollback()
				return nil, err
			}
			if err = tx.Commit(); err != nil {
				return nil, err
			}
			failures = append(failures, f.Title+": "+e.Error())
			continue
		}
		list := []SocialPost{}
		tagCounts := map[string]int{}
		for _, p := range posts {
			list = append(list, p)
			for _, tag := range p.Tags {
				tagCounts[tag]++
			}
		}
		sort.Slice(list, func(i, j int) bool {
			a, b := list[i], list[j]
			if a.Score != b.Score {
				return a.Score > b.Score
			}
			if a.Published != b.Published {
				return a.Published > b.Published
			}
			return a.UID > b.UID
		})
		tags := []SocialTag{}
		for tag, n := range tagCounts {
			tags = append(tags, SocialTag{tag, n})
		}
		sort.Slice(tags, func(i, j int) bool {
			if tags[i].Posts != tags[j].Posts {
				return tags[i].Posts > tags[j].Posts
			}
			return tags[i].Tag < tags[j].Tag
		})
		if len(tags) > 12 {
			tags = tags[:12]
		}
		tx, err := c.Store.DB.Begin()
		if err != nil {
			return nil, err
		}
		for i, p := range list {
			_, err = tx.Exec("INSERT INTO articles(feed_id,uid,title,url,content,published,collected) VALUES(?,?,?,?,?,?,?) ON CONFLICT(feed_id,uid) DO UPDATE SET title=excluded.title,url=excluded.url,content=excluded.content", v.FeedID, p.UID, p.Title, p.URL, p.Content, p.Published, now())
			if err != nil {
				break
			}
			err = tx.QueryRow("SELECT id FROM articles WHERE feed_id=? AND uid=?", v.FeedID, p.UID).Scan(&list[i].ArticleID)
			if err != nil {
				break
			}
		}
		runID := int64(0)
		if err == nil {
			snap := SocialSnapshot{Posts: list[:min(40, len(list))], Tags: tags, SampleCount: len(list)}
			r, e := tx.Exec("INSERT INTO social_runs(feed_id,collected,window_start,posts) VALUES(?,?,?,?)", v.FeedID, end.Format(timestampFormat), start.Format(timestampFormat), jsonString(snap))
			err = e
			if e == nil {
				runID, err = r.LastInsertId()
			}
		}
		if err == nil {
			_, err = tx.Exec("UPDATE social_sources SET next_at=?,failures=0 WHERE feed_id=?", end.Add(time.Duration(v.Interval)*time.Minute).Format(timestampFormat), v.FeedID)
		}
		if err == nil {
			_, err = tx.Exec("UPDATE feeds SET last_fetched=?,last_error='' WHERE id=?", now(), v.FeedID)
		}
		if err == nil {
			_, err = tx.Exec("DELETE FROM social_runs WHERE feed_id=? AND id NOT IN(SELECT id FROM social_runs WHERE feed_id=? ORDER BY id DESC LIMIT 30)", v.FeedID, v.FeedID)
		}
		if err != nil {
			tx.Rollback()
			return nil, err
		}
		if err = tx.Commit(); err != nil {
			return nil, err
		}
		updated++
		settings, settingsErr := c.Store.Settings()
		if settingsErr != nil {
			return nil, settingsErr
		}
		if v.AIEnabled && !f.Paused && !settings.PauseCollection {
			_, queueErr := c.Store.queueTopics(v.FeedID, runID, true)
			errorText := ""
			if queueErr != nil {
				errorText = queueErr.Error()
				failures = append(failures, f.Title+": AI予約: "+errorText)
			}
			if _, e = c.Store.DB.Exec("UPDATE social_sources SET ai_error=? WHERE feed_id=?", errorText, v.FeedID); e != nil {
				return nil, e
			}
		}
	}
	return map[string]any{"updated": updated, "errors": failures}, nil
}
func (s *Store) SocialDetail(id int64) (any, error) {
	sources, e := s.SocialSources()
	if e != nil {
		return nil, e
	}
	var source *SocialSource
	for _, v := range sources {
		if v.FeedID == id {
			copy := v
			source = &copy
			break
		}
	}
	if source == nil {
		return nil, fmt.Errorf("SNS情報源が見つかりません")
	}
	runs, e := s.SocialRuns(id)
	if e != nil {
		return nil, e
	}
	jobs, e := s.AIJobs("topics", id)
	return map[string]any{"source": source, "runs": runs, "jobs": jobs}, e
}
