package app

import (
	"context"
	"encoding/json"
	"errors"
	"net/url"
	"regexp"
	"strings"
)

func (w *AIWorker) generate(ctx context.Context, j AIJob) (any, any, any, *int64, error) {
	key, e := credential(j.Provider)
	if e != nil {
		return nil, nil, nil, nil, e
	}
	if strings.HasPrefix(j.Provider, "ollama-") {
		return w.ollama(ctx, j, key)
	}
	endpoint := "https://openrouter.ai/api/v1/chat/completions"
	if j.Provider == "orcarouter" {
		endpoint = "https://api.orcarouter.ai/v1/chat/completions"
	}
	b, h, e := requestJSON(ctx, w.Client, "POST", endpoint, j.Input.Body, key, 1024*1024, false)
	if e != nil {
		return nil, nil, nil, nil, e
	}
	var response struct {
		ID      string `json:"id"`
		Model   string `json:"model"`
		Choices []struct {
			Finish  string `json:"finish_reason"`
			Message struct {
				Role    string          `json:"role"`
				Content string          `json:"content"`
				Refusal json.RawMessage `json:"refusal"`
				Tools   json.RawMessage `json:"tool_calls"`
			} `json:"message"`
		} `json:"choices"`
		Usage struct {
			Prompt     *int64          `json:"prompt_tokens"`
			Completion *int64          `json:"completion_tokens"`
			Cost       json.RawMessage `json:"cost"`
			OrcaCost   json.RawMessage `json:"cost_usd"`
		} `json:"usage"`
	}
	if json.Unmarshal(b, &response) != nil || len(response.Choices) != 1 {
		return nil, nil, nil, nil, errors.New("AI応答の形式が不正です")
	}
	choice := response.Choices[0]
	if choice.Finish != "stop" || choice.Message.Role != "assistant" || choice.Message.Content == "" || len(choice.Message.Content) > 1024*1024 || len(choice.Message.Refusal) > 0 && string(choice.Message.Refusal) != "null" || len(choice.Message.Tools) > 0 && string(choice.Message.Tools) != "null" && string(choice.Message.Tools) != "[]" {
		return nil, nil, nil, nil, errors.New("AI応答が拒否・途中切れ・ツール呼出しを含みます")
	}
	if response.Usage.Prompt == nil || response.Usage.Completion == nil || *response.Usage.Prompt < 0 || *response.Usage.Prompt > int64(len(j.Input.Body)+256) || *response.Usage.Completion < 0 || *response.Usage.Completion > j.Config.MaxTokens {
		return nil, nil, nil, nil, errors.New("AI利用量が不明または上限超過です")
	}
	cost := response.Usage.Cost
	receipt := "inline"
	requestID := response.ID
	if j.Provider == "orcarouter" {
		requestID = h.Get("X-Orca-Request-Id")
		if !regexp.MustCompile(`^[A-Za-z0-9_-]{1,200}$`).MatchString(requestID) {
			return nil, nil, nil, nil, errors.New("OrcaRouterの処理IDが不正です")
		}
		cost = response.Usage.OrcaCost
		if len(cost) == 0 || string(cost) == "null" {
			receipt = "unknown"
			for i := 0; i < 2; i++ {
				data, _, err := requestJSON(ctx, w.Client, "GET", "https://api.orcarouter.ai/v1/generation?id="+url.QueryEscape(requestID), nil, key, 1024*1024, false)
				if err != nil {
					continue
				}
				var r struct {
					Data struct {
						ID       string          `json:"id"`
						Currency string          `json:"cost_currency"`
						Cost     json.RawMessage `json:"total_cost"`
					} `json:"data"`
				}
				if json.Unmarshal(data, &r) != nil || r.Data.ID != requestID || r.Data.Currency != "" && r.Data.Currency != "USD" {
					break
				}
				if len(r.Data.Cost) > 0 && string(r.Data.Cost) != "null" {
					cost = r.Data.Cost
					receipt = "settlement"
					break
				}
			}
		}
	}
	actual, e := microUSD(cost)
	if e != nil {
		return nil, nil, nil, nil, e
	}
	if j.Provider == "openrouter" && actual == nil {
		return nil, nil, nil, nil, errors.New("OpenRouterの費用が不明です")
	}
	if actual != nil && *actual > j.Reserved {
		return nil, nil, nil, actual, errors.New("申告費用が予約額を超過しました")
	}
	output, e := validateAIOutput(choice.Message.Content, j.Input)
	if e != nil {
		return nil, nil, nil, actual, e
	}
	usage := map[string]any{"promptTokens": response.Usage.Prompt, "completionTokens": response.Usage.Completion, "costMicro": actual}
	lineage := map[string]any{"provider": j.Provider, "requestedModel": j.Config.Model, "returnedModel": response.Model, "requestId": requestID, "adapter": "router-json-v1", "costSource": receipt}
	return output, usage, lineage, actual, nil
}
func (w *AIWorker) ollama(ctx context.Context, j AIJob, key string) (any, any, any, *int64, error) {
	local := j.Provider == "ollama-local"
	client := w.Client
	base := "https://ollama.com"
	lineage := map[string]any{"provider": j.Provider, "requestedModel": j.Config.Model, "adapter": "ollama-json-v1"}
	if local {
		client = w.LocalClient
		base = "http://127.0.0.1:11434"
		data, _, e := requestJSON(ctx, client, "GET", base+"/api/status", nil, "", 1024*1024, true)
		if e != nil {
			return nil, nil, nil, nil, e
		}
		var status struct {
			Cloud struct {
				Disabled bool `json:"disabled"`
			} `json:"cloud"`
		}
		if json.Unmarshal(data, &status) != nil || !status.Cloud.Disabled {
			return nil, nil, nil, nil, errors.New("Ollamaのクラウド無効化を確認できません")
		}
		data, _, e = requestJSON(ctx, client, "GET", base+"/api/tags", nil, "", 1024*1024, true)
		if e != nil {
			return nil, nil, nil, nil, e
		}
		var tags struct {
			Models []struct {
				Name        string `json:"name"`
				Model       string `json:"model"`
				Digest      string `json:"digest"`
				RemoteHost  string `json:"remote_host"`
				RemoteModel string `json:"remote_model"`
			} `json:"models"`
		}
		if json.Unmarshal(data, &tags) != nil {
			return nil, nil, nil, nil, errors.New("Ollamaのモデル一覧が不正です")
		}
		found := false
		for _, m := range tags.Models {
			if m.Name == j.Config.Model || m.Model == j.Config.Model {
				if m.Digest != j.Config.Digest || m.RemoteHost != "" || m.RemoteModel != "" {
					return nil, nil, nil, nil, errors.New("Ollamaのモデルdigestまたはローカル性が不一致です")
				}
				found = true
			}
		}
		if !found {
			return nil, nil, nil, nil, errors.New("指定のローカルモデルがありません")
		}
		data, _, e = requestJSON(ctx, client, "GET", base+"/api/version", nil, "", 1024*1024, true)
		if e != nil {
			return nil, nil, nil, nil, e
		}
		var version struct {
			Version string `json:"version"`
		}
		if json.Unmarshal(data, &version) != nil || version.Version == "" {
			return nil, nil, nil, nil, errors.New("Ollamaの版が不明です")
		}
		lineage["runtimeVersion"] = version.Version
		lineage["digest"] = j.Config.Digest
	}
	data, _, e := requestJSON(ctx, client, "POST", base+"/api/chat", j.Input.Body, key, 1024*1024, local)
	if e != nil {
		return nil, nil, nil, nil, e
	}
	var r struct {
		Model   string `json:"model"`
		Done    bool   `json:"done"`
		Reason  string `json:"done_reason"`
		Prompt  *int64 `json:"prompt_eval_count"`
		Output  *int64 `json:"eval_count"`
		Message struct {
			Role    string          `json:"role"`
			Content string          `json:"content"`
			Tools   json.RawMessage `json:"tool_calls"`
		} `json:"message"`
	}
	if json.Unmarshal(data, &r) != nil || !r.Done || r.Reason != "stop" || r.Message.Role != "assistant" || r.Model == "" || r.Prompt == nil || r.Output == nil || *r.Prompt < 0 || *r.Prompt > int64(len(j.Input.Body)+256) || *r.Output < 0 || *r.Output > j.Config.MaxTokens || len(r.Message.Tools) > 0 && string(r.Message.Tools) != "null" && string(r.Message.Tools) != "[]" {
		return nil, nil, nil, nil, errors.New("Ollamaの完了状態・利用量が不正です")
	}
	if local && r.Model != j.Config.Model && r.Model != j.Config.Model+":latest" {
		return nil, nil, nil, nil, errors.New("Ollama応答のモデルが指定と一致しません")
	}
	output, e := validateAIOutput(r.Message.Content, j.Input)
	if e != nil {
		return nil, nil, nil, nil, e
	}
	lineage["returnedModel"] = r.Model
	actual := int64(0)
	var actualPtr *int64
	if local {
		actualPtr = &actual
	}
	return output, map[string]any{"promptTokens": r.Prompt, "completionTokens": r.Output, "costMicro": actualPtr}, lineage, actualPtr, nil
}

