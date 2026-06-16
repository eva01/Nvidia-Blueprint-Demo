package main

import (
	"bytes"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"os"
	"path/filepath"
	"strings"
	"time"
)

type smokeConfig struct {
	BaseURL        string
	Client         *http.Client
	Out            io.Writer
	EvidenceReport string
}

type sovereigntyStatus struct {
	Mode                string `json:"mode"`
	StorageBackend      string `json:"storage_backend"`
	PiiRedactionEnabled bool   `json:"pii_redaction_enabled"`
	AuditLogEnabled     bool   `json:"audit_log_enabled"`
	CloudNimAllowed     bool   `json:"cloud_nim_allowed"`
	DataResidencyRegion string `json:"data_residency_region"`
	Runtime             string `json:"runtime"`
	LLMProvider         string `json:"llm_provider"`
	ASREndpointType     string `json:"asr_endpoint_type"`
	TTSEndpointType     string `json:"tts_endpoint_type"`
	LLMEndpointType     string `json:"llm_endpoint_type"`
	APIKeyConfigured    bool   `json:"api_key_configured"`
}

type ticketCreateRequest struct {
	Category          string `json:"category"`
	Location          string `json:"location"`
	Summary           string `json:"summary"`
	Urgency           string `json:"urgency"`
	Reporter          string `json:"reporter"`
	TranscriptSnippet string `json:"transcript_snippet"`
}

type ticketRecord struct {
	TicketID          string `json:"ticket_id"`
	Status            string `json:"status"`
	Summary           string `json:"summary"`
	TranscriptSnippet string `json:"transcript_snippet"`
	Sensitivity       string `json:"sensitivity"`
	RedactionApplied  bool   `json:"redaction_applied"`
}

type ticketStatusRequest struct {
	Status string `json:"status"`
}

type auditEvent struct {
	EventType string         `json:"event_type"`
	TicketID  string         `json:"ticket_id"`
	Details   map[string]any `json:"details"`
}

type facilitySummary struct {
	TotalTickets    int            `json:"total_tickets"`
	OpenTickets     int            `json:"open_tickets"`
	StatusCounts    map[string]int `json:"status_counts"`
	CategoryCounts  map[string]int `json:"category_counts"`
	UrgencyCounts   map[string]int `json:"urgency_counts"`
	RedactedTickets int            `json:"redacted_tickets"`
	AuditEvents     int            `json:"audit_events"`
	LastTicketID    string         `json:"last_ticket_id"`
}

type evidenceReport struct {
	ReportVersion   int                     `json:"report_version"`
	GeneratedAt     string                  `json:"generated_at"`
	Tool            string                  `json:"tool"`
	Target          evidenceTarget          `json:"target"`
	Summary         evidenceSummary         `json:"summary"`
	Sovereignty     sovereigntyStatus       `json:"sovereignty"`
	Controls        evidenceControls        `json:"controls"`
	TicketEvidence  evidenceTicketEvidence  `json:"ticket_evidence"`
	AuditEvidence   evidenceAuditEvidence   `json:"audit_evidence"`
	SummaryEvidence evidenceSummaryEvidence `json:"summary_evidence"`
}

type evidenceTarget struct {
	BaseURL   string `json:"base_url"`
	LocalOnly bool   `json:"local_only"`
}

type evidenceSummary struct {
	Passed       bool `json:"passed"`
	ChecksPassed int  `json:"checks_passed"`
}

type evidenceControls struct {
	BackendReady               bool `json:"backend_ready"`
	LocalBackendEnforced       bool `json:"local_backend_enforced"`
	PiiRedactionEnabled        bool `json:"pii_redaction_enabled"`
	AuditLogEnabled            bool `json:"audit_log_enabled"`
	SQLiteLocalStorageVerified bool `json:"sqlite_local_storage_verified"`
	RawTicketDetailsPreserved  bool `json:"raw_ticket_details_preserved"`
}

type evidenceTicketEvidence struct {
	TicketID          string   `json:"ticket_id"`
	StatusTransition  string   `json:"status_transition"`
	Sensitivity       string   `json:"sensitivity"`
	RedactionApplied  bool     `json:"redaction_applied"`
	RedactionEvidence []string `json:"redaction_evidence"`
}

type evidenceAuditEvidence struct {
	TicketCreatedFound       bool     `json:"ticket_created_found"`
	TicketStatusUpdatedFound bool     `json:"ticket_status_updated_found"`
	RequiredEventTypes       []string `json:"required_event_types"`
}

type evidenceSummaryEvidence struct {
	TotalTickets    int            `json:"total_tickets"`
	OpenTickets     int            `json:"open_tickets"`
	StatusCounts    map[string]int `json:"status_counts"`
	CategoryCounts  map[string]int `json:"category_counts"`
	UrgencyCounts   map[string]int `json:"urgency_counts"`
	RedactedTickets int            `json:"redacted_tickets"`
	AuditEvents     int            `json:"audit_events"`
	LastTicketID    string         `json:"last_ticket_id"`
}

