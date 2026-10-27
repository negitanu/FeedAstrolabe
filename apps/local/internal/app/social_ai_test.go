package app

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"sync/atomic"
	"testing"
	"time"
)

func socialFixture(t *testing.T, s *Store, provider, kind, target string) int64 {
	t.Helper()
	origin := ""
	if provider == "mastodon" {
		origin = "https://mastodon.example"
	}
	id, e := s.SaveSocial(SocialSource{Provider: provider, Kind: kind, Target: target, Origin: origin, Interval: 15, WindowHours: 24, Title: "Fixture SNS"})
	if e != nil {
		t.Fatal(e)
	}
	return id
}
func mastodonRows(id string, score int) string {
	return jsonString([]any{map[string]any{"id": id, "visibility": "public", "content": "<p>Safe public evidence</p><script>bad()</script>", "url": "https://mastodon.example/@a/" + id, "created_at": time.Now().UTC().Add(-time.Minute).Format(timestampFormat), "favourites_count": score, "reblogs_count": 2, "replies_count": 1, "tags": []any{map[string]any{"name": "AI"}}}})
}
func mockJSON(fn func(*http.Request) (int, string, http.Header)) *http.Client {
	return &http.Client{Transport: roundTrip(func(r *http.Request) (*http.Response, error) {
		status, body, headers := fn(r)
		if headers == nil {
			headers = make(http.Header)
		}
		return &http.Response{StatusCode: status, Header: headers, Body: io.NopCloser(strings.NewReader(body)), Request: r}, nil
	})}
}
func configure(t *testing.T, s *Store, p string) AIConfig {
	t.Helper()
	c, e := s.AIConfig(p)
	if e != nil {
		t.Fatal(e)
	}
	c.Enabled = true
	c.Model = "openai/test-model"
	if p == "openrouter" {
		t.Setenv("OPENROUTER_API_KEY", strings.Repeat("t", 32))
	}
	if p == "orcarouter" {
		t.Setenv("ORCAROUTER_API_KEY", strings.Repeat("o", 32))
	}
	if p == "ollama-local" {
		c.Model = "fixture:latest"
		c.Digest = strings.Repeat("a", 64)
	}
	if p == "ollama-cloud" {
		c.Model = "fixture-cloud"
		c.RateDate = time.Now().UTC().Format("2006-01-02")
		path := filepath.Join(t.TempDir(), "ollama-token")
		if e = os.WriteFile(path, []byte(strings.Repeat("c", 32)), 0600); e != nil {
			t.Fatal(e)
		}
		t.Setenv("FEEDASTROLABE_OLLAMA_TOKEN_FILE", path)
	}
	if e = s.SaveAIConfig(c); e != nil {
		t.Fatal(e)
	}
	c, e = s.AIConfig(p)
	if e != nil {
		t.Fatal(e)
	}
	g, e := s.AIGlobal()
	if e != nil {
		t.Fatal(e)
	}
	if p == "openrouter" || p == "orcarouter" {
		g.Active = p
	}
	if e = s.SaveAIGlobal(g); e != nil {
		t.Fatal(e)
	}
	return c
}
func collectedFixture(t *testing.T, s *Store) (int64, *Collector) {
	t.Helper()
	id := socialFixture(t, s, "mastodon", "tag", "AI")
	c := NewCollector(s)
	c.client = mockJSON(func(r *http.Request) (int, string, http.Header) { return 200, mastodonRows("123", 5), nil })
	r, e := c.RefreshSocial(context.Background(), id, true)
	if e != nil || r["updated"] != 1 {
		t.Fatal(r, e)
	}
	return id, c
}
func TestSocialAtomicFailureRateLimitAndRanking(t *testing.T) {
	s := testStore(t)
	id := socialFixture(t, s, "mastodon", "tag", "AI,Go")
	var secondFails bool
	var calls int
	c := NewCollector(s)
	c.client = mockJSON(func(r *http.Request) (int, string, http.Header) {
		calls++
		if secondFails && strings.Contains(r.URL.Path, "go") {
			return 500, `{"error":"should never persist upstream body"}`, nil
		}
		return 200, mastodonRows("123", 5), nil
	})
	r, e := c.RefreshSocial(context.Background(), id, true)
	if e != nil || r["updated"] != 1 || calls != 2 {
		t.Fatal(r, e, calls)
	}
	runs, e := s.SocialRuns(id)
	if e != nil || runs[0].Snapshot.SampleCount != 1 || runs[0].Snapshot.Posts[0].Score != 10 || runs[0].Snapshot.Tags[0].Tag != "ai" {
		t.Fatal(runs, e)
	}
	a, e := s.Article(1, true)
	if e != nil || a.Content != "Safe public evidence" {
		t.Fatal(a, e)
	}
	secondFails = true
	r, e = c.RefreshSocial(context.Background(), id, true)
	if e != nil || len(r["errors"].([]string)) != 1 {
		t.Fatal(r, e)
	}
	runs, _ = s.SocialRuns(id)
	if len(runs) != 1 {
		t.Fatal("partial run saved")
	}
	a, _ = s.Article(1, false)
	if !a.Read {
		t.Fatal("read state lost")
	}
	c.client = mockJSON(func(*http.Request) (int, string, http.Header) {
		return 429, "{}", http.Header{"Retry-After": []string{"1800"}}
	})
	if _, e = c.RefreshSocial(context.Background(), id, true); e != nil {
		t.Fatal(e)
	}
	other := socialFixture(t, s, "mastodon", "tag", "security")
	called := false
	c.client = mockJSON(func(*http.Request) (int, string, http.Header) { called = true; return 200, "[]", nil })
	r, e = c.RefreshSocial(context.Background(), other, true)
	if e != nil || called || len(r["errors"].([]string)) == 0 {
		t.Fatal("shared rate wait bypass", r, e)
	}
}
func TestBlueskyAndMastodonAccounts(t *testing.T) {
	s := testStore(t)
	id := socialFixture(t, s, "bluesky", "search", "Go lang:ja")
	c := NewCollector(s)
	calls := 0
	c.client = mockJSON(func(r *http.Request) (int, string, http.Header) {
		calls++
		if r.URL.Host != "api.bsky.app" || r.URL.Query().Get("limit") != "100" {
			t.Fatal(r.URL)
		}
		post := map[string]any{"uri": "at://did:plc:abc/app.bsky.feed.post/one", "author": map[string]any{"did": "did:plc:abc"}, "record": map[string]any{"$type": "app.bsky.feed.post", "text": "Go public post", "createdAt": time.Now().UTC().Add(-time.Minute).Format(timestampFormat), "tags": []string{"Go"}}, "likeCount": 1, "repostCount": 3, "replyCount": 2}
		return 200, jsonString(map[string]any{"posts": []any{post}}), nil
	})
	r, e := c.RefreshSocial(context.Background(), id, true)
	if e != nil || calls != 2 || r["updated"] != 1 {
		t.Fatal(r, e)
	}
	runs, _ := s.SocialRuns(id)
	if runs[0].Snapshot.SampleCount != 1 || runs[0].Snapshot.Posts[0].Score != 9 {
		t.Fatal(runs)
	}
	opml, _ := s.ExportOPML()
	if strings.Contains(opml, "social:") {
		t.Fatal("SNS internal URL exported")
	}
	account := socialFixture(t, s, "mastodon", "account", "alice")
	c.client = mockJSON(func(r *http.Request) (int, string, http.Header) {
		if strings.HasSuffix(r.URL.Path, "lookup") {
			return 200, `{"id":"456"}`, nil
		}
		if r.URL.Path != "/api/v1/accounts/456/statuses" {
			t.Fatal(r.URL)
		}
		return 200, mastodonRows("987", 1), nil
	})
	r, e = c.RefreshSocial(context.Background(), account, true)
	if e != nil || r["updated"] != 1 {
		t.Fatal(r, e)
	}
}
func TestSocialValidationPauseHistoryAndAutoAI(t *testing.T) {
	s := testStore(t)
	for _, v := range []SocialSource{{Provider: "mastodon", Kind: "tag", Target: "a,b,c,d", Origin: "https://mastodon.example", Interval: 15, WindowHours: 24}, {Provider: "mastodon", Kind: "account", Target: "alice@elsewhere", Origin: "https://mastodon.example", Interval: 15, WindowHours: 24}, {Provider: "bluesky", Kind: "search", Target: "x", Origin: "https://evil.example", Interval: 15, WindowHours: 24}} {
		if _, e := s.SaveSocial(v); e == nil {
			t.Fatal(v)
		}
	}
	id, c := collectedFixture(t, s)
	configure(t, s, "openrouter")
	sources, _ := s.SocialSources()
	sources[0].AIEnabled = true
	if _, e := s.SaveSocial(sources[0]); e != nil {
		t.Fatal(e)
	}
	for i := 0; i < 31; i++ {
		if _, e := c.RefreshSocial(context.Background(), id, true); e != nil {
			t.Fatal(e)
		}
	}
	runs, _ := s.SocialRuns(id)
	if len(runs) != 30 {
		t.Fatal(len(runs))
	}
	jobs, _ := s.AIJobs("topics", id)
	if len(jobs) == 0 {
		t.Fatal("no automatic job")
	}
	feeds, _ := s.Feeds()
	feeds[0].Paused = true
	if e := s.SaveFeed(feeds[0]); e != nil {
		t.Fatal(e)
	}
	r, e := c.RefreshSocial(context.Background(), id, false)
	if e != nil || r["updated"] != 0 {
		t.Fatal(r, e)
	}
	if _, e = c.RefreshSocial(context.Background(), id, true); e != nil {
		t.Fatal(e)
	}
	after, _ := s.AIJobs("topics", id)
	if len(after) != len(jobs) {
		t.Fatal("paused source auto generated")
	}
}
func topicResponse(id int64, cost string) string {
	return jsonString(map[string]any{"id": "test-request", "model": "openai/test-model", "choices": []any{map[string]any{"finish_reason": "stop", "message": map[string]any{"role": "assistant", "content": jsonString(map[string]any{"topics": []any{AITopic{Title: "Test", Summary: "Public summary", Importance: 70, Reason: "Evidence", Uncertainty: "Not independently verified", ArticleIDs: []int64{id}}}})}}}, "usage": map[string]any{"prompt_tokens": 100, "completion_tokens": 100, "cost": json.RawMessage(cost)}})
}
func TestRouterProviderIsolationBudgetAndCitations(t *testing.T) {
	s := testStore(t)
	id, _ := collectedFixture(t, s)
	configure(t, s, "openrouter")
	jobID, e := s.QueueTopics(id, 0)
	if e != nil {
		t.Fatal(e)
	}
	again, e := s.QueueTopics(id, 0)
	if e != nil || again != jobID {
		t.Fatal(again, e)
	}
	configure(t, s, "orcarouter")
	var count atomic.Int32
	w := NewAIWorker(s, mockJSON(func(r *http.Request) (int, string, http.Header) {
		count.Add(1)
		if r.URL.Host != "openrouter.ai" || r.Header.Get("Authorization") != "Bearer "+strings.Repeat("t", 32) {
			t.Fatal("wrong provider credential")
		}
		body, _ := io.ReadAll(r.Body)
		var wire map[string]json.RawMessage
		json.Unmarshal(body, &wire)
		if len(wire["provider"]) == 0 {
			t.Fatal("OpenRouter privacy routing missing")
		}
		return 200, topicResponse(1, "0.001"), nil
	}))
	if ok, e := w.ProcessOne(context.Background()); e != nil || !ok {
		t.Fatal(ok, e)
	}
	jobs, _ := s.AIJobs("topics", id)
	if jobs[0].State != "succeeded" || jobs[0].Provider != "openrouter" || jobs[0].Actual == nil || *jobs[0].Actual != 1000 {
		t.Fatal(jobs)
	}
	if ok, e := w.ProcessOne(context.Background()); e != nil || ok || count.Load() != 1 {
		t.Fatal("replayed", ok, e, count.Load())
	}
	state, e := s.AIState()
	if e != nil {
		t.Fatal(e)
	}
	if state.(map[string]any)["today"].(map[string]any)["calls"] != 1 {
		t.Fatal(state)
	}
	g, _ := s.AIGlobal()
	g.DailyCalls = 1
	s.SaveAIGlobal(g)
	if _, e = s.QueueTopics(id, 0); e == nil {
		t.Fatal("cross-provider budget reset")
	}
	if _, e = validateAIOutput(`{"topics":[{"title":"Bad","summary":"Text","importance":5,"reason":"r","uncertainty":"u","articleIds":[999]}]}`, jobs[0].Input); e == nil {
		t.Fatal("invalid citation accepted")
	}
}
func TestOrcaReceiptAndUnknownCost(t *testing.T) {
	for _, settled := range []bool{true, false} {
		t.Run(fmt.Sprint(settled), func(t *testing.T) {
			s := testStore(t)
			id, _ := collectedFixture(t, s)
			configure(t, s, "orcarouter")
			if _, e := s.QueueTopics(id, 0); e != nil {
				t.Fatal(e)
			}
			posts, gets := 0, 0
			w := NewAIWorker(s, mockJSON(func(r *http.Request) (int, string, http.Header) {
				if r.URL.Host != "api.orcarouter.ai" {
					t.Fatal(r.URL)
				}
				if r.Method == "GET" {
					gets++
					if settled {
						return 200, `{"data":{"id":"orca-123","cost_currency":"USD","total_cost":"0.002"}}`, nil
					}
					return 404, "{}", nil
				}
				posts++
				if r.Header.Get("X-OrcaRouter-Include-Cost") != "true" {
					t.Fatal("no cost request")
				}
				body, _ := io.ReadAll(r.Body)
				var wire map[string]any
				json.Unmarshal(body, &wire)
				if wire["provider"] != nil {
					t.Fatal("OpenRouter-only fields leaked")
				}
				return 200, topicResponse(1, "null"), http.Header{"X-Orca-Request-Id": []string{"orca-123"}}
			}))
			if _, e := w.ProcessOne(context.Background()); e != nil {
				t.Fatal(e)
			}
			jobs, _ := s.AIJobs("topics", id)
			if jobs[0].State != "succeeded" || posts != 1 || gets > 2 {
				t.Fatal(jobs, posts, gets)
			}
			if settled && (jobs[0].Actual == nil || *jobs[0].Actual != 2000) {
				t.Fatal(jobs)
			}
			if !settled && jobs[0].Actual != nil {
				t.Fatal("unknown cost treated as zero")
			}
		})
	}
}
func TestAIPrivacyAndSecretExclusion(t *testing.T) {
	s := testStore(t)
	id, _ := collectedFixture(t, s)
	configure(t, s, "openrouter")
	caseID, e := s.SaveCase(Case{Title: "Internal", Classification: "internal"})
	if e != nil {
		t.Fatal(e)
	}
	if _, e = s.Capture(Link{CaseID: caseID, ArticleID: 1}); e != nil {
		t.Fatal(e)
	}
	if _, e = s.QueueTopics(id, 0); e == nil {
		t.Fatal("private source sent")
	}
	cases, _ := s.Cases()
	cases[0].Classification = "public"
	s.SaveCase(cases[0])
	if _, e = s.DB.Exec("UPDATE articles SET content=? WHERE id=1", "token="+strings.Repeat("x", 32)); e != nil {
		t.Fatal(e)
	}
	// Frozen SNS content stays public, but changes to the reference policy must still block at dispatch.
	jobID, e := s.QueueTopics(id, 0)
	if e != nil {
		t.Fatal(e)
	}
	cases, _ = s.Cases()
	cases[0].Classification = "restricted"
	s.SaveCase(cases[0])
	sent := false
	w := NewAIWorker(s, mockJSON(func(*http.Request) (int, string, http.Header) { sent = true; return 200, "{}", nil }))
	if _, e = w.ProcessOne(context.Background()); e != nil {
		t.Fatal(e)
	}
	jobs, _ := s.AIJobs("topics", id)
	if sent || jobs[0].ID != jobID || jobs[0].State != "failed" {
		t.Fatal(jobs, sent)
	}
	for _, text := range []string{"Bearer " + strings.Repeat("a", 24), "api_key=" + strings.Repeat("b", 24)} {
		if !secretPattern.MatchString(text) {
			t.Fatal("secret pattern missing")
		}
	}
}
func assistantFixture(t *testing.T, s *Store) (int64, int64) {
	t.Helper()
	seedFeed(t, s, 1)
	caseID, e := s.SaveCase(Case{Title: "Research", Note: "facts", Classification: "public"})
	if e != nil {
		t.Fatal(e)
	}
	evidence, e := s.Capture(Link{CaseID: caseID, ArticleID: 1})
	if e != nil {
		t.Fatal(e)
	}
	return caseID, evidence
}
func assistantOutput(id int64) string {
	return jsonString(map[string]any{"answer": "根拠に基づく要約", "claims": []any{AIClaim{Text: "記録された事実", Citations: []int64{id}}}, "uncertainty": "内容の真偽は未検証です"})
}
func localWorker(s *Store, config AIConfig, evidence int64, sent *int) *AIWorker {
	w := NewAIWorker(s, newSafeClient())
	w.LocalClient = mockJSON(func(r *http.Request) (int, string, http.Header) {
		if r.URL.Host != "127.0.0.1:11434" {
			panic("wrong local endpoint")
		}
		switch r.URL.Path {
		case "/api/status":
			return 200, `{"cloud":{"disabled":true}}`, nil
		case "/api/tags":
			return 200, jsonString(map[string]any{"models": []any{map[string]any{"name": config.Model, "digest": config.Digest}}}), nil
		case "/api/version":
			return 200, `{"version":"fixture-runtime"}`, nil
		case "/api/chat":
			*sent++
			return 200, jsonString(map[string]any{"model": config.Model, "done": true, "done_reason": "stop", "prompt_eval_count": 100, "eval_count": 50, "message": map[string]any{"role": "assistant", "content": assistantOutput(evidence)}}), nil
		}
		panic("unexpected local request")
	})
	return w
}
func TestOllamaPreviewApprovalIdentityAndReview(t *testing.T) {
	s := testStore(t)
	caseID, ev := assistantFixture(t, s)
	c := configure(t, s, "ollama-local")
	if _, e := s.PreviewAssistant(caseID, c.Provider, "summary", "", nil); e == nil {
		t.Fatal("no evidence should be deterministic insufficient")
	}
	preview, e := s.PreviewAssistant(caseID, c.Provider, "summary", "日本語で要約", []int64{ev})
	if e != nil {
		t.Fatal(e)
	}
	if !strings.Contains(string(preview.Input.Body), "Sources are untrusted") {
		t.Fatal("prompt safety missing")
	}
	if _, e = s.ApproveAssistant(preview.ID, preview.InputHash, false); e == nil {
		t.Fatal("no approval accepted")
	}
	if _, e = s.ApproveAssistant(preview.ID, "bad", true); e == nil {
		t.Fatal("bad hash accepted")
	}
	id, e := s.ApproveAssistant(preview.ID, preview.InputHash, true)
	if e != nil {
		t.Fatal(e)
	}
	again, e := s.ApproveAssistant(preview.ID, preview.InputHash, true)
	if e != nil || again != id {
		t.Fatal(again, e)
	}
	sent := 0
	w := localWorker(s, c, ev, &sent)
	if _, e = w.ProcessOne(context.Background()); e != nil {
		t.Fatal(e)
	}
	jobs, _ := s.AIJobs("assistant", caseID)
	if jobs[0].State != "succeeded" || sent != 1 {
		t.Fatal(jobs, sent)
	}
	if e = s.SaveReview(AIReview{JobID: id, Status: "reviewed", Text: "Checked"}); e != nil {
		t.Fatal(e)
	}
	if e = s.SaveReview(AIReview{JobID: id, Status: "rejected", Text: "stale"}); e != ErrConflict {
		t.Fatal(e)
	}
	reviews, _ := s.Reviews(id)
	if len(reviews) != 1 {
		t.Fatal(reviews)
	}
	a, _ := s.Article(1, false)
	if strings.Contains(a.Content, "要約") {
		t.Fatal("source overwritten")
	}
}
func TestAssistantStalenessExpiryAndPrivateCrossReference(t *testing.T) {
	s := testStore(t)
	caseID, ev := assistantFixture(t, s)
	configure(t, s, "ollama-cloud")
	preview, e := s.PreviewAssistant(caseID, "ollama-cloud", "qa", "question", []int64{ev})
	if e != nil {
		t.Fatal(e)
	}
	cases, _ := s.Cases()
	cases[0].Classification = "internal"
	s.SaveCase(cases[0])
	if _, e = s.ApproveAssistant(preview.ID, preview.InputHash, true); e == nil {
		t.Fatal("changed policy approved")
	}
	cases, _ = s.Cases()
	cases[0].Classification = "public"
	s.SaveCase(cases[0])
	private, e := s.SaveCase(Case{Title: "Restricted", Classification: "restricted"})
	if e != nil {
		t.Fatal(e)
	}
	s.Link(Link{CaseID: private, ArticleID: 1}, false)
	if _, e = s.PreviewAssistant(caseID, "ollama-cloud", "summary", "", []int64{ev}); e == nil {
		t.Fatal("private cross reference sent")
	}
	s.Link(Link{CaseID: private, ArticleID: 1}, true)
	preview, e = s.PreviewAssistant(caseID, "ollama-cloud", "summary", "", []int64{ev})
	if e != nil {
		t.Fatal(e)
	}
	s.DB.Exec("UPDATE ai_previews SET created=? WHERE id=?", time.Now().Add(-31*time.Minute).UTC().Format(timestampFormat), preview.ID)
	if _, e = s.ApproveAssistant(preview.ID, preview.InputHash, true); e == nil {
		t.Fatal("expired preview accepted")
	}
}
func TestOllamaCloudAndLocalPreflight(t *testing.T) {
	t.Run("cloud", func(t *testing.T) {
		s := testStore(t)
		caseID, ev := assistantFixture(t, s)
		configure(t, s, "ollama-cloud")
		p, e := s.PreviewAssistant(caseID, "ollama-cloud", "translation", "日本語", []int64{ev})
		if e != nil {
			t.Fatal(e)
		}
		_, e = s.ApproveAssistant(p.ID, p.InputHash, true)
		if runtime.GOOS == "windows" {
			if e == nil || !strings.Contains(e.Error(), "ACL") {
				t.Fatalf("Windows must reject unsupported token ACL validation: %v", e)
			}
			return
		}
		if e != nil {
			t.Fatal(e)
		}
		w := NewAIWorker(s, mockJSON(func(r *http.Request) (int, string, http.Header) {
			if r.URL.String() != "https://ollama.com/api/chat" || r.Header.Get("Authorization") != "Bearer "+strings.Repeat("c", 32) {
				t.Fatal(r.URL)
			}
			return 200, jsonString(map[string]any{"model": "fixture-cloud", "done": true, "done_reason": "stop", "prompt_eval_count": 100, "eval_count": 50, "message": map[string]any{"role": "assistant", "content": assistantOutput(ev)}}), nil
		}))
		_, e = w.ProcessOne(context.Background())
		if e != nil {
			t.Fatal(e)
		}
		jobs, _ := s.AIJobs("assistant", caseID)
		if jobs[0].State != "succeeded" || jobs[0].Actual != nil {
			t.Fatal(jobs)
		}
	})
	t.Run("local mismatch", func(t *testing.T) {
		s := testStore(t)
		caseID, ev := assistantFixture(t, s)
		c := configure(t, s, "ollama-local")
		p, e := s.PreviewAssistant(caseID, c.Provider, "summary", "", []int64{ev})
		if e != nil {
			t.Fatal(e)
		}
		s.ApproveAssistant(p.ID, p.InputHash, true)
		post := false
		w := NewAIWorker(s, newSafeClient())
		w.LocalClient = mockJSON(func(r *http.Request) (int, string, http.Header) {
			if r.Method == "POST" {
				post = true
			}
			return 200, `{"cloud":{"disabled":false}}`, nil
		})
		if _, e = w.ProcessOne(context.Background()); e != nil {
			t.Fatal(e)
		}
		jobs, _ := s.AIJobs("assistant", caseID)
		if post || jobs[0].State != "failed" {
			t.Fatal(jobs, post)
		}
	})
}
func TestAIRestartRestoreAndSettingsExport(t *testing.T) {
	dir := t.TempDir()
	s, e := Open(dir)
	if e != nil {
		t.Fatal(e)
	}
	id, _ := collectedFixture(t, s)
	configure(t, s, "openrouter")
	job, e := s.QueueTopics(id, 0)
	if e != nil {
		t.Fatal(e)
	}
	s.DB.Exec("UPDATE ai_jobs SET state='running' WHERE id=?", job)
	s.Close()
	s, e = Open(dir)
	if e != nil {
		t.Fatal(e)
	}
	defer s.Close()
	jobs, _ := s.AIJobs("topics", id)
	if jobs[0].State != "failed" {
		t.Fatal(jobs)
	}
	backup, e := s.Backup()
	if e != nil {
		t.Fatal(e)
	}
	b, _ := json.Marshal(backup)
	if strings.Contains(string(b), strings.Repeat("t", 32)) {
		t.Fatal("secret in backup")
	}
	if _, e = s.Restore(b); e != nil {
		t.Fatal(e)
	}
	c, e := s.AIConfig("openrouter")
	if e != nil || c.Enabled || c.Model == "" {
		t.Fatal(c, e)
	}
	out, e := s.ExportSettings()
	if e != nil {
		t.Fatal(e)
	}
	jsonOut := jsonString(out)
	if strings.Contains(jsonOut, "Safe public") || strings.Contains(jsonOut, "references") {
		t.Fatal("data in settings")
	}
	if e = s.ImportSettings(out); e != nil {
		t.Fatal(e)
	}
	state, _ := s.AIState()
	if state.(map[string]any)["today"].(map[string]any)["calls"] != 1 {
		t.Fatal("budget reset")
	}
}
func TestMigrationAndStrictJSON(t *testing.T) {
	dir := t.TempDir()
	s, e := Open(dir)
	if e != nil {
		t.Fatal(e)
	}
	seedFeed(t, s, 1)
	s.DB.Exec("PRAGMA user_version=1")
	s.Close()
	s, e = Open(dir)
	if e != nil {
		t.Fatal(e)
	}
	defer s.Close()
	files, e := os.ReadDir(filepath.Join(dir, "migration-backups"))
	if e != nil || len(files) < 1 {
		t.Fatal(files, e)
	}
	a, e := s.Article(1, false)
	if e != nil || a.ID != 1 {
		t.Fatal(a, e)
	}
	for _, raw := range []string{`{"a":1,"a":2}`, `{"a":[{"x":1,"x":2}]}`, `{} {}`} {
		if e = uniqueJSON([]byte(raw)); e == nil {
			t.Fatal("ambiguous JSON accepted", raw)
		}
	}
	if e = uniqueJSON([]byte(`{"a":[1,2,{"b":true}]}`)); e != nil {
		t.Fatal(e)
	}
}

