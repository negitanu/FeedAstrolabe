package app

import (
	"context"
	"encoding/json"
	"errors"
)

func (s *Server) socialAICall(ctx context.Context, op string, data json.RawMessage) (any, error) {
	switch op {
	case "social.list":
		return s.Store.SocialSources()
	case "social.save":
		v, e := input[SocialSource](data)
		if e != nil {
			return nil, e
		}
		return s.Store.SaveSocial(v)
	case "social.detail":
		v, e := input[struct {
			ID int64 `json:"id"`
		}](data)
		if e != nil {
			return nil, e
		}
		return s.Store.SocialDetail(v.ID)
	case "social.refresh":
		v, e := input[struct {
			ID int64 `json:"id"`
		}](data)
		if e != nil {
			return nil, e
		}
		return s.Collector.RefreshSocial(ctx, v.ID, true)
	case "ai.state":
		return s.Store.AIState()
	case "ai.config.save":
		v, e := input[AIConfig](data)
		if e != nil {
			return nil, e
		}
		return nil, s.Store.SaveAIConfig(v)
	case "ai.global.save":
		v, e := input[AIGlobal](data)
		if e != nil {
			return nil, e
		}
		return nil, s.Store.SaveAIGlobal(v)
	case "ai.topics.queue":
		v, e := input[struct {
			FeedID int64 `json:"feedId"`
			RunID  int64 `json:"runId"`
		}](data)
		if e != nil {
			return nil, e
		}
		return s.Store.QueueTopics(v.FeedID, v.RunID)
	case "ai.assistant.preview":
		v, e := input[struct {
			CaseID      int64   `json:"caseId"`
			Provider    string  `json:"provider"`
			Mode        string  `json:"mode"`
			Question    string  `json:"question"`
			EvidenceIDs []int64 `json:"evidenceIds"`
		}](data)
		if e != nil {
			return nil, e
		}
		return s.Store.PreviewAssistant(v.CaseID, v.Provider, v.Mode, v.Question, v.EvidenceIDs)
	case "ai.assistant.approve":
		v, e := input[struct {
			ID       int64  `json:"id"`
			Hash     string `json:"hash"`
			Approved bool   `json:"approved"`
		}](data)
		if e != nil {
			return nil, e
		}
		return s.Store.ApproveAssistant(v.ID, v.Hash, v.Approved)
	case "ai.jobs":
		v, e := input[struct {
			Kind string `json:"kind"`
			ID   int64  `json:"id"`
		}](data)
		if e != nil {
			return nil, e
		}
		return s.Store.AIJobs(v.Kind, v.ID)
	case "ai.review.save":
		v, e := input[AIReview](data)
		if e != nil {
			return nil, e
		}
		return nil, s.Store.SaveReview(v)
	case "ai.reviews":
		v, e := input[struct {
			ID int64 `json:"id"`
		}](data)
		if e != nil {
			return nil, e
		}
		return s.Store.Reviews(v.ID)
	default:
		return nil, errors.New("未対応のSNS/AI操作です")
	}
}