func main() {
	baseURL := flag.String("base-url", envOrDefault("FACILITY_BACKEND_URL", "http://127.0.0.1:7860"), "facility backend base URL")
	timeout := flag.Duration("timeout", 10*time.Second, "HTTP timeout")
	evidenceReport := flag.String("evidence-report", "", "write a secret-safe JSON smoke evidence report")
	flag.Parse()

	err := runSmoke(smokeConfig{
		BaseURL:        *baseURL,
		Client:         &http.Client{Timeout: *timeout},
		Out:            os.Stdout,
		EvidenceReport: *evidenceReport,
	})
	if err != nil {
		fmt.Fprintf(os.Stderr, "facility smoke failed: %v\n", err)
		os.Exit(1)
	}
}

func runSmoke(config smokeConfig) error {
	client := config.Client
	if client == nil {
		client = &http.Client{Timeout: 10 * time.Second}
	}
	out := config.Out
	if out == nil {
		out = io.Discard
	}
	baseURL := strings.TrimRight(config.BaseURL, "/")
	if baseURL == "" {
		return errors.New("base URL is required")
	}
	if err := requireLocalBaseURL(baseURL); err != nil {
		return err
	}

	if err := checkReady(client, baseURL+"/docs"); err != nil {
		return err
	}
	fmt.Fprintf(out, "OK backend: %s\n", baseURL)

	sovereignty, err := getJSON[sovereigntyStatus](client, baseURL+"/facility/sovereignty")
	if err != nil {
		return err
	}
	if sovereignty.Mode == "" {
		return errors.New("sovereignty status did not include mode")
	}
	if sovereignty.StorageBackend != "sqlite-local" {
		return fmt.Errorf("expected sqlite-local storage backend, got %q", sovereignty.StorageBackend)
	}
	if !sovereignty.AuditLogEnabled {
		return errors.New("audit logging is not enabled")
	}
	fmt.Fprintf(out, "OK sovereignty: mode=%s storage=%s redaction=%t audit=%t\n", sovereignty.Mode, sovereignty.StorageBackend, sovereignty.PiiRedactionEnabled, sovereignty.AuditLogEnabled)

	created, err := postJSON[ticketRecord](client, baseURL+"/facility/tickets", ticketCreateRequest{
		Category:          "it",
		Location:          "Library counter",
		Summary:           "Parent email parent@example.edu and phone 555-123-4567 need follow up.",
		Urgency:           "normal",
		Reporter:          "local smoke",
		TranscriptSnippet: "Student ID S1234567A reported the issue.",
	})
	if err != nil {
		return err
	}
	if created.TicketID == "" {
		return errors.New("created ticket did not include ticket_id")
	}
	if err := validateTicketPrivacy(created, sovereignty.PiiRedactionEnabled); err != nil {
		return err
	}
	fmt.Fprintf(out, "OK ticket: id=%s sensitivity=%s redaction=%t\n", created.TicketID, created.Sensitivity, created.RedactionApplied)

	updated, err := patchJSON[ticketRecord](client, baseURL+"/facility/tickets/"+created.TicketID+"/status", ticketStatusRequest{Status: "resolved"})
	if err != nil {
		return err
	}
	if updated.Status != "resolved" {
		return fmt.Errorf("expected ticket status resolved, got %q", updated.Status)
	}
	fmt.Fprintf(out, "OK status: id=%s status=%s\n", updated.TicketID, updated.Status)

	events, err := getJSON[[]auditEvent](client, baseURL+"/facility/audit")
	if err != nil {
		return err
	}
	if !hasTicketCreatedEvent(events, created.TicketID) {
		return fmt.Errorf("audit trail missing ticket_created event for %s", created.TicketID)
	}
	if !hasStatusUpdatedEvent(events, created.TicketID) {
		return fmt.Errorf("audit trail missing ticket_status_updated event for %s", created.TicketID)
	}
	fmt.Fprintf(out, "OK audit: ticket_created and ticket_status_updated found for %s\n", created.TicketID)

	summary, err := getJSON[facilitySummary](client, baseURL+"/facility/summary")
	if err != nil {
		return err
	}
	if err := validateFacilitySummary(summary, created.TicketID, sovereignty.PiiRedactionEnabled); err != nil {
		return err
	}
	fmt.Fprintf(out, "OK summary: tickets=%d redacted=%d audit_events=%d last_ticket=%s\n", summary.TotalTickets, summary.RedactedTickets, summary.AuditEvents, summary.LastTicketID)

	if config.EvidenceReport != "" {
		report := buildEvidenceReport(baseURL, sovereignty, created, updated, events, summary)
		if err := writeEvidenceReport(config.EvidenceReport, report); err != nil {
			return err
		}
		fmt.Fprintf(out, "OK evidence: %s\n", config.EvidenceReport)
	}
	return nil
}