func TestAIFailureWaitReservationAndNoReplay(t *testing.T) {
	s := testStore(t)
	id, c := collectedFixture(t, s)
	configure(t, s, "openrouter")
	job, e := s.QueueTopics(id, 0)
	if e != nil {
		t.Fatal(e)
	}
	posts := 0
	w := NewAIWorker(s, mockJSON(func(*http.Request) (int, string, http.Header) {
		posts++
		return 429, `{"error":"do not record this body"}`, http.Header{"Retry-After": []string{"3600"}}
	}))
	if _, e = w.ProcessOne(context.Background()); e != nil {
		t.Fatal(e)
	}
	jobs, _ := s.AIJobs("topics", id)
	if jobs[0].State != "failed" || jobs[0].Reserved == 0 || strings.Contains(jobs[0].Error, "record") {
		t.Fatal(jobs)
	}
	again, e := s.QueueTopics(id, 0)
	if e != nil || again != job {
		t.Fatal(again, e)
	}
	if _, e = c.RefreshSocial(context.Background(), id, true); e != nil {
		t.Fatal(e)
	}
	if _, e = s.QueueTopics(id, 0); e != nil {
		t.Fatal(e)
	}
	if ok, e := w.ProcessOne(context.Background()); e != nil || ok || posts != 1 {
		t.Fatal("429 replay", ok, e, posts)
	}
	g, _ := s.AIGlobal()
	g.DailyCalls = 2
	s.SaveAIGlobal(g)
	configure(t, s, "orcarouter")
	if _, e = s.QueueTopics(id, 0); e == nil {
		t.Fatal("failed and waiting reservations not counted")
	}
}
func TestAIInvalidFinishUsageAndOutput(t *testing.T) {
	for _, kind := range []string{"finish", "usage", "citation", "duplicate"} {
		t.Run(kind, func(t *testing.T) {
			s := testStore(t)
			id, _ := collectedFixture(t, s)
			configure(t, s, "openrouter")
			s.QueueTopics(id, 0)
			body := topicResponse(1, "0.001")
			switch kind {
			case "finish":
				body = strings.Replace(body, `"finish_reason":"stop"`, `"finish_reason":"length"`, 1)
			case "usage":
				body = strings.Replace(body, `"completion_tokens":100`, `"completion_tokens":99999`, 1)
			case "citation":
				body = topicResponse(999, "0.001")
			case "duplicate":
				body = strings.Replace(body, `"prompt_tokens":100`, `"prompt_tokens":100,"prompt_tokens":2`, 1)
			}
			posts := 0
			w := NewAIWorker(s, mockJSON(func(*http.Request) (int, string, http.Header) { posts++; return 200, body, nil }))
			if _, e := w.ProcessOne(context.Background()); e != nil {
				t.Fatal(e)
			}
			jobs, _ := s.AIJobs("topics", id)
			if jobs[0].State != "failed" {
				t.Fatal(kind, jobs)
			}
			w.ProcessOne(context.Background())
			if posts != 1 {
				t.Fatal("generation replayed")
			}
		})
	}
}
func TestPrivatePolicyWriteCannotRaceSending(t *testing.T) {
	s := testStore(t)
	id, _ := collectedFixture(t, s)
	caseID, e := s.SaveCase(Case{Title: "Public", Classification: "public"})
	if e != nil {
		t.Fatal(e)
	}
	s.Link(Link{CaseID: caseID, ArticleID: 1}, false)
	configure(t, s, "openrouter")
	s.QueueTopics(id, 0)
	entered := make(chan struct{})
	release := make(chan struct{})
	w := NewAIWorker(s, mockJSON(func(*http.Request) (int, string, http.Header) {
		close(entered)
		<-release
		return 200, topicResponse(1, "0.001"), nil
	}))
	workerDone := make(chan error, 1)
	go func() { _, e := w.ProcessOne(context.Background()); workerDone <- e }()
	<-entered
	writeDone := make(chan error, 1)
	go func() {
		_, e := s.SaveCase(Case{ID: caseID, Title: "Private", Revision: 1, Classification: "restricted"})
		writeDone <- e
	}()
	select {
	case e := <-writeDone:
		close(release)
		t.Fatalf("classification changed during send: %v", e)
	case <-time.After(30 * time.Millisecond):
	}
	close(release)
	if e = <-workerDone; e != nil {
		t.Fatal(e)
	}
	if e = <-writeDone; e != nil {
		t.Fatal(e)
	}
}
func TestCredentialFileAndConfigBoundaries(t *testing.T) {
	s := testStore(t)
	for _, p := range aiProviders {
		c := DefaultAIConfig(p)
		c.Model = "orcarouter/auto"
		c.Enabled = true
		if e := validConfig(c); e == nil {
			t.Fatal("auto model accepted", p)
		}
	}
	t.Setenv("OPENROUTER_API_KEY", strings.Repeat("x", 4097))
	if _, e := credential("openrouter"); e == nil {
		t.Fatal("oversized key accepted")
	}
	file := filepath.Join(t.TempDir(), "token")
	os.WriteFile(file, []byte(strings.Repeat("z", 32)), 0644)
	t.Setenv("FEEDASTROLABE_OLLAMA_TOKEN_FILE", file)
	if _, e := readOllamaToken(); e == nil {
		t.Fatal("public token file accepted")
	}
	os.Chmod(file, 0600)
	link := file + "-link"
	os.Symlink(file, link)
	t.Setenv("FEEDASTROLABE_OLLAMA_TOKEN_FILE", link)
	if _, e := readOllamaToken(); e == nil {
		t.Fatal("symlink token file accepted")
	}
	_ = s
}

