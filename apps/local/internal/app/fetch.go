package app

import (
	"context"
	"crypto/sha256"
	"crypto/tls"
	"encoding/hex"
	"errors"
	"fmt"
	"io"
	"net"
	"net/http"
	"net/netip"
	"net/url"
	"strings"
	"sync"
	"time"
	"unicode"

	"github.com/mmcdole/gofeed"
	"golang.org/x/net/html"
	"golang.org/x/net/idna"
)

const maxDownload = 5 * 1024 * 1024

func PublicIP(ip net.IP) bool {
	a, ok := netip.AddrFromSlice(ip)
	if !ok {
		return false
	}
	a = a.Unmap()
	if !a.IsGlobalUnicast() || a.IsPrivate() || a.IsLoopback() || a.IsLinkLocalUnicast() || a.IsUnspecified() {
		return false
	}
	for _, s := range []string{"0.0.0.0/8", "100.64.0.0/10", "192.0.0.0/24", "192.0.2.0/24", "198.18.0.0/15", "198.51.100.0/24", "203.0.113.0/24", "240.0.0.0/4", "2001:db8::/32", "2001::/23", "2002::/16", "64:ff9b::/96", "64:ff9b:1::/48", "::/96"} {
		if netip.MustParsePrefix(s).Contains(a) {
			return false
		}
	}
	return true
}
func parseURL(raw string) (*url.URL, error) {
	u, err := url.Parse(strings.TrimSpace(raw))
	if err != nil || u.Hostname() == "" || u.User != nil || u.Fragment != "" || (u.Scheme != "https" && u.Scheme != "http") {
		return nil, errors.New("HTTP(S)の公開URLを入力してください")
	}
	port := u.Port()
	if port != "" && !((u.Scheme == "https" && port == "443") || (u.Scheme == "http" && port == "80")) {
		return nil, errors.New("標準HTTP(S)ポートのみ利用できます")
	}
	if ip := net.ParseIP(u.Hostname()); ip != nil && !PublicIP(ip) {
		return nil, errors.New("プライベートIPは取得できません")
	}
	host := strings.ToLower(u.Hostname())
	if net.ParseIP(host) == nil {
		host, err = idna.Lookup.ToASCII(host)
		if err != nil {
			return nil, errors.New("ホスト名が不正です")
		}
	}
	if strings.Contains(host, ":") {
		host = "[" + host + "]"
	}
	u.Host = host
	if u.Path == "" {
		u.Path = "/"
	}
	return u, nil
}
func newSafeClient() *http.Client {
	transport := &http.Transport{Proxy: nil, DisableCompression: true, TLSClientConfig: &tls.Config{MinVersion: tls.VersionTLS12}, ResponseHeaderTimeout: 15 * time.Second, MaxResponseHeaderBytes: 1 << 20}
	transport.DialContext = func(ctx context.Context, network, address string) (net.Conn, error) {
		host, port, err := net.SplitHostPort(address)
		if err != nil {
			return nil, err
		}
		ips, err := net.DefaultResolver.LookupIP(ctx, "ip", host)
		if err != nil {
			return nil, err
		}
		if len(ips) == 0 {
			return nil, errors.New("DNS応答が空です")
		}
		for _, ip := range ips {
			if !PublicIP(ip) {
				return nil, errors.New("公開IP以外へ接続できません")
			}
		}
		d := net.Dialer{Timeout: 10 * time.Second}
		var last error
		for _, ip := range ips {
			conn, e := d.DialContext(ctx, network, net.JoinHostPort(ip.String(), port))
			if e == nil {
				return conn, nil
			}
			last = e
		}
		return nil, last
	}
	return &http.Client{Transport: transport, Timeout: 20 * time.Second, CheckRedirect: func(req *http.Request, via []*http.Request) error {
		if len(via) >= 5 {
			return errors.New("リダイレクトが多すぎます")
		}
		_, err := parseURL(req.URL.String())
		return err
	}}
}

type Collector struct {
	Store  *Store
	client *http.Client
	mu     sync.Mutex
}

