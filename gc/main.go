package main

import (
	"context"
	"crypto/subtle"
	"encoding/json"
	"errors"
	"fmt"
	"log/slog"
	"math"
	"net/http"
	"os"
	"os/signal"
	"strconv"
	"strings"
	"sync/atomic"
	"syscall"
	"time"

	dota2 "github.com/paralin/go-dota2"
	devents "github.com/paralin/go-dota2/events"
	"github.com/paralin/go-dota2/protocol"
	steam "github.com/paralin/go-steam"
	"github.com/paralin/go-steam/protocol/steamlang"
	"github.com/sirupsen/logrus"
)

const (
	reconnectDelay       = 5 * time.Second
	matchHistoryPageSize = uint32(20)
)

type config struct {
	host           string
	port           string
	token          string
	username       string
	password       string
	accessToken    string
	authCode       string
	twoFactorCode  string
	deviceName     string
	requestTimeout time.Duration
}

type gcService struct {
	config                 config
	client                 *steam.Client
	dota                   *dota2.Dota2
	ready                  atomic.Bool
	authenticatedAccountID atomic.Uint32
}

type matchPlayer struct {
	ID        uint32 `json:"id"`
	Name      string `json:"name,omitempty"`
	IsRadiant bool   `json:"is_radiant"`
}

type matchDetails struct {
	MatchID    uint64        `json:"match_id"`
	Cluster    uint32        `json:"cluster,omitempty"`
	ReplaySalt uint32        `json:"replay_salt,omitempty"`
	Duration   uint32        `json:"duration,omitempty"`
	StartTime  uint32        `json:"start_time,omitempty"`
	LeagueID   uint32        `json:"league_id,omitempty"`
	RadiantWin *bool         `json:"radiant_win,omitempty"`
	Players    []matchPlayer `json:"players"`
}

func main() {
	if len(os.Args) == 2 && os.Args[1] == "healthcheck" {
		if err := healthcheck(); err != nil {
			os.Exit(1)
		}

		return
	}

	if err := run(); err != nil {
		slog.Error("Dota GC service stopped", "error", err)
		os.Exit(1)
	}
}

func healthcheck() error {
	request, err := http.NewRequest(http.MethodGet, "http://127.0.0.1:"+environment("PORT", "5700")+"/health", nil)
	if err != nil {
		return err
	}
	if token := os.Getenv("DOTA_GC_TOKEN"); token != "" {
		request.Header.Set("Authorization", "Bearer "+token)
	}

	client := &http.Client{Timeout: 3 * time.Second}
	response, err := client.Do(request)
	if err != nil {
		return err
	}
	defer response.Body.Close()

	if response.StatusCode != http.StatusOK {
		return fmt.Errorf("health endpoint returned %s", response.Status)
	}

	return nil
}

func run() error {
	cfg, err := loadConfig()
	if err != nil {
		return err
	}

	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()

	logger := logrus.New()
	logger.SetOutput(os.Stderr)
	logger.SetLevel(logrus.WarnLevel)

	client := steam.NewClient()
	service := &gcService{
		config: cfg,
		client: client,
		dota:   dota2.New(client, logger),
	}

	go service.runSteam(ctx)

	server := &http.Server{
		Addr:              cfg.host + ":" + cfg.port,
		Handler:           service.routes(),
		ReadHeaderTimeout: 5 * time.Second,
		IdleTimeout:       60 * time.Second,
	}

	serverError := make(chan error, 1)
	go func() {
		slog.Info("Dota GC service listening", "address", server.Addr)
		serverError <- server.ListenAndServe()
	}()

	select {
	case <-ctx.Done():
		shutdownCtx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
		defer cancel()

		return server.Shutdown(shutdownCtx)
	case err := <-serverError:
		if errors.Is(err, http.ErrServerClosed) {
			return nil
		}

		return err
	}
}

func loadConfig() (config, error) {
	cfg := config{
		host:          environment("HOST", "127.0.0.1"),
		port:          environment("PORT", "5700"),
		token:         os.Getenv("DOTA_GC_TOKEN"),
		username:      os.Getenv("STEAM_USERNAME"),
		password:      os.Getenv("STEAM_PASSWORD"),
		accessToken:   os.Getenv("STEAM_ACCESS_TOKEN"),
		authCode:      os.Getenv("STEAM_AUTH_CODE"),
		twoFactorCode: os.Getenv("STEAM_TFA_CODE"),
		deviceName:    environment("STEAM_DEVICE_NAME", "wardmap-dota-gc"),
	}

	if cfg.username == "" {
		return config{}, errors.New("STEAM_USERNAME is required")
	}
	if cfg.password == "" && cfg.accessToken == "" {
		return config{}, errors.New("STEAM_PASSWORD or STEAM_ACCESS_TOKEN is required")
	}

	timeout, err := time.ParseDuration(environment("DOTA_GC_REQUEST_TIMEOUT", "30s"))
	if err != nil || timeout <= 0 {
		return config{}, errors.New("DOTA_GC_REQUEST_TIMEOUT must be a positive duration")
	}
	cfg.requestTimeout = timeout

	return cfg, nil
}

