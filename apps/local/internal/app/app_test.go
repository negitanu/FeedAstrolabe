package app

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net"
	"net/http"
	"net/http/httptest"
	"os"
	"strings"
	"testing"
	"time"
)

func testStore(t *testing.T) *Store {
	t.Helper()
	s, e := Open(t.TempDir())
	if e != nil {
		t.Fatal(e)
	}
	t.Cleanup(func() { s.Close() })
	return s
}
func seedFeed(t *testing.T, s *Store, n int) int64 {
	t.Helper()
	r, e := s.DB.Exec("INSERT INTO feeds(title,url,position) VALUES('Fixture','https://example.com/feed',0)")
	if e != nil {
		t.Fatal(e)
	}
	id, _ := r.LastInsertId()
	for i := 0; i < n; i++ {
		_, e = s.DB.Exec("INSERT INTO articles(feed_id,uid,title,url,content,published,collected) VALUES(?,?,?,?,?,?,?)", id, fmt.Sprint(i), fmt.Sprintf("Article %03d", i), fmt.Sprintf("https://example.com/%d", i), "A literal 100%_ string about Go\nEvidence", time.Date(2026, 10, 1, 0, 0, i, 0, time.UTC).Format(timestampFormat), now())
		if e != nil {
			t.Fatal(e)
		}
	}
	return id
}
func TestFilterAndAtomicStates(t *testing.T) {
	s := testStore(t)
	feed := seedFeed(t, s, 125)
	folder, e := s.SaveFolder(Folder{Name: "Research"})
	if e != nil {
		t.Fatal(e)
	}
	feeds, _ := s.Feeds()
	feeds[0].FolderID = folder
	if e = s.SaveFeed(feeds[0]); e != nil {
		t.Fatal(e)
	}
	result, e := s.Articles(Filter{FolderID: folder, Query: "100%_", Mode: "unread"})
	if e != nil {
		t.Fatal(e)
	}
	if result["total"] != 125 || len(result["items"].([]Article)) != 60 || result["hasMore"] != true {
		t.Fatalf("bad result: %#v", result)
	}
	v := true
	count, e := s.ChangeState(StateChange{Filter: &Filter{FeedID: feed, Query: "100%_"}, Read: &v})
	if e != nil || count != 125 {
		t.Fatalf("mark all: %d %v", count, e)
	}
	unread, _ := s.Unread()
	if unread != 0 {
		t.Fatal(unread)
	}
	_, e = s.ChangeState(StateChange{IDs: []int64{1, 2}, Starred: &v})
	if e != nil {
		t.Fatal(e)
	}
	stars, _ := s.Articles(Filter{Mode: "starred"})
	if stars["total"] != 2 {
		t.Fatal(stars)
	}
	cases := []struct {
		f    Filter
		want int
	}{{Filter{Any: "missing,Go", Exclude: "nothere"}, 125}, {Filter{Query: "100%_", Target: "title"}, 0}, {Filter{Exclude: "Go"}, 0}, {Filter{From: "2026-10-02"}, 0}, {Filter{To: "2026-10-01"}, 125}}
	for _, v := range cases {
		r, e := s.Articles(v.f)
		if e != nil || r["total"] != v.want {
			t.Fatalf("filter %#v: %v %v", v.f, r, e)
		}
	}
	if _, e = s.Articles(Filter{From: "bad"}); e == nil {
		t.Fatal("invalid date accepted")
	}
	if _, e = s.Articles(Filter{From: "2026-10-03", To: "2026-10-01"}); e == nil {
		t.Fatal("reversed dates")
	}
	a, e := s.Article(1, true)
	if e != nil || !a.Read || a.Viewed == "" {
		t.Fatalf("visit: %v %v", a, e)
	}
	r, _ := s.Articles(Filter{Mode: "history"})
	if r["total"] != 1 {
		t.Fatal(r)
	}
}
func TestReorderPauseAndRestart(t *testing.T) {
	dir := t.TempDir()
	s, e := Open(dir)
	if e != nil {
		t.Fatal(e)
	}
	feed := seedFeed(t, s, 2)
	folder, _ := s.SaveFolder(Folder{Name: "folder"})
	if e = s.Reorder([]Order{{Kind: "folder", ID: folder}, {Kind: "feed", ID: feed, FolderID: folder}}); e != nil {
		t.Fatal(e)
	}
	feeds, _ := s.Feeds()
	feeds[0].Paused = true
	if e = s.SaveFeed(feeds[0]); e != nil {
		t.Fatal(e)
	}
	if e = s.Close(); e != nil {
		t.Fatal(e)
	}
	s, e = Open(dir)
	if e != nil {
		t.Fatal(e)
	}
	defer s.Close()
	feeds, _ = s.Feeds()
	if !feeds[0].Paused || feeds[0].FolderID != folder {
		t.Fatal(feeds)
	}
	if e = s.Delete("folder", folder); e != nil {
		t.Fatal(e)
	}
	feeds, _ = s.Feeds()
	if feeds[0].FolderID != 0 {
		t.Fatal(feeds)
	}
	r, _ := s.Articles(Filter{})
	if r["total"] != 2 {
		t.Fatal(r)
	}
}
func TestResearchBackupRollback(t *testing.T) {
	s := testStore(t)
	seedFeed(t, s, 3)
	id, e := s.SaveCase(Case{Title: "Investigation", Note: "## Facts"})
	if e != nil {
		t.Fatal(e)
	}
	cases, _ := s.Cases()
	c := cases[0]
	c.Note = "## Updated"
	if _, e = s.SaveCase(c); e != nil {
		t.Fatal(e)
	}
	if _, e = s.SaveCase(c); e != ErrConflict {
		t.Fatalf("no conflict: %v", e)
	}
	evidenceID, e := s.Capture(Link{CaseID: id, ArticleID: 1})
	if e != nil {
		t.Fatal(e)
	}
	if evidenceID <= 0 {
		t.Fatal(evidenceID)
	}
	_, e = s.DB.Exec("UPDATE articles SET content='changed' WHERE id=1")
	if e != nil {
		t.Fatal(e)
	}
	evidence, e := s.Evidence(id)
	if e != nil || !strings.Contains(evidence[0].Content, "Evidence") {
		t.Fatal(evidence, e)
	}
	report, e := s.Report(id)
	if e != nil || !strings.Contains(report, "[E1]") || !strings.Contains(report, "SHA-256") {
		t.Fatal(report, e)
	}
	backup, e := s.Backup()
	if e != nil {
		t.Fatal(e)
	}
	b, _ := json.Marshal(backup)
	if _, e = s.DB.Exec("DELETE FROM feeds"); e != nil {
		t.Fatal(e)
	}
	path, e := s.Restore(b)
	if e != nil {
		t.Fatal(e)
	}
	if _, e = os.Stat(path); e != nil {
		t.Fatal(e)
	}
	articles, _ := s.Articles(Filter{})
	if articles["total"] != 3 {
		t.Fatal(articles)
	}
	revs, _ := s.Revisions(id)
	if len(revs) != 2 {
		t.Fatal(revs)
	}
	bad := strings.Replace(string(b), "feedastrolabe-local-backup", "other-format", 1)
	if _, e = s.Restore([]byte(bad)); e == nil {
		t.Fatal("unsupported backup accepted")
	}
	var corrupt Backup
	json.Unmarshal(b, &corrupt)
	corrupt.Tables[6].Rows[0][7] = "bad-hash"
	badBytes, _ := json.Marshal(corrupt)
	if _, e = s.Restore(badBytes); e == nil {
		t.Fatal("bad evidence accepted")
	}
	articles, _ = s.Articles(Filter{})
	if articles["total"] != 3 {
		t.Fatal("rollback lost data")
	}
	_, e = s.DB.Exec("DELETE FROM feeds")
	if e != nil {
		t.Fatal(e)
	}
	evidence, _ = s.Evidence(id)
	if len(evidence) != 1 {
		t.Fatal("evidence deleted with article")
	}
}
func TestOPML(t *testing.T) {
	s := testStore(t)
	raw := `<?xml version="1.0"?><opml version="2.0"><body><outline text="Tech"><outline text="One" xmlUrl="https://example.com/rss"/><outline text="Duplicate" xmlUrl="https://example.com/rss"/><outline text="Bad" xmlUrl="http://127.0.0.1/private"/></outline></body></opml>`
	items, e := s.PreviewOPML(raw)
	if e != nil || len(items) != 3 || !items[1].Duplicate || items[2].Error == "" {
		t.Fatal(items, e)
	}
	r, e := s.ImportOPML(raw)
	if e != nil || r["added"] != 1 || r["skipped"] != 2 {
		t.Fatal(r, e)
	}
	out, e := s.ExportOPML()
	if e != nil || !strings.Contains(out, "Tech") || !strings.Contains(out, "https://example.com/rss") {
		t.Fatal(out, e)
	}
	items, e = s.PreviewOPML(out)
	if e != nil || !items[0].Duplicate {
		t.Fatal(items, e)
	}
	if _, e = s.PreviewOPML(`<!DOCTYPE opml [<!ENTITY x SYSTEM "file:///etc/passwd">]><opml><body/></opml>`); e == nil {
		t.Fatal("DTD accepted")
	}
}
func TestNetworkPolicy(t *testing.T) {
	for _, raw := range []string{"http://127.0.0.1", "http://[::1]", "http://10.1.1.1", "http://169.254.169.254", "https://example.com:444/", "file:///etc/passwd", "https://user:pass@example.com"} {
		if _, e := parseURL(raw); e == nil {
			t.Fatalf("accepted %s", raw)
		}
	}
	for _, raw := range []string{"0.0.0.0", "192.168.1.1", "100.64.0.1", "::ffff:127.0.0.1", "2001:db8::1", "64:ff9b::7f00:1", "224.0.0.1"} {
		if PublicIP(net.ParseIP(raw)) {
			t.Fatalf("accepted %s", raw)
		}
	}
	for _, raw := range []string{"8.8.8.8", "1.1.1.1", "2606:4700:4700::1111"} {
		if !PublicIP(net.ParseIP(raw)) {
			t.Fatalf("rejected %s", raw)
		}
	}
}