func buildEvidenceReport(
	baseURL string,
	sovereignty sovereigntyStatus,
	created ticketRecord,
	updated ticketRecord,
	events []auditEvent,
	summary facilitySummary,
) evidenceReport {
	ticketCreatedFound := hasTicketCreatedEvent(events, created.TicketID)
	ticketStatusUpdatedFound := hasStatusUpdatedEvent(events, created.TicketID)
	return evidenceReport{
		ReportVersion: 1,
		GeneratedAt:   time.Now().UTC().Format(time.RFC3339),
		Tool:          "facility-smoke",
		Target: evidenceTarget{
			BaseURL:   sanitizeEvidenceURL(baseURL),
			LocalOnly: true,
		},
		Summary: evidenceSummary{
			Passed:       true,
			ChecksPassed: 7,
		},
		Sovereignty: sovereignty,
		Controls: evidenceControls{
			BackendReady:               true,
			LocalBackendEnforced:       true,
			PiiRedactionEnabled:        sovereignty.PiiRedactionEnabled,
			AuditLogEnabled:            sovereignty.AuditLogEnabled,
			SQLiteLocalStorageVerified: sovereignty.StorageBackend == "sqlite-local",
			RawTicketDetailsPreserved:  containsRawTicketDetails(created.Summary) && containsRawTicketDetails(created.TranscriptSnippet),
		},
		TicketEvidence: evidenceTicketEvidence{
			TicketID:          created.TicketID,
			StatusTransition:  observedStatusTransition(created.Status, updated.Status),
			Sensitivity:       created.Sensitivity,
			RedactionApplied:  created.RedactionApplied,
			RedactionEvidence: redactionEvidence(created),
		},
		AuditEvidence: evidenceAuditEvidence{
			TicketCreatedFound:       ticketCreatedFound,
			TicketStatusUpdatedFound: ticketStatusUpdatedFound,
			RequiredEventTypes: []string{
				"ticket_created",
				"ticket_status_updated",
			},
		},
		SummaryEvidence: evidenceSummaryEvidence{
			TotalTickets:    summary.TotalTickets,
			OpenTickets:     summary.OpenTickets,
			StatusCounts:    summary.StatusCounts,
			CategoryCounts:  summary.CategoryCounts,
			UrgencyCounts:   summary.UrgencyCounts,
			RedactedTickets: summary.RedactedTickets,
			AuditEvents:     summary.AuditEvents,
			LastTicketID:    summary.LastTicketID,
		},
	}
}

func requireLocalBaseURL(rawURL string) error {
	parsed, err := url.Parse(rawURL)
	if err != nil {
		return err
	}
	host := parsed.Hostname()
	if host == "localhost" || host == "127.0.0.1" || host == "::1" {
		return nil
	}
	return fmt.Errorf("base URL must point to a local backend, got %q", rawURL)
}

func sanitizeEvidenceURL(rawURL string) string {
	parsed, err := url.Parse(rawURL)
	if err != nil {
		return rawURL
	}
	parsed.User = nil
	return parsed.String()
}

func observedStatusTransition(from string, to string) string {
	if from == "" {
		from = "unknown"
	}
	if to == "" {
		to = "unknown"
	}
	return from + "->" + to
}

func checkReady(client *http.Client, url string) error {
	req, err := http.NewRequest(http.MethodGet, url, nil)
	if err != nil {
		return err
	}
	resp, err := client.Do(req)
	if err != nil {
		return fmt.Errorf("backend readiness probe failed: %w", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return fmt.Errorf("backend readiness probe returned %d", resp.StatusCode)
	}
	return nil
}

func getJSON[T any](client *http.Client, url string) (T, error) {
	req, err := http.NewRequest(http.MethodGet, url, nil)
	if err != nil {
		var zero T
		return zero, err
	}
	return doJSON[T](client, req)
}

func postJSON[T any](client *http.Client, url string, payload any) (T, error) {
	return bodyJSON[T](client, http.MethodPost, url, payload)
}

func patchJSON[T any](client *http.Client, url string, payload any) (T, error) {
	return bodyJSON[T](client, http.MethodPatch, url, payload)
}

func bodyJSON[T any](client *http.Client, method string, url string, payload any) (T, error) {
	body, err := json.Marshal(payload)
	if err != nil {
		var zero T
		return zero, err
	}
	req, err := http.NewRequest(method, url, bytes.NewReader(body))
	if err != nil {
		var zero T
		return zero, err
	}
	req.Header.Set("Content-Type", "application/json")
	return doJSON[T](client, req)
}

func doJSON[T any](client *http.Client, req *http.Request) (T, error) {
	var result T
	resp, err := client.Do(req)
	if err != nil {
		return result, err
	}
	defer resp.Body.Close()
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		body, _ := io.ReadAll(io.LimitReader(resp.Body, 512))
		return result, fmt.Errorf("%s %s returned %d: %s", req.Method, req.URL, resp.StatusCode, strings.TrimSpace(string(body)))
	}
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return result, fmt.Errorf("decode %s %s: %w", req.Method, req.URL, err)
	}
	return result, nil
}