func NewCollector(s *Store) *Collector { return NewCollectorWithTLS12(s, false) }

// NewCollectorWithTLS12 changes only the explicitly requested maximum TLS version.
func NewCollectorWithTLS12(s *Store, compat bool) *Collector {
	client := newSafeClient()
	if compat {
		client.Transport.(*http.Transport).TLSClientConfig.MaxVersion = tls.VersionTLS12
	}
	return &Collector{Store: s, client: client}
}
func (c *Collector) download(ctx context.Context, raw string) ([]byte, *url.URL, error) {
	u, err := parseURL(raw)
	if err != nil {
		return nil, nil, err
	}
	req, err := http.NewRequestWithContext(ctx, "GET", u.String(), nil)
	if err != nil {
		return nil, nil, err
	}
	req.Header.Set("User-Agent", "FeedAstrolabe-local/0.1 (+RSS reader)")
	req.Header.Set("Accept-Encoding", "identity")
	req.Header.Set("Accept", "application/rss+xml, application/atom+xml, application/xml, text/xml, text/html;q=0.8")
	resp, err := c.client.Do(req)
	if err != nil {
		return nil, nil, err
	}
	defer resp.Body.Close()
	if resp.StatusCode != 200 {
		return nil, nil, fmt.Errorf("HTTP %d", resp.StatusCode)
	}
	if v := resp.Header.Get("Content-Encoding"); v != "" && v != "identity" {
		return nil, nil, errors.New("圧縮された応答は取得できません")
	}
	if resp.ContentLength > maxDownload {
		return nil, nil, errors.New("応答が5MiBを超えています")
	}
	data, err := io.ReadAll(io.LimitReader(resp.Body, maxDownload+1))
	if err != nil {
		return nil, nil, err
	}
	if len(data) > maxDownload {
		return nil, nil, errors.New("応答が5MiBを超えています")
	}
	return data, resp.Request.URL, nil
}
func safeXML(b []byte) error {
	s := strings.ToLower(string(b))
	if strings.Contains(s, "<!doctype") || strings.Contains(s, "<!entity") {
		return errors.New("DTD・実体宣言は利用できません")
	}
	if strings.IndexByte(string(b), 0) >= 0 {
		return errors.New("XMLはUTF-8で指定してください")
	}
	return nil
}
func parseFeed(data []byte) (*gofeed.Feed, error) {
	if err := safeXML(data); err != nil {
		return nil, err
	}
	f, err := gofeed.NewParser().ParseString(string(data))
	if err != nil {
		return nil, errors.New("RSS / Atomを解析できません")
	}
	if len(f.Items) > 2000 {
		return nil, errors.New("1回の取得は2000記事までです")
	}
	return f, nil
}
func textHTML(raw string) string {
	doc, err := html.Parse(strings.NewReader(raw))
	if err != nil {
		return raw
	}
	var b strings.Builder
	var walk func(*html.Node)
	walk = func(n *html.Node) {
		if n.Type == html.ElementNode {
			switch n.Data {
			case "script", "style", "iframe", "object", "noscript", "svg":
				return
			case "p", "br", "div", "li", "h1", "h2", "h3", "blockquote":
				b.WriteByte('\n')
			}
		}
		if n.Type == html.TextNode {
			b.WriteString(n.Data)
		}
		for v := n.FirstChild; v != nil; v = v.NextSibling {
			walk(v)
		}
	}
	walk(doc)
	lines := []string{}
	for _, line := range strings.Split(b.String(), "\n") {
		line = strings.TrimFunc(line, unicode.IsSpace)
		if line != "" {
			lines = append(lines, line)
		}
	}
	return strings.Join(lines, "\n")
}
func httpLink(raw string, base *url.URL) string {
	u, err := url.Parse(raw)
	if err != nil {
		return ""
	}
	if base != nil {
		u = base.ResolveReference(u)
	}
	if u.User != nil || u.Hostname() == "" || (u.Scheme != "http" && u.Scheme != "https") {
		return ""
	}
	return u.String()
}

