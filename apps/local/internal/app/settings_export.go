package app

import (
	"encoding/json"
	"errors"
)

type SyncSettingsExport struct {
	URL string `json:"url"`
}

type SettingsExport struct {
	Sync     *SyncSettingsExport `json:"sync,omitempty"`
	Format   string              `json:"format"`
	Version  int                 `json:"version"`
	Settings Settings            `json:"settings"`
	Configs  []AIConfig          `json:"configs,omitempty"`
	Global   *AIGlobal           `json:"global,omitempty"`
}

func (s *Store) ExportSettings() (SettingsExport, error) {
	out := SettingsExport{Format: "feedastrolabe-local-settings", Version: 3}
	v, e := s.Settings()
	if e != nil {
		return out, e
	}
	connection, e := s.SyncConnection()
	if e != nil {
		return out, e
	}
	out.Sync = &SyncSettingsExport{URL: connection.URL}
	out.Settings = v
	for _, p := range aiProviders {
		c, e := s.AIConfig(p)
		if e != nil {
			return out, e
		}
		out.Configs = append(out.Configs, c)
	}
	g, e := s.AIGlobal()
	if e != nil {
		return out, e
	}
	out.Global = &g
	return out, nil
}
func (s *Store) ImportSettings(v SettingsExport) error {
	if v.Format != "feedastrolabe-local-settings" || v.Version != 1 && v.Version != 2 && v.Version != 3 {
		return errors.New("未対応の設定形式です")
	}
	if e := validateSettings(v.Settings); e != nil {
		return e
	}
	if v.Version >= 2 && len(v.Configs) != 4 {
		return errors.New("AI設定の構成が不正です")
	}
	if v.Sync != nil {
		if _, e := validSyncURL(v.Sync.URL); e != nil {
			return e
		}
	}
	seen := map[string]bool{}
	for _, c := range v.Configs {
		if e := validConfig(c); e != nil {
			return e
		}
		if seen[c.Provider] {
			return errors.New("AI設定が重複しています")
		}
		seen[c.Provider] = true
	}
	g := v.Global
	if g != nil && ((g.Active != "openrouter" && g.Active != "orcarouter") || g.DailyCalls < 1 || g.DailyCalls > 1000 || g.DailyMicro < 1 || g.DailyMicro > 100000000) {
		return errors.New("日次予算が不正です")
	}
	tx, e := s.DB.Begin()
	if e != nil {
		return e
	}
	defer tx.Rollback()
	b, _ := json.Marshal(v.Settings)
	if _, e = tx.Exec("UPDATE settings SET value=? WHERE id=1", string(b)); e != nil {
		return e
	}
	for _, c := range v.Configs {
		var old string
		if e = tx.QueryRow("SELECT value FROM ai_configs WHERE provider=?", c.Provider).Scan(&old); e != nil {
			return e
		}
		var previous AIConfig
		if e = json.Unmarshal([]byte(old), &previous); e != nil {
			return e
		}
		c.Enabled = false
		c.Revision = previous.Revision + 1
		if _, e = tx.Exec("UPDATE ai_configs SET value=? WHERE provider=?", jsonString(c), c.Provider); e != nil {
			return e
		}
	}
	if g != nil {
		if _, e = tx.Exec("UPDATE ai_global SET active=?,daily_micro=?,daily_calls=?,revision=revision+1 WHERE id=1", g.Active, g.DailyMicro, g.DailyCalls); e != nil {
			return e
		}
	}
	if v.Sync != nil {
		u, _ := validSyncURL(v.Sync.URL)
		if _, e = tx.Exec("UPDATE sync_connection SET url=?,enabled=0,cursor=0,sent=0,hub='',last_success='',error='' WHERE id=1", u); e != nil {
			return e
		}
	}
	return tx.Commit()
}