func environment(name, fallback string) string {
	if value := strings.TrimSpace(os.Getenv(name)); value != "" {
		return value
	}

	return fallback
}

func (s *gcService) runSteam(ctx context.Context) {
	s.client.Connect()

	helloTicker := time.NewTicker(reconnectDelay)
	defer helloTicker.Stop()

	loggedOn := false
	for {
		select {
		case <-ctx.Done():
			s.ready.Store(false)
			s.authenticatedAccountID.Store(0)
			s.dota.Close()
			if s.client.Connected() {
				s.dota.SetPlaying(false)
			}
			s.client.Disconnect()

			return
		case <-helloTicker.C:
			if loggedOn && !s.ready.Load() {
				s.dota.SayHello()
			}
		case rawEvent := <-s.client.Events():
			switch event := rawEvent.(type) {
			case *steam.ConnectedEvent:
				if err := s.client.Auth.LogOn(ctx, &steam.LogOnDetails{
					Username:           s.config.username,
					Password:           s.config.password,
					AccessToken:        s.config.accessToken,
					DeviceFriendlyName: s.config.deviceName,
					AuthCode:           s.config.authCode,
					TwoFactorCode:      s.config.twoFactorCode,
				}); err != nil {
					slog.Error("Steam authentication failed", "error", err)
				}
			case *steam.LoggedOnEvent:
				if event.Result != steamlang.EResult_OK {
					slog.Error("Steam logon failed", "result", event.Result)

					continue
				}
				loggedOn = true
				s.authenticatedAccountID.Store(s.client.SteamId().GetAccountId())
				s.dota.SetPlaying(true)
				s.dota.SayHello()
			case *devents.ClientWelcomed:
				s.ready.Store(true)
				slog.Info("Dota Game Coordinator is ready")
			case *devents.GCConnectionStatusChanged:
				if event.NewState != protocol.GCConnectionStatus_GCConnectionStatus_HAVE_SESSION {
					s.ready.Store(false)
				}
			case *steam.LoggedOffEvent:
				loggedOn = false
				s.ready.Store(false)
				s.authenticatedAccountID.Store(0)
				slog.Warn("Steam logged off", "result", event.Result)
			case *steam.DisconnectedEvent:
				loggedOn = false
				s.ready.Store(false)
				s.authenticatedAccountID.Store(0)
				slog.Warn("Steam disconnected; reconnecting")
				time.AfterFunc(reconnectDelay, func() {
					if ctx.Err() == nil {
						s.client.Connect()
					}
				})
			case steam.FatalErrorEvent:
				loggedOn = false
				s.ready.Store(false)
				s.authenticatedAccountID.Store(0)
				slog.Error("Steam connection failure", "error", error(event))
			case error:
				slog.Error("Steam client error", "error", event)
			}
		}
	}
}

func (s *gcService) routes() http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /health", s.health)
	mux.HandleFunc("GET /account", s.account)
	mux.HandleFunc("GET /players/{accountID}/matches", s.playerMatches)
	mux.HandleFunc("GET /matches/{matchID}", s.matchDetails)

	return s.authorize(mux)
}

func (s *gcService) account(response http.ResponseWriter, _ *http.Request) {
	accountID := s.authenticatedAccountID.Load()
	if !s.ready.Load() || accountID == 0 {
		writeJSON(response, http.StatusServiceUnavailable, map[string]string{"error": "Dota Game Coordinator is not ready"})

		return
	}

	writeJSON(response, http.StatusOK, map[string]uint32{"account_id": accountID})
}

func (s *gcService) authorize(next http.Handler) http.Handler {
	return http.HandlerFunc(func(response http.ResponseWriter, request *http.Request) {
		if s.config.token != "" {
			expected := "Bearer " + s.config.token
			provided := request.Header.Get("Authorization")
			if len(expected) != len(provided) || subtle.ConstantTimeCompare([]byte(expected), []byte(provided)) != 1 {
				writeJSON(response, http.StatusUnauthorized, map[string]string{"error": "Unauthorized"})

				return
			}
		}

		next.ServeHTTP(response, request)
	})
}

func (s *gcService) health(response http.ResponseWriter, _ *http.Request) {
	status := http.StatusOK
	if !s.ready.Load() {
		status = http.StatusServiceUnavailable
	}

	writeJSON(response, status, map[string]bool{"ready": s.ready.Load()})
}

func (s *gcService) playerMatches(response http.ResponseWriter, request *http.Request) {
	if !s.ready.Load() {
		writeJSON(response, http.StatusServiceUnavailable, map[string]string{"error": "Dota Game Coordinator is not ready"})

		return
	}

	accountID, err := parseUint32(request.PathValue("accountID"))
	if err != nil || accountID == 0 {
		writeJSON(response, http.StatusBadRequest, map[string]string{"error": "Invalid account ID"})

		return
	}
	if accountID != s.authenticatedAccountID.Load() {
		writeJSON(response, http.StatusForbidden, map[string]string{"error": "Only the authenticated account can be synchronized"})

		return
	}

	limit := uint32(100)
	if value := request.URL.Query().Get("limit"); value != "" {
		parsed, parseErr := parseUint32(value)
		if parseErr != nil || parsed == 0 {
			writeJSON(response, http.StatusBadRequest, map[string]string{"error": "Invalid match limit"})

			return
		}
		limit = min(parsed, 100)
	}

	requestCtx, cancel := context.WithTimeout(request.Context(), s.config.requestTimeout)
	defer cancel()

	matches, err := s.playerMatchIDs(requestCtx, accountID, limit)
	if err != nil {
		writeGCError(response, err)

		return
	}

	writeJSON(response, http.StatusOK, map[string]any{"matches": matches})
}

