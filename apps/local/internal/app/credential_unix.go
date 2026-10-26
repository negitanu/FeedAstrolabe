//go:build !windows

package app

import (
	"errors"
	"io"
	"os"
	"strings"
	"syscall"
)

func readOllamaToken() (string, error) {
	path := os.Getenv("FEEDASTROLABE_OLLAMA_TOKEN_FILE")
	bad := errors.New("Ollamaクラウドの所有者専用token file（0600）が未設定または不正です")
	info, e := os.Lstat(path)
	if e != nil || !info.Mode().IsRegular() || info.Mode().Perm() != 0600 || info.Size() > 4096 {
		return "", bad
	}
	stat, ok := info.Sys().(*syscall.Stat_t)
	if !ok || stat.Uid != uint32(os.Getuid()) {
		return "", bad
	}
	f, e := os.Open(path)
	if e != nil {
		return "", bad
	}
	defer f.Close()
	actual, e := f.Stat()
	if e != nil || !os.SameFile(info, actual) || actual.Mode().Perm() != 0600 {
		return "", bad
	}
	b, e := io.ReadAll(io.LimitReader(f, 4097))
	key := strings.TrimSpace(string(b))
	if e != nil || len(b) > 4096 || len(key) < 16 || strings.ContainsAny(key, "\r\n\x00 ") {
		return "", bad
	}
	return key, nil
}
