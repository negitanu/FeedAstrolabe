package app

import (
	"bytes"
	"context"
	"errors"
	"fmt"
	"io"
	"net/http"
	"strconv"
	"strings"
	"time"
)

type serviceError struct {
	Status int
	Until  string
}

func (e *serviceError) Error() string {
	return fmt.Sprintf("接続先がHTTP %dを返しました", e.Status)
}
func retryAt(h http.Header) string {
	end := time.Now().UTC().Add(15 * time.Minute)
	if n, e := strconv.Atoi(h.Get("Retry-After")); e == nil && n >= 0 {
		end = time.Now().UTC().Add(time.Duration(n) * time.Second)
	} else if d, e := http.ParseTime(h.Get("Retry-After")); e == nil {
		end = d
	}
	for _, key := range []string{"X-RateLimit-Reset", "RateLimit-Reset"} {
		raw := h.Get(key)
		if n, e := strconv.ParseInt(raw, 10, 64); e == nil && n > time.Now().Unix() {
			d := time.Unix(n, 0)
			if d.After(end) {
				end = d
			}
		}
	}
	max := time.Now().UTC().Add(7 * 24 * time.Hour)
	if end.After(max) {
		end = max
	}
	if end.Before(time.Now()) {
		end = time.Now().UTC().Add(time.Minute)
	}
	return end.UTC().Format(timestampFormat)
}
func requestJSON(ctx context.Context, client *http.Client, method, raw string, body []byte, key string, max int, local bool) ([]byte, http.Header, error) {
	if local {
		if !strings.HasPrefix(raw, "http://127.0.0.1:11434/api/") {
			return nil, nil, errors.New("ローカルOllama接続先が不正です")
		}
	} else {
		u, e := parseURL(raw)
		if e != nil || u.Scheme != "https" {
			return nil, nil, errors.New("公開HTTPS接続先のみ利用できます")
		}
	}
	req, e := http.NewRequestWithContext(ctx, method, raw, bytes.NewReader(body))
	if e != nil {
		return nil, nil, errors.New("要求が不正です")
	}
	req.Header.Set("Accept", "application/json")
	req.Header.Set("Accept-Encoding", "identity")
	req.Header.Set("User-Agent", "FeedAstrolabe-local/0.2")
	if method == "POST" {
		req.Header.Set("Content-Type", "application/json")
	}
	if key != "" {
		req.Header.Set("Authorization", "Bearer "+key)
	}
	if strings.HasPrefix(raw, "https://api.orcarouter.ai/") {
		req.Header.Set("X-OrcaRouter-Include-Cost", "true")
	}
	copyClient := *client
	copyClient.CheckRedirect = func(*http.Request, []*http.Request) error { return http.ErrUseLastResponse }
	res, e := copyClient.Do(req)
	if e != nil {
		return nil, nil, errors.New("接続に失敗しました（タイムアウト・TLS・公開IPを確認してください）")
	}
	defer res.Body.Close()
	if res.StatusCode != 200 {
		err := &serviceError{Status: res.StatusCode}
		if res.StatusCode == 429 {
			err.Until = retryAt(res.Header)
		}
		return nil, res.Header, err
	}
	if v := res.Header.Get("Content-Encoding"); v != "" && v != "identity" {
		return nil, nil, errors.New("圧縮応答は利用できません")
	}
	if res.ContentLength > int64(max) {
		return nil, nil, errors.New("応答サイズが上限を超えました")
	}
	b, e := io.ReadAll(io.LimitReader(res.Body, int64(max)+1))
	if e != nil || len(b) > max {
		return nil, nil, errors.New("応答の読込みに失敗しました")
	}
	if !jsonValid(b) || uniqueJSON(b) != nil {
		return nil, nil, errors.New("JSON応答が不正です")
	}
	return b, res.Header, nil
}
func (s *Store) checkWait(service string) error {
	var until string
	err := s.DB.QueryRow("SELECT until_at FROM service_waits WHERE service=?", service).Scan(&until)
	if err == nil && until > now() {
		return fmt.Errorf("接続先は %s まで待機中です", until)
	}
	return nil
}
func (s *Store) setWait(service string, e error) error {
	var se *serviceError
	if errors.As(e, &se) && se.Status == 429 {
		_, err := s.DB.Exec("INSERT INTO service_waits(service,until_at) VALUES(?,?) ON CONFLICT(service) DO UPDATE SET until_at=max(until_at,excluded.until_at)", service, se.Until)
		return err
	}
	return nil
}