func TestProviderWaitDoesNotBlockOtherProvider(t *testing.T) {
	s := testStore(t)
	id, _ := collectedFixture(t, s)
	configure(t, s, "openrouter")
	s.QueueTopics(id, 0)
	configure(t, s, "orcarouter")
	s.QueueTopics(id, 0)
	s.DB.Exec("INSERT INTO service_waits VALUES(?,?)", "ai:openrouter", time.Now().UTC().Add(time.Hour).Format(timestampFormat))
	w := NewAIWorker(s, mockJSON(func(r *http.Request) (int, string, http.Header) {
		if r.URL.Host != "api.orcarouter.ai" {
			t.Fatal("waiting provider dispatched")
		}
		body := strings.Replace(topicResponse(1, "0.001"), `"cost":0.001`, `"cost_usd":0.001`, 1)
		return 200, body, http.Header{"X-Orca-Request-Id": []string{"orca-wait-test"}}
	}))
	if ok, e := w.ProcessOne(context.Background()); e != nil || !ok {
		t.Fatal(ok, e)
	}
	jobs, _ := s.AIJobs("topics", id)
	if jobs[0].Provider != "orcarouter" || jobs[0].State != "succeeded" || jobs[1].State != "queued" {
		t.Fatal(jobs)
	}
}
func TestPrivateNoteCitationBlocksExternalInput(t *testing.T) {
	s := testStore(t)
	id, _ := collectedFixture(t, s)
	public, e := s.SaveCase(Case{Title: "Public", Classification: "public"})
	if e != nil {
		t.Fatal(e)
	}
	ev, e := s.Capture(Link{CaseID: public, ArticleID: 1})
	if e != nil {
		t.Fatal(e)
	}
	_, e = s.SaveCase(Case{Title: "Private note", Classification: "internal", Note: fmt.Sprintf("引用 [E%d]", ev)})
	if e != nil {
		t.Fatal(e)
	}
	configure(t, s, "openrouter")
	if _, e = s.QueueTopics(id, 0); e == nil {
		t.Fatal("private note reference ignored")
	}
}

