package main

import (
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/paralin/go-dota2/protocol"
)

func TestHealthReflectsGCReadiness(t *testing.T) {
	service := &gcService{}

	request := httptest.NewRequest(http.MethodGet, "/health", nil)
	response := httptest.NewRecorder()
	service.routes().ServeHTTP(response, request)
	if response.Code != http.StatusServiceUnavailable {
		t.Fatalf("unready status = %d, want %d", response.Code, http.StatusServiceUnavailable)
	}

	service.ready.Store(true)
	response = httptest.NewRecorder()
	service.routes().ServeHTTP(response, request)
	if response.Code != http.StatusOK {
		t.Fatalf("ready status = %d, want %d", response.Code, http.StatusOK)
	}
}

func TestAuthorization(t *testing.T) {
	service := &gcService{config: config{token: "secret"}}
	handler := service.routes()

	request := httptest.NewRequest(http.MethodGet, "/health", nil)
	response := httptest.NewRecorder()
	handler.ServeHTTP(response, request)
	if response.Code != http.StatusUnauthorized {
		t.Fatalf("missing token status = %d, want %d", response.Code, http.StatusUnauthorized)
	}

	request = httptest.NewRequest(http.MethodGet, "/health", nil)
	request.Header.Set("Authorization", "Bearer secret")
	response = httptest.NewRecorder()
	handler.ServeHTTP(response, request)
	if response.Code != http.StatusServiceUnavailable {
		t.Fatalf("valid token status = %d, want %d", response.Code, http.StatusServiceUnavailable)
	}
}

func TestPlayerHistoryRejectsAnotherAccount(t *testing.T) {
	service := &gcService{}
	service.ready.Store(true)
	service.authenticatedAccountID.Store(42)

	request := httptest.NewRequest(http.MethodGet, "/players/43/matches", nil)
	response := httptest.NewRecorder()
	service.routes().ServeHTTP(response, request)
	if response.Code != http.StatusForbidden {
		t.Fatalf("status = %d, want %d", response.Code, http.StatusForbidden)
	}
}

func TestRadiantWin(t *testing.T) {
	tests := []struct {
		name    string
		outcome protocol.EMatchOutcome
		want    *bool
	}{
		{name: "radiant", outcome: protocol.EMatchOutcome_k_EMatchOutcome_RadVictory, want: boolPointer(true)},
		{name: "dire", outcome: protocol.EMatchOutcome_k_EMatchOutcome_DireVictory, want: boolPointer(false)},
		{name: "unknown", outcome: protocol.EMatchOutcome_k_EMatchOutcome_Unknown, want: nil},
	}

	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			got := radiantWin(test.outcome)
			if got == nil || test.want == nil {
				if got != test.want {
					t.Fatalf("radiantWin(%s) = %v, want %v", test.outcome, got, test.want)
				}

				return
			}
			if *got != *test.want {
				t.Fatalf("radiantWin(%s) = %v, want %v", test.outcome, *got, *test.want)
			}
		})
	}
}

func TestReplayState(t *testing.T) {
	if got := replayState(protocol.CMsgDOTAMatch_REPLAY_EXPIRED); got != "expired" {
		t.Fatalf("replayState(expired) = %q, want expired", got)
	}
	if got := replayState(protocol.CMsgDOTAMatch_REPLAY_NOT_RECORDED); got != "not_recorded" {
		t.Fatalf("replayState(not recorded) = %q, want not_recorded", got)
	}
}

func boolPointer(value bool) *bool {
	return &value
}