type roundTrip func(*http.Request) (*http.Response, error)

func (f roundTrip) RoundTrip(r *http.Request) (*http.Response, error) { return f(r) }

const rssFixture = `<?xml version="1.0"?><rss version="2.0"><channel><title>Fixture</title><link>https://example.com</link><description>Test</description><item><guid>one</guid><title>First</title><link>https://example.com/one</link><description><![CDATA[<p>Safe text</p><script>alert(1)</script><img src="https://tracker.example/x">]]></description><pubDate>Mon, 26 Oct 2026 00:00:00 GMT</pubDate></item></channel></rss>`

func fixtureCollector(s *Store, body *string) *Collector {
	c := NewCollector(s)
	c.client = &http.Client{Transport: roundTrip(func(r *http.Request) (*http.Response, error) {
		return &http.Response{StatusCode: 200, Header: make(http.Header), Body: io.NopCloser(strings.NewReader(*body)), Request: r}, nil
	})}
	return c
}
func TestCollectionPreservesStateAndFailure(t *testing.T) {
	s := testStore(t)
	body := rssFixture
	c := fixtureCollector(s, &body)
	previews, e := c.Preview(context.Background(), "https://example.com/rss")
	if e != nil || len(previews) != 1 {
		t.Fatal(previews, e)
	}
	id, e := c.Subscribe(context.Background(), "https://example.com/rss", "", 0)
	if e != nil {
		t.Fatal(e)
	}
	a, e := s.Article(1, true)
	if e != nil || a.Content != "<p>Safe text</p>" {
		t.Fatal(a, e)
	}
	yes := true
	s.ChangeState(StateChange{IDs: []int64{1}, Starred: &yes})
	body = strings.Replace(body, "Safe text", "Updated", 1)
	if _, e = c.Refresh(context.Background(), id); e != nil {
		t.Fatal(e)
	}
	a, _ = s.Article(1, false)
	if !a.Read || !a.Starred || a.Content != "<p>Updated</p>" {
		t.Fatal(a)
	}
	body = "bad feed"
	r, e := c.Refresh(context.Background(), id)
	if e != nil || len(r["errors"].([]string)) != 1 {
		t.Fatal(r, e)
	}
	a, _ = s.Article(1, false)
	if a.Content != "<p>Updated</p>" {
		t.Fatal(a)
	}
	feeds, _ := s.Feeds()
	if feeds[0].LastError == "" {
		t.Fatal(feeds)
	}
	feeds[0].Paused = true
	s.SaveFeed(feeds[0])
	r, _ = c.Refresh(context.Background(), id)
	if r["updated"] != 0 || len(r["errors"].([]string)) != 0 {
		t.Fatal(r)
	}
}
func TestAtomAndLimits(t *testing.T) {
	atom := `<feed xmlns="http://www.w3.org/2005/Atom"><title>Atom</title><entry><id>a</id><title>A</title><updated>2026-10-26T00:00:00Z</updated><link href="https://example.com/a"/><content type="html">&lt;p&gt;Atom text&lt;/p&gt;</content></entry></feed>`
	f, e := parseFeed([]byte(atom))
	if e != nil {
		t.Fatal(e)
	}
	a := articlesFromFeed(f, nil)
	if len(a) != 1 || a[0].Content != "<p>Atom text</p>" {
		t.Fatal(a)
	}
	if _, e = parseFeed([]byte(`<!DOCTYPE rss><rss/>`)); e == nil {
		t.Fatal("DTD")
	}
	s := testStore(t)
	body := strings.Repeat("x", maxDownload+1)
	c := fixtureCollector(s, &body)
	if _, _, e = c.download(context.Background(), "https://example.com/rss"); e == nil {
		t.Fatal("oversize")
	}
	if got := httpLink("javascript:alert(1)", nil); got != "" {
		t.Fatal(got)
	}
}
func TestAuthenticatedAPI(t *testing.T) {
	s := testStore(t)
	api := &Server{Store: s, Collector: NewCollector(s), Token: strings.Repeat("a", 64)}
	handler := api.Handler()
	for _, v := range []struct {
		token, origin string
		want          int
	}{{"", "", 401}, {"Bearer bad", "", 401}, {"Bearer " + api.Token, "https://evil.example", 401}, {"Bearer " + api.Token, "", 200}} {
		req := httptest.NewRequest("POST", "http://127.0.0.1/rpc", strings.NewReader(`{"op":"bootstrap","data":{}}`))
		req.Header.Set("Authorization", v.token)
		req.Header.Set("Origin", v.origin)
		req.Header.Set("Content-Type", "application/json")
		w := httptest.NewRecorder()
		handler.ServeHTTP(w, req)
		if w.Code != v.want {
			t.Fatal(w.Code, w.Body.String())
		}
	}
}