func TestGlobalCollectionPauseStopsAutomaticJobs(t *testing.T) {
	s := testStore(t)
	id, c := collectedFixture(t, s)
	configure(t, s, "openrouter")
	sources, _ := s.SocialSources()
	sources[0].AIEnabled = true
	if _, e := s.SaveSocial(sources[0]); e != nil {
		t.Fatal(e)
	}
	if _, e := c.RefreshSocial(context.Background(), id, true); e != nil {
		t.Fatal(e)
	}
	jobs, _ := s.AIJobs("topics", id)
	if len(jobs) != 1 || !jobs[0].Input.Automatic {
		t.Fatal(jobs)
	}
	settings, _ := s.Settings()
	settings.PauseCollection = true
	s.SaveSettings(settings)
	posts := 0
	w := NewAIWorker(s, mockJSON(func(*http.Request) (int, string, http.Header) { posts++; return 200, topicResponse(1, "0.001"), nil }))
	if _, e := w.ProcessOne(context.Background()); e != nil {
		t.Fatal(e)
	}
	jobs, _ = s.AIJobs("topics", id)
	if posts != 0 || jobs[0].State != "failed" {
		t.Fatal(jobs, posts)
	}
	if _, e := c.RefreshSocial(context.Background(), id, true); e != nil {
		t.Fatal(e)
	}
	if _, e := s.QueueTopics(id, 0); e != nil {
		t.Fatal(e)
	}
	if _, e := w.ProcessOne(context.Background()); e != nil {
		t.Fatal(e)
	}
	if posts != 1 {
		t.Fatal("explicit manual request blocked")
	}
}

func TestRestoreBetweenClaimAndSendCannotReviveJob(t *testing.T) {
	s := testStore(t)
	id, _ := collectedFixture(t, s)
	configure(t, s, "openrouter")
	s.QueueTopics(id, 0)
	backup, e := s.Backup()
	if e != nil {
		t.Fatal(e)
	}
	b, _ := json.Marshal(backup)
	sent := false
	w := NewAIWorker(s, mockJSON(func(*http.Request) (int, string, http.Header) {
		sent = true
		return 200, topicResponse(1, "0.001"), nil
	}))
	w.afterClaim = func() {
		if _, e := s.Restore(b); e != nil {
			t.Fatal(e)
		}
	}
	if _, e = w.ProcessOne(context.Background()); e != nil {
		t.Fatal(e)
	}
	jobs, _ := s.AIJobs("topics", id)
	if sent || jobs[0].State != "failed" || !strings.Contains(jobs[0].Error, "復元した未完了") {
		t.Fatal(jobs, sent)
	}
}
