package app

import (
	"context"
	"os"
	"testing"
	"time"
)

// Opt-in public GET-only smoke. No AI worker, credential or user library is used.
func TestLiveSocial(t *testing.T) {
	if os.Getenv("FEEDASTROLABE_LIVE_SOCIAL") != "1" {
		t.Skip("set FEEDASTROLABE_LIVE_SOCIAL=1 for public SNS GET requests")
	}
	for _, v := range []SocialSource{{Provider: "bluesky", Kind: "search", Target: "golang", Interval: 15, WindowHours: 24, Title: "Public smoke"}, {Provider: "mastodon", Kind: "tag", Target: "golang", Origin: "https://mastodon.social", Interval: 15, WindowHours: 168, Title: "Public smoke"}} {
		t.Run(v.Provider, func(t *testing.T) {
			s := testStore(t)
			id, e := s.SaveSocial(v)
			if e != nil {
				t.Fatal(e)
			}
			c := NewCollectorWithTLS12(s, os.Getenv("FEEDASTROLABE_LOCAL_TLS12") == "1")
			ctx, cancel := context.WithTimeout(context.Background(), 60*time.Second)
			defer cancel()
			r, e := c.RefreshSocial(ctx, id, true)
			if e != nil || r["updated"] != 1 {
				t.Fatal(r, e)
			}
			runs, e := s.SocialRuns(id)
			if e != nil || len(runs) != 1 || runs[0].Snapshot.SampleCount == 0 {
				t.Fatal("no validated public posts", e)
			}
			t.Logf("%s: %d validated posts, %d ranked", v.Provider, runs[0].Snapshot.SampleCount, len(runs[0].Snapshot.Posts))
		})
	}
}
