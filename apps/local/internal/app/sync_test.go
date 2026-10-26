package app

import (
	"context"
	"encoding/json"
	"fmt"
	"net/url"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

func syncEv(n int, clock int64, kind string, key []string, value any) SyncEvent {
	return SyncEvent{ID: fmt.Sprintf("%032x", n), Clock: clock, Kind: kind, Key: key, Value: json.RawMessage(syncJSON(value))}
}
func remoteFixture() []SyncEvent {
	return []SyncEvent{
		syncEv(1, 10, "feed", []string{"https://example.org/rss"}, syncFeed{Title: "共有", Folder: "調査", Enabled: 1, Source: "rss", Interval: 900}),
		syncEv(2, 11, "article", []string{"https://example.org/rss", "a"}, syncArticle{Title: "本文", URL: "https://example.org/a", Content: "fixture", Published: "2026-10-26T00:00:00Z", Collected: "2026-10-26T00:00:00Z"}),
		syncEv(3, 12, "read", []string{"https://example.org/rss", "a"}, map[string]int{"value": 1}),
	}
}
func acceptFixture(t *testing.T, s *Store, events []SyncEvent) {
	t.Helper()
	p, e := s.PrepareSync()
	if e != nil {
		t.Fatal(e)
	}
	if e = s.AcceptSync(p, SyncResponse{Version: 1, Hub: fmt.Sprintf("%032x", 999), Cursor: p.Request.Cursor + int64(len(events)), Events: events}); e != nil {
		t.Fatal(e)
	}
}
func TestSyncMergeReplayConflictAndTombstone(t *testing.T) {
	s := testStore(t)
	if e := s.SaveSyncConnection("https://reader.example", true); e != nil {
		t.Fatal(e)
	}
	events := remoteFixture()
	acceptFixture(t, s, []SyncEvent{events[2], events[1], events[0]})
	articles, e := s.Articles(Filter{})
	if e != nil {
		t.Fatal(e)
	}
	a := articles["items"].([]Article)[0]
	if !a.Read || a.Starred {
		t.Fatal(a)
	}
	star := true
	if _, e = s.ChangeState(StateChange{IDs: []int64{a.ID}, Starred: &star}); e != nil {
		t.Fatal(e)
	}
	acceptFixture(t, s, []SyncEvent{syncEv(4, 13, "read", events[1].Key, map[string]int{"value": 0})})
	a, e = s.Article(a.ID, false)
	if e != nil || a.Read || !a.Starred {
		t.Fatal(a, e)
	}
	var before, after int
	_ = s.DB.QueryRow("SELECT count(*) FROM sync_events").Scan(&before)
	acceptFixture(t, s, events)
	_ = s.DB.QueryRow("SELECT count(*) FROM sync_events").Scan(&after)
	if before != after {
		t.Fatal("replay created duplicates")
	}
	acceptFixture(t, s, []SyncEvent{syncEv(5, 20, "delete", events[0].Key, map[string]any{}), syncEv(6, 19, "feed", events[0].Key, syncFeed{Title: "stale", Enabled: 1, Source: "rss", Interval: 900})})
	var n int
	_ = s.DB.QueryRow("SELECT count(*) FROM feeds").Scan(&n)
	if n != 0 {
		t.Fatal("tombstone lost")
	}
}
func TestSyncAtomicValidationAndSettingChanges(t *testing.T) {
	s := testStore(t)
	_ = s.SaveSyncConnection("https://reader.example", true)
	p, _ := s.PrepareSync()
	events := remoteFixture()
	events[2].Value = json.RawMessage(`{"value":true}`)
	if e := s.AcceptSync(p, SyncResponse{Version: 1, Hub: fmt.Sprintf("%032x", 9), Cursor: 3, Events: events}); e == nil {
		t.Fatal("invalid state accepted")
	}
	var n int
	_ = s.DB.QueryRow("SELECT count(*) FROM feeds").Scan(&n)
	if n != 0 {
		t.Fatal("partial commit")
	}
	_ = s.SaveSyncConnection("https://another.example", true)
	if e := s.AcceptSync(p, SyncResponse{Version: 1, Hub: fmt.Sprintf("%032x", 9), Cursor: 0, Events: []SyncEvent{}}); e == nil {
		t.Fatal("changed destination accepted")
	}
	for _, u := range []string{"http://example.com", "https://user:secret@example.com", "https://example.com/path", "file:///tmp/x", "https://example.com/?token=x"} {
		if e := s.SaveSyncConnection(u, true); e == nil {
			t.Fatal("invalid origin", u)
		}
	}
}
func TestSyncJournalRestartAndMigrationBackup(t *testing.T) {
	dir := t.TempDir()
	s, e := Open(dir)
	if e != nil {
		t.Fatal(e)
	}
	seedFeed(t, s, 1)
	_ = s.SaveSyncConnection("https://reader.example", true)
	before, _ := s.PrepareSync()
	if len(before.Request.Events) != 3 {
		t.Fatal(before)
	}
	s.Close()
	s, e = Open(dir)
	if e != nil {
		t.Fatal(e)
	}
	defer s.Close()
	after, _ := s.PrepareSync()
	if syncJSON(before) != syncJSON(after) {
		t.Fatal("restart changed pending events")
	}
	// Read-only migration backup is present when enabling sync on a legacy library.
	other := testStore(t)
	seedFeed(t, other, 1)
	rows, e := other.DB.Query("SELECT name FROM sqlite_master WHERE type='trigger' AND name LIKE 'sync_%'")
	if e != nil {
		t.Fatal(e)
	}
	names := []string{}
	for rows.Next() {
		var name string
		_ = rows.Scan(&name)
		names = append(names, name)
	}
	rows.Close()
	for _, name := range names {
		_, _ = other.DB.Exec("DROP TRIGGER " + name)
	}
	for _, table := range []string{"sync_meta", "sync_events", "sync_versions", "sync_connection", "sync_feed_meta"} {
		if _, e = other.DB.Exec("DROP TABLE " + table); e != nil {
			t.Fatal(e)
		}
	}
	if e = other.migrateSync(); e != nil {
		t.Fatal(e)
	}
	entries, e := os.ReadDir(filepath.Join(other.Dir, "migration-backups"))
	if e != nil || len(entries) < 1 {
		t.Fatal(entries, e)
	}
}

func TestSyncCollectionIntervalBackupAndSettings(t *testing.T) {
	s := testStore(t)
	body := rssFixture
	c := fixtureCollector(s, &body)
	id, e := c.Subscribe(context.Background(), "https://example.com/rss", "Fixture", 0)
	if e != nil {
		t.Fatal(e)
	}
	feeds, e := s.Feeds()
	if e != nil {
		t.Fatal(e)
	}
	feeds[0].Interval = 3600
	if e = s.SaveFeed(feeds[0]); e != nil {
		t.Fatal(e)
	}
	result, e := c.refresh(context.Background(), id, false)
	if e != nil || result["updated"] != 0 {
		t.Fatal(result, e)
	}
	if _, e = s.DB.Exec("UPDATE feeds SET last_fetched=? WHERE id=?", time.Now().UTC().Add(-2*time.Hour).Format(timestampFormat), id); e != nil {
		t.Fatal(e)
	}
	result, e = c.refresh(context.Background(), id, false)
	if e != nil || result["updated"] != 1 {
		t.Fatal(result, e)
	}
	_ = s.SaveSyncConnection("https://reader.example", true)
	exported, e := s.ExportSettings()
	if e != nil {
		t.Fatal(e)
	}
	if exported.Version != 3 || exported.Sync.URL != "https://reader.example" {
		t.Fatal(exported)
	}
	if e = s.ImportSettings(exported); e != nil {
		t.Fatal(e)
	}
	connection, _ := s.SyncConnection()
	if connection.Enabled || connection.URL != "https://reader.example" {
		t.Fatal(connection)
	}
	backup, e := s.Backup()
	if e != nil {
		t.Fatal(e)
	}
	b, _ := json.Marshal(backup)
	if _, e = s.Restore(b); e != nil {
		t.Fatal(e)
	}
	feeds, e = s.Feeds()
	if e != nil || feeds[0].Interval != 3600 {
		t.Fatal(feeds, e)
	}
	connection, _ = s.SyncConnection()
	if connection.Enabled || connection.URL != "" {
		t.Fatal("restore did not disconnect", connection)
	}
}
func TestRichReaderKeepsFormattingAndBlocksActiveContent(t *testing.T) {
	raw := `<p onclick="evil()">Safe <strong>formatting</strong><a href="javascript:evil()">bad</a><a href="/source">source</a><img src="https://track.example/x"><script>evil()</script><svg onload="evil()"></svg></p>`
	base, _ := url.Parse("https://example.com/path")
	safe := SanitizeRichHTML(raw, base)
	if !strings.Contains(safe, "<strong>formatting</strong>") || !strings.Contains(safe, `href="https://example.com/source"`) {
		t.Fatal(safe)
	}
	for _, danger := range []string{"onclick", "javascript:", "<img", "<script", "<svg", "evil()"} {
		if strings.Contains(safe, danger) {
			t.Fatal(safe)
		}
	}
}

func TestSyncPauseSurvivesRename(t *testing.T) {
	s := testStore(t)
	_ = s.SaveSyncConnection("https://reader.example", true)
	events := remoteFixture()
	renamed := syncFeed{Title: "renamed", Enabled: 1, Source: "rss", Interval: 900}
	acceptFixture(t, s, []SyncEvent{events[0], syncEv(9, 20, "enabled", events[0].Key, map[string]int{"value": 0}), syncEv(10, 99, "feed", events[0].Key, renamed)})
	feeds, e := s.Feeds()
	if e != nil || !feeds[0].Paused || feeds[0].Title != "renamed" {
		t.Fatal(feeds, e)
	}
	acceptFixture(t, s, []SyncEvent{syncEv(11, 100, "enabled", events[0].Key, map[string]int{"value": 1})})
	feeds, e = s.Feeds()
	if e != nil || feeds[0].Paused {
		t.Fatal(feeds, e)
	}
}

func TestLegacySocialBackupGetsWebCompatibleIdentity(t *testing.T) {
	s := testStore(t)
	id, _ := collectedFixture(t, s)
	backup, e := s.Backup()
	if e != nil {
		t.Fatal(e)
	}
	backup.Version = 2
	backup.Tables = backup.Tables[:preSyncTables]
	for i := range backup.Tables {
		if backup.Tables[i].Name == "feeds" {
			backup.Tables[i].Rows[0][3] = "social:" + strings.Repeat("a", 64)
		}
	}
	raw, _ := json.Marshal(backup)
	if _, e = s.Restore(raw); e != nil {
		t.Fatal(e)
	}
	feeds, e := s.Feeds()
	if e != nil || len(feeds) != 1 || feeds[0].ID != id || !strings.HasPrefix(feeds[0].URL, "social-topic:") {
		t.Fatal(feeds, e)
	}
	a, e := s.Article(1, false)
	if e != nil || a.UID != "mastodon:123" {
		t.Fatal(a, e)
	}
}

func TestDeleteAndRenameOrderConverges(t *testing.T) {
	for _, deleteFirst := range []bool{true, false} {
		t.Run(fmt.Sprint(deleteFirst), func(t *testing.T) {
			s := testStore(t)
			_ = s.SaveSyncConnection("https://reader.example", true)
			events := remoteFixture()
			acceptFixture(t, s, events)
			deletion := syncEv(4, 20, "delete", events[0].Key, map[string]any{})
			rename := syncEv(5, 99, "feed", events[0].Key, syncFeed{Title: "newer", Enabled: 1, Source: "rss", Interval: 900})
			order := []SyncEvent{rename, deletion}
			if deleteFirst {
				order = []SyncEvent{deletion, rename}
			}
			for _, ev := range order {
				acceptFixture(t, s, []SyncEvent{ev})
			}
			result, e := s.Articles(Filter{})
			if e != nil || result["total"] != 0 {
				t.Fatal(result, e)
			}
			acceptFixture(t, s, []SyncEvent{syncEv(6, 100, "article", events[1].Key, syncArticle{Title: "new", Content: "new", Published: "2026-10-26T00:00:00Z"})})
			result, e = s.Articles(Filter{})
			if e != nil || result["total"] != 1 || result["items"].([]Article)[0].Read {
				t.Fatal(result, e)
			}
		})
	}
}