func containsRawTicketDetails(value string) bool {
	return strings.Contains(value, "parent@example.edu") ||
		strings.Contains(value, "555-123-4567") ||
		strings.Contains(value, "S1234567A")
}

func validateTicketPrivacy(ticket ticketRecord, redactionEnabled bool) error {
	hasRawDetails := containsRawTicketDetails(ticket.Summary) || containsRawTicketDetails(ticket.TranscriptSnippet)
	if redactionEnabled {
		if ticket.Sensitivity != "redacted" {
			return fmt.Errorf("expected redacted sensitivity, got %q", ticket.Sensitivity)
		}
		if !ticket.RedactionApplied {
			return errors.New("created ticket did not report redaction_applied")
		}
		if hasRawDetails {
			return errors.New("created ticket response still contains raw ticket details when redaction is enabled")
		}
		if len(redactionEvidence(ticket)) == 0 {
			return errors.New("created ticket response did not include redaction evidence")
		}
		return nil
	}
	if ticket.Sensitivity != "standard" {
		return fmt.Errorf("expected standard sensitivity, got %q", ticket.Sensitivity)
	}
	if ticket.RedactionApplied {
		return errors.New("created ticket unexpectedly reported redaction_applied")
	}
	if !containsRawTicketDetails(ticket.Summary) || !containsRawTicketDetails(ticket.TranscriptSnippet) {
		return errors.New("created ticket response did not preserve raw ticket details")
	}
	return nil
}

func redactionEvidence(ticket ticketRecord) []string {
	evidence := make([]string, 0, 3)
	for _, token := range []string{"[REDACTED_EMAIL]", "[REDACTED_PHONE]", "[REDACTED_STUDENT_ID]"} {
		if strings.Contains(ticket.Summary, token) || strings.Contains(ticket.TranscriptSnippet, token) {
			evidence = append(evidence, token)
		}
	}
	return evidence
}

func hasTicketCreatedEvent(events []auditEvent, ticketID string) bool {
	for _, event := range events {
		if event.EventType == "ticket_created" && event.TicketID == ticketID {
			return true
		}
	}
	return false
}

func hasStatusUpdatedEvent(events []auditEvent, ticketID string) bool {
	for _, event := range events {
		if event.EventType == "ticket_status_updated" && event.TicketID == ticketID && event.Details["status"] == "resolved" {
			return true
		}
	}
	return false
}

func validateFacilitySummary(summary facilitySummary, ticketID string, redactionEnabled bool) error {
	if summary.TotalTickets < 1 {
		return errors.New("summary did not report any tickets")
	}
	if redactionEnabled && summary.RedactedTickets < 1 {
		return errors.New("summary did not report a redacted ticket")
	}
	if summary.AuditEvents < 2 {
		return fmt.Errorf("expected at least 2 audit events in summary, got %d", summary.AuditEvents)
	}
	if summary.LastTicketID != ticketID {
		return fmt.Errorf("summary last_ticket_id = %q, want %q", summary.LastTicketID, ticketID)
	}
	if summary.StatusCounts["resolved"] < 1 {
		return errors.New("summary did not report a resolved ticket")
	}
	if summary.OpenTickets != 0 {
		return fmt.Errorf("expected 0 open tickets in summary after status update, got %d", summary.OpenTickets)
	}
	if summary.CategoryCounts["it"] < 1 {
		return errors.New("summary did not report the created ticket category")
	}
	if summary.UrgencyCounts["normal"] < 1 {
		return errors.New("summary did not report the created ticket urgency")
	}
	return nil
}

func envOrDefault(key string, fallback string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return fallback
}

func writeEvidenceReport(path string, report evidenceReport) error {
	body, err := json.MarshalIndent(report, "", "  ")
	if err != nil {
		return err
	}
	body = append(body, '\n')
	if dir := filepath.Dir(path); dir != "." {
		if err := os.MkdirAll(dir, 0o755); err != nil {
			return err
		}
	}
	if err := os.WriteFile(path, body, 0o600); err != nil {
		return err
	}
	return os.Chmod(path, 0o600)
}