type AITopic struct {
	Title       string  `json:"title"`
	Summary     string  `json:"summary"`
	Importance  int     `json:"importance"`
	Reason      string  `json:"reason"`
	Uncertainty string  `json:"uncertainty"`
	ArticleIDs  []int64 `json:"articleIds"`
}
type AIClaim struct {
	Text      string  `json:"text"`
	Citations []int64 `json:"citations"`
}

func validateAIOutput(raw string, in AIInput) (any, error) {
	var shape map[string]json.RawMessage
	if e := decodeStrict([]byte(raw), &shape); e != nil || shape == nil {
		return nil, errors.New("AI出力JSONが不正です")
	}
	if in.Kind == "topics" {
		if len(shape) != 1 || shape["topics"] == nil {
			return nil, errors.New("話題抽出のフィールドが不正です")
		}
		var rows []map[string]json.RawMessage
		if json.Unmarshal(shape["topics"], &rows) != nil {
			return nil, errors.New("話題抽出の配列が不正です")
		}
		for _, row := range rows {
			if len(row) != 6 {
				return nil, errors.New("話題抽出の必須フィールドがありません")
			}
			for _, key := range []string{"title", "summary", "importance", "reason", "uncertainty", "articleIds"} {
				if row[key] == nil {
					return nil, errors.New("話題抽出の必須フィールドがありません")
				}
			}
		}
	} else {
		if len(shape) != 3 || shape["answer"] == nil || shape["claims"] == nil || shape["uncertainty"] == nil {
			return nil, errors.New("調査補助の必須フィールドがありません")
		}
		var claims []map[string]json.RawMessage
		if json.Unmarshal(shape["claims"], &claims) != nil {
			return nil, errors.New("調査補助のclaimが不正です")
		}
		for _, c := range claims {
			if len(c) != 2 || c["text"] == nil || c["citations"] == nil {
				return nil, errors.New("調査補助のclaimフィールドが不正です")
			}
		}
	}

	allowed := map[int64]bool{}
	for _, r := range in.References {
		allowed[r.ID] = true
	}
	validIDs := func(ids []int64) bool {
		if len(ids) < 1 || len(ids) > 8 {
			return false
		}
		seen := map[int64]bool{}
		for _, id := range ids {
			if !allowed[id] || seen[id] {
				return false
			}
			seen[id] = true
		}
		return true
	}
	validText := func(s string, n int) bool {
		return strings.TrimSpace(s) != "" && len([]rune(s)) <= n && !secretPattern.MatchString(s)
	}
	if in.Kind == "topics" {
		var v struct {
			Topics []AITopic `json:"topics"`
		}
		if decodeStrict([]byte(raw), &v) != nil || v.Topics == nil || len(v.Topics) > 5 {
			return nil, errors.New("話題抽出のJSON形式が不正です")
		}
		seen := map[string]bool{}
		for _, t := range v.Topics {
			key := strings.ToLower(t.Title)
			if !validText(t.Title, 120) || !validText(t.Summary, 800) || !validText(t.Reason, 600) || !validText(t.Uncertainty, 400) || t.Importance < 0 || t.Importance > 100 || !validIDs(t.ArticleIDs) || seen[key] {
				return nil, errors.New("話題抽出の本文・出典IDが不正です")
			}
			seen[key] = true
		}
		return v, nil
	}
	var v struct {
		Answer      string    `json:"answer"`
		Claims      []AIClaim `json:"claims"`
		Uncertainty string    `json:"uncertainty"`
	}
	if decodeStrict([]byte(raw), &v) != nil || !validText(v.Answer, 8000) || v.Claims == nil || len(v.Claims) > 20 || !validText(v.Uncertainty, 2000) {
		return nil, errors.New("調査補助のJSON形式が不正です")
	}
	for _, c := range v.Claims {
		if !validText(c.Text, 2000) || !validIDs(c.Citations) {
			return nil, errors.New("調査補助の出典IDが不正です")
		}
	}
	return v, nil
}