func (s *gcService) playerMatchIDs(ctx context.Context, accountID uint32, limit uint32) ([]uint64, error) {
	includePractice := false
	includeCustom := false
	startAtMatchID := uint64(0)
	requestID := uint32(time.Now().UnixNano())
	matches := make([]uint64, 0, limit)

	for uint32(len(matches)) < limit {
		pageSize := min(matchHistoryPageSize, limit-uint32(len(matches)))
		result, err := s.dota.GetPlayerMatchHistory(ctx, &protocol.CMsgDOTAGetPlayerMatchHistory{
			AccountId:              &accountID,
			StartAtMatchId:         &startAtMatchID,
			MatchesRequested:       &pageSize,
			RequestId:              &requestID,
			IncludePracticeMatches: &includePractice,
			IncludeCustomGames:     &includeCustom,
		})
		if err != nil {
			return nil, err
		}

		page := result.GetMatches()
		for _, match := range page {
			if matchID := match.GetMatchId(); matchID != 0 {
				matches = append(matches, matchID)
			}
		}
		if uint32(len(page)) < pageSize || len(matches) == 0 {
			break
		}

		lastMatchID := page[len(page)-1].GetMatchId()
		if lastMatchID <= 1 {
			break
		}
		startAtMatchID = lastMatchID - 1
		requestID++
	}

	return matches, nil
}

func (s *gcService) matchDetails(response http.ResponseWriter, request *http.Request) {
	if !s.ready.Load() {
		writeJSON(response, http.StatusServiceUnavailable, map[string]string{"error": "Dota Game Coordinator is not ready"})

		return
	}

	matchID, err := strconv.ParseUint(request.PathValue("matchID"), 10, 64)
	if err != nil || matchID == 0 {
		writeJSON(response, http.StatusBadRequest, map[string]string{"error": "Invalid match ID"})

		return
	}

	requestCtx, cancel := context.WithTimeout(request.Context(), s.config.requestTimeout)
	defer cancel()

	result, err := s.dota.RequestMatchDetails(requestCtx, matchID)
	if err != nil {
		writeGCError(response, err)

		return
	}

	match := result.GetMatch()
	if match == nil || match.GetMatchId() == 0 {
		writeJSON(response, http.StatusNotFound, map[string]string{"error": "Match not found"})

		return
	}

	players := make([]matchPlayer, 0, len(match.GetPlayers()))
	for _, player := range match.GetPlayers() {
		if player.GetAccountId() == 0 {
			continue
		}
		players = append(players, matchPlayer{
			ID:        player.GetAccountId(),
			Name:      player.GetPlayerName(),
			IsRadiant: player.GetPlayerSlot() < 128,
		})
	}

	details := matchDetails{
		MatchID:    match.GetMatchId(),
		Cluster:    match.GetCluster(),
		ReplaySalt: match.GetReplaySalt(),
		Duration:   match.GetDuration(),
		StartTime:  match.GetStarttime(),
		LeagueID:   match.GetLeagueid(),
		RadiantWin: radiantWin(match.GetMatchOutcome()),
		Players:    players,
	}
	writeJSON(response, http.StatusOK, map[string]any{"match": details})
}

func radiantWin(outcome protocol.EMatchOutcome) *bool {
	var won bool
	switch outcome {
	case protocol.EMatchOutcome_k_EMatchOutcome_RadVictory:
		won = true
	case protocol.EMatchOutcome_k_EMatchOutcome_DireVictory:
		won = false
	default:
		return nil
	}

	return &won
}

func parseUint32(value string) (uint32, error) {
	parsed, err := strconv.ParseUint(value, 10, 32)
	if err != nil || parsed > math.MaxUint32 {
		return 0, fmt.Errorf("invalid uint32 %q", value)
	}

	return uint32(parsed), nil
}

func writeGCError(response http.ResponseWriter, err error) {
	status := http.StatusBadGateway
	if errors.Is(err, context.DeadlineExceeded) {
		status = http.StatusGatewayTimeout
	}

	slog.Warn("Dota GC request failed", "error", err)
	writeJSON(response, status, map[string]string{"error": "Dota GC request failed"})
}

func writeJSON(response http.ResponseWriter, status int, payload any) {
	response.Header().Set("Content-Type", "application/json")
	response.WriteHeader(status)
	if err := json.NewEncoder(response).Encode(payload); err != nil {
		slog.Error("Unable to write HTTP response", "error", err)
	}
}