type Preview struct {
	URL     string    `json:"url"`
	Title   string    `json:"title"`
	SiteURL string    `json:"siteUrl"`
	Items   []Article `json:"items"`
}

func articlesFromFeed(f *gofeed.Feed, base *url.URL) []Article {
	out := []Article{}
	stamp := now()
	for _, v := range f.Items {
		content := v.Content
		if content == "" {
			content = v.Description
		}
		content = SanitizeRichHTML(content, base)
		link := httpLink(v.Link, base)
		uid := v.GUID
		if uid == "" {
			uid = link
		}
		if uid == "" {
			h := sha256.Sum256([]byte(textHTML(v.Title)))
			uid = hex.EncodeToString(h[:])
		}
		published := stamp
		if v.PublishedParsed != nil {
			published = v.PublishedParsed.UTC().Format(timestampFormat)
		} else if v.UpdatedParsed != nil {
			published = v.UpdatedParsed.UTC().Format(timestampFormat)
		}
		title := textHTML(v.Title)
		if title == "" {
			title = "（無題）"
		}
		out = append(out, Article{UID: uid, Title: title, URL: link, Content: content, Published: published, Collected: stamp})
	}
	return out
}
func (c *Collector) Preview(ctx context.Context, raw string) ([]Preview, error) {
	data, base, err := c.download(ctx, raw)
	if err != nil {
		return nil, err
	}
	if f, e := parseFeed(data); e == nil {
		return []Preview{{base.String(), textHTML(f.Title), httpLink(f.Link, base), articlesFromFeed(f, base)}}, nil
	}
	if err = safeXML(data); err != nil && !strings.Contains(strings.ToLower(string(data)), "<html") {
		return nil, err
	}
	doc, err := html.Parse(strings.NewReader(string(data)))
	if err != nil {
		return nil, errors.New("フィードが見つかりません")
	}
	urls := []string{}
	seen := map[string]bool{}
	var walk func(*html.Node)
	walk = func(n *html.Node) {
		if n.Type == html.ElementNode && n.Data == "link" {
			attrs := map[string]string{}
			for _, a := range n.Attr {
				attrs[a.Key] = a.Val
			}
			rel := " " + strings.ToLower(attrs["rel"]) + " "
			typ := strings.ToLower(attrs["type"])
			if strings.Contains(rel, " alternate ") && (typ == "application/rss+xml" || typ == "application/atom+xml") {
				u := httpLink(attrs["href"], base)
				if _, e := parseURL(u); e == nil && !seen[u] && len(urls) < 8 {
					seen[u] = true
					urls = append(urls, u)
				}
			}
		}
		for v := n.FirstChild; v != nil; v = v.NextSibling {
			walk(v)
		}
	}
	walk(doc)
	out := []Preview{}
	for _, u := range urls {
		b, final, e := c.download(ctx, u)
		if e != nil {
			continue
		}
		f, e := parseFeed(b)
		if e != nil {
			continue
		}
		items := articlesFromFeed(f, final)
		if len(items) > 5 {
			items = items[:5]
		}
		out = append(out, Preview{final.String(), textHTML(f.Title), httpLink(f.Link, final), items})
	}
	if len(out) == 0 {
		return nil, errors.New("RSS / Atomが見つかりません。フィードURLを直接指定してください")
	}
	return out, nil
}
func (c *Collector) Subscribe(ctx context.Context, raw, title string, folder int64) (int64, error) {
	c.mu.Lock()
	defer c.mu.Unlock()
	data, base, err := c.download(ctx, raw)
	if err != nil {
		return 0, err
	}
	f, err := parseFeed(data)
	if err != nil {
		return 0, err
	}
	if title == "" {
		title = textHTML(f.Title)
	}
	if title == "" {
		title = base.Hostname()
	}
	if err = validName(title); err != nil {
		return 0, err
	}
	tx, err := c.Store.DB.Begin()
	if err != nil {
		return 0, err
	}
	defer tx.Rollback()
	r, err := tx.Exec("INSERT INTO feeds(folder_id,title,url,site_url,position,last_fetched) VALUES(?,?,?,?,(SELECT COALESCE(MAX(position),0)+1 FROM feeds),?)", nullableID(folder), title, base.String(), httpLink(f.Link, base), now())
	if err != nil {
		return 0, errors.New("登録済みURLまたはフォルダーの指定が不正です")
	}
	id, err := r.LastInsertId()
	if err != nil {
		return 0, err
	}
	for _, a := range articlesFromFeed(f, base) {
		if _, err = tx.Exec("INSERT OR IGNORE INTO articles(feed_id,uid,title,url,content,published,collected) VALUES(?,?,?,?,?,?,?)", id, a.UID, a.Title, a.URL, a.Content, a.Published, a.Collected); err != nil {
			return 0, err
		}
	}
	return id, tx.Commit()
}
func (c *Collector) Refresh(ctx context.Context, id int64) (map[string]any, error) {
	return c.refresh(ctx, id, true)
}
func (c *Collector) refresh(ctx context.Context, id int64, force bool) (map[string]any, error) {
	if !c.mu.TryLock() {
		return nil, errors.New("更新は実行中です")
	}
	defer c.mu.Unlock()
	feeds, err := c.Store.Feeds()
	if err != nil {
		return nil, err
	}
	count := 0
	failures := []string{}
	for _, v := range feeds {
		var source string
		_ = c.Store.DB.QueryRow("SELECT source FROM sync_feed_meta WHERE feed_id=?", v.ID).Scan(&source)
		if (source != "" && source != "rss") || strings.HasPrefix(v.URL, "social:") || v.Paused || (id != 0 && id != v.ID) {
			continue
		}
		if !force && v.LastFetched != "" {
			interval := v.Interval
			if interval == 0 {
				settings, e := c.Store.Settings()
				if e != nil {
					return nil, e
				}
				interval = settings.Interval * 60
			}
			last, e := time.Parse(timestampFormat, v.LastFetched)
			if e == nil && time.Now().Before(last.Add(time.Duration(interval)*time.Second)) {
				continue
			}
		}
		b, base, e := c.download(ctx, v.URL)
		var f *gofeed.Feed
		if e == nil {
			f, e = parseFeed(b)
		}
		if e != nil {
			if _, err = c.Store.DB.Exec("UPDATE feeds SET last_fetched=?,last_error=? WHERE id=?", now(), e.Error(), v.ID); err != nil {
				return nil, err
			}
			failures = append(failures, v.Title+": "+e.Error())
			continue
		}
		tx, e := c.Store.DB.Begin()
		if e != nil {
			return nil, e
		}
		for _, a := range articlesFromFeed(f, base) {
			_, e = tx.Exec("INSERT INTO articles(feed_id,uid,title,url,content,published,collected) VALUES(?,?,?,?,?,?,?) ON CONFLICT(feed_id,uid) DO UPDATE SET title=excluded.title,url=excluded.url,content=excluded.content", v.ID, a.UID, a.Title, a.URL, a.Content, a.Published, a.Collected)
			if e != nil {
				break
			}
		}
		if e == nil {
			_, e = tx.Exec("UPDATE feeds SET last_fetched=?,last_error='' WHERE id=?", now(), v.ID)
		}
		if e != nil {
			tx.Rollback()
			return nil, e
		}
		if e = tx.Commit(); e != nil {
			return nil, e
		}
		count++
	}
	return map[string]any{"updated": count, "errors": failures}, nil
}
func (c *Collector) Run(ctx context.Context) {
	timer := time.NewTimer(time.Second)
	defer timer.Stop()
	for {
		select {
		case <-ctx.Done():
			return
		case <-timer.C:
			settings, e := c.Store.Settings()
			if e == nil && !settings.PauseCollection {
				_, _ = c.refresh(ctx, 0, false)
				_, _ = c.RefreshSocial(ctx, 0, false)
			}
			timer.Reset(time.Minute)
		}
	}
}

func (c *Collector) HTTPClient() *http.Client { return c.client }
