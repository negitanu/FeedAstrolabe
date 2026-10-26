package main

import (
	"bufio"
	"context"
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"flag"
	"fmt"
	"log"
	"net"
	"net/http"
	"os"
	"os/signal"
	"path/filepath"
	"syscall"
	"time"

	"feedastrolabe.local/desktop/internal/app"
)

func main() {
	if err := run(); err != nil {
		log.Fatal(err)
	}
}
func run() error {
	dir := flag.String("data-dir", "", "データ保存先（絶対パス）")
	tls12 := flag.Bool("tls12", os.Getenv("FEEDASTROLABE_LOCAL_TLS12") == "1", "TLS 1.2互換モード（明示指定時のみ）")
	stdio := flag.Bool("parent-stdin", false, "親のstdinが閉じたら終了")
	flag.Parse()
	if *dir == "" {
		d, err := os.UserConfigDir()
		if err != nil {
			return err
		}
		*dir = filepath.Join(d, "FeedAstrolabe Local", "library")
	}
	if !filepath.IsAbs(*dir) {
		return fmt.Errorf("data-dirは絶対パスで指定してください")
	}
	store, err := app.Open(*dir)
	if err != nil {
		return err
	}
	defer store.Close()
	ctx, cancel := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer cancel()
	if *stdio {
		go func() {
			scanner := bufio.NewScanner(os.Stdin)
			for scanner.Scan() {
			}
			cancel()
		}()
	}
	b := make([]byte, 32)
	if _, err = rand.Read(b); err != nil {
		return err
	}
	token := hex.EncodeToString(b)
	collector := app.NewCollectorWithTLS12(store, *tls12)
	worker := app.NewAIWorker(store, collector.HTTPClient())
	api := &app.Server{Store: store, Collector: collector, Token: token}
	listener, err := net.Listen("tcp4", "127.0.0.1:0")
	if err != nil {
		return err
	}
	server := &http.Server{Handler: api.Handler(), ReadHeaderTimeout: 5 * time.Second, ReadTimeout: 30 * time.Second, WriteTimeout: 3 * time.Minute, IdleTimeout: 30 * time.Second, MaxHeaderBytes: 16 * 1024}
	done := make(chan struct{})
	go func() { defer close(done); collector.Run(ctx) }()
	aiDone := make(chan struct{})
	go func() { defer close(aiDone); worker.Run(ctx) }()
	serveErr := make(chan error, 1)
	go func() { serveErr <- server.Serve(listener) }()
	if err = json.NewEncoder(os.Stdout).Encode(map[string]any{"type": "ready", "url": "http://" + listener.Addr().String(), "token": token, "version": "0.1.0"}); err != nil {
		return err
	}
	select {
	case <-ctx.Done():
	case err = <-serveErr:
		cancel()
		if err != http.ErrServerClosed {
			return err
		}
	}
	shutdownCtx, closeShutdown := context.WithTimeout(context.Background(), 5*time.Second)
	defer closeShutdown()
	if err = server.Shutdown(shutdownCtx); err != nil {
		_ = server.Close()
	}
	cancel()
	<-done
	<-aiDone
	return nil
}