func TestDiscoveryRedirectAndCompression(t *testing.T) {
	s := testStore(t)
	c := NewCollector(s)
	c.client = &http.Client{Transport: roundTrip(func(r *http.Request) (*http.Response, error) {
		body := rssFixture
		if r.URL.Path == "/" {
			body = `<!doctype html><html><head><link rel="alternate" type="application/rss+xml" href="/feed"><link rel="alternate" type="application/rss+xml" href="http://127.0.0.1/internal"></head></html>`
		}
		return &http.Response{StatusCode: 200, Header: make(http.Header), Body: io.NopCloser(strings.NewReader(body)), Request: r}, nil
	})}
	out, err := c.Preview(context.Background(), "https://example.com/")
	if err != nil || len(out) != 1 || out[0].URL != "https://example.com/feed" {
		t.Fatal(out, err)
	}
	safe := newSafeClient()
	req, _ := http.NewRequest("GET", "http://127.0.0.1/private", nil)
	if err = safe.CheckRedirect(req, []*http.Request{{}}); err == nil {
		t.Fatal("private redirect accepted")
	}
	c.client = &http.Client{Transport: roundTrip(func(r *http.Request) (*http.Response, error) {
		return &http.Response{StatusCode: 200, Header: http.Header{"Content-Encoding": []string{"gzip"}}, Body: io.NopCloser(strings.NewReader("data")), Request: r}, nil
	})}
	if _, _, err = c.download(context.Background(), "https://example.com/feed"); err == nil {
		t.Fatal("compressed response accepted")
	}
}
func TestCanonicalPublicationDates(t *testing.T) {
	s := testStore(t)
	seedFeed(t, s, 1)
	backup, err := s.Backup()
	if err != nil {
		t.Fatal(err)
	}
	backup.Tables[2].Rows[0][6] = "2026-10-26T09:00:00+09:00"
	b, _ := json.Marshal(backup)
	if _, err = s.Restore(b); err != nil {
		t.Fatal(err)
	}
	a, err := s.Article(1, false)
	if err != nil || a.Published != "2026-10-26T00:00:00.000000000Z" {
		t.Fatal(a, err)
	}
	r, err := s.Articles(Filter{From: "2026-10-26", To: "2026-10-26"})
	if err != nil || r["total"] != 1 {
		t.Fatal(r, err)
	}
	r, err = s.Articles(Filter{To: "2026-10-25"})
	if err != nil || r["total"] != 0 {
		t.Fatal(r, err)
	}
}
func TestRestoreReferentialFailureAndSafetyCopy(t *testing.T) {
	s := testStore(t)
	seedFeed(t, s, 1)
	backup, err := s.Backup()
	if err != nil {
		t.Fatal(err)
	}
	backup.Tables[2].Rows[0][1] = 999
	b, _ := json.Marshal(backup)
	if _, err = s.Restore(b); err == nil {
		t.Fatal("orphan accepted")
	}
	a, err := s.Article(1, false)
	if err != nil || a.FeedID != 1 {
		t.Fatal(a, err)
	}
	backup, _ = s.Backup()
	b, _ = json.Marshal(backup)
	if err = os.WriteFile(s.Dir+"/backups", []byte("not a directory"), 0600); err != nil {
		t.Fatal(err)
	}
	if _, err = s.Restore(b); err == nil {
		t.Fatal("restored without safety backup")
	}
	if _, err = s.Article(1, false); err != nil {
		t.Fatal(err)
	}
}

func TestExplicitTLSCompatibility(t *testing.T) {
	s := testStore(t)
	defaultConfig := NewCollector(s).client.Transport.(*http.Transport).TLSClientConfig
	compatConfig := NewCollectorWithTLS12(s, true).client.Transport.(*http.Transport).TLSClientConfig
	if defaultConfig.MaxVersion != 0 || compatConfig.MaxVersion != 0x0303 || compatConfig.InsecureSkipVerify {
		t.Fatal("TLS defaults or certificate verification changed")
	}
}
