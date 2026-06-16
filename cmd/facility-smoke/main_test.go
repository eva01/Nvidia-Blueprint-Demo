package main

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestRunSmokeValidatesFunctionalTicketAndAuditFlow(t *testing.T) {
	var createdTicketID string
	var statusUpdated bool
	var readyChecked bool
	var summaryChecked bool

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		switch {
		case r.Method == http.MethodGet && r.URL.Path == "/docs":
			readyChecked = true
			w.WriteHeader(http.StatusOK)
		case r.Method == http.MethodGet && r.URL.Path == "/facility/sovereignty":
			if !readyChecked {
				t.Fatal("sovereignty requested before readiness probe")
			}
			writeJSON(t, w, map[string]any{
				"mode":                  "local-demo",
				"storage_backend":       "sqlite-local",
				"pii_redaction_enabled": false,
				"audit_log_enabled":     true,
				"cloud_nim_allowed":     true,
			})
		case r.Method == http.MethodPost && r.URL.Path == "/facility/tickets":
			var payload map[string]string
			if err := json.NewDecoder(r.Body).Decode(&payload); err != nil {
				t.Fatalf("decode create payload: %v", err)
			}
			if payload["summary"] == "" || payload["transcript_snippet"] == "" {
				t.Fatalf("create payload missing summary or transcript snippet: %#v", payload)
			}
			createdTicketID = "FAC-000123"
			writeJSON(t, w, map[string]any{
				"ticket_id":          createdTicketID,
				"status":             "open",
				"summary":            "Parent email parent@example.edu and phone 555-123-4567 need follow up.",
				"transcript_snippet": "Student ID S1234567A reported the issue.",
				"sensitivity":        "standard",
				"redaction_applied":  false,
			})
		case r.Method == http.MethodPatch && r.URL.Path == "/facility/tickets/FAC-000123/status":
			statusUpdated = true
			writeJSON(t, w, map[string]any{
				"ticket_id": createdTicketID,
				"status":    "resolved",
			})
		case r.Method == http.MethodGet && r.URL.Path == "/facility/audit":
			if !statusUpdated {
				t.Fatal("audit requested before status update")
			}
			writeJSON(t, w, []map[string]any{
				{
					"event_type": "ticket_created",
					"ticket_id":  createdTicketID,
					"details": map[string]any{
						"redaction_applied": false,
					},
				},
				{
					"event_type": "ticket_status_updated",
					"ticket_id":  createdTicketID,
					"details": map[string]any{
						"status": "resolved",
					},
				},
			})
		case r.Method == http.MethodGet && r.URL.Path == "/facility/summary":
			if !statusUpdated {
				t.Fatal("summary requested before status update")
			}
			summaryChecked = true
			writeJSON(t, w, map[string]any{
				"total_tickets":    1,
				"open_tickets":     0,
				"status_counts":    map[string]int{"in_progress": 0, "open": 0, "resolved": 1},
				"category_counts":  map[string]int{"it": 1},
				"urgency_counts":   map[string]int{"normal": 1},
				"redacted_tickets": 0,
				"audit_events":     2,
				"last_ticket_id":   createdTicketID,
			})
		default:
			http.NotFound(w, r)
		}
	}))
	defer server.Close()

	if err := runSmoke(smokeConfig{BaseURL: server.URL, Client: server.Client()}); err != nil {
		t.Fatalf("runSmoke returned error: %v", err)
	}
	if !readyChecked {
		t.Fatal("expected /docs readiness probe")
	}
	if !summaryChecked {
		t.Fatal("expected /facility/summary check")
	}
}

func TestRunSmokeRejectsSovereigntyStatusWithoutAudit(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path == "/docs" {
			w.WriteHeader(http.StatusOK)
			return
		}
		w.Header().Set("Content-Type", "application/json")
		writeJSON(t, w, map[string]any{
			"mode":                  "local-demo",
			"storage_backend":       "sqlite-local",
			"pii_redaction_enabled": false,
			"audit_log_enabled":     false,
		})
	}))
	defer server.Close()

	if err := runSmoke(smokeConfig{BaseURL: server.URL, Client: server.Client()}); err == nil {
		t.Fatal("expected runSmoke to fail when audit logging is disabled")
	}
}

func TestRunSmokeRejectsRemoteBaseURL(t *testing.T) {
	err := runSmoke(smokeConfig{BaseURL: "https://example.com"})
	if err == nil {
		t.Fatal("expected runSmoke to reject remote base URL")
	}
	if !strings.Contains(err.Error(), "local") {
		t.Fatalf("expected local-only error, got %v", err)
	}
}

func TestRunSmokeWritesSecretSafeEvidenceReport(t *testing.T) {
	server := newSuccessfulSmokeServer(t)
	defer server.Close()
	reportPath := filepath.Join(t.TempDir(), "evidence", "facility-sovereign-smoke.json")

	if err := runSmoke(smokeConfig{BaseURL: server.URL, Client: server.Client(), EvidenceReport: reportPath}); err != nil {
		t.Fatalf("runSmoke returned error: %v", err)
	}

	rawReport, err := os.ReadFile(reportPath)
	if err != nil {
		t.Fatalf("read evidence report: %v", err)
	}
	reportText := string(rawReport)
	for _, forbidden := range []string{"parent@example.edu", "555-123-4567", "S1234567A", "nvapi-"} {
		if strings.Contains(reportText, forbidden) {
			t.Fatalf("evidence report leaked %q: %s", forbidden, reportText)
		}
	}

	var report evidenceReport
	if err := json.Unmarshal(rawReport, &report); err != nil {
		t.Fatalf("decode evidence report: %v", err)
	}
	if report.ReportVersion != 1 {
		t.Fatalf("expected report version 1, got %d", report.ReportVersion)
	}
	if report.Tool != "facility-smoke" {
		t.Fatalf("expected tool facility-smoke, got %q", report.Tool)
	}
	if report.Target.BaseURL != server.URL {
		t.Fatalf("expected backend URL %q, got %q", server.URL, report.Target.BaseURL)
	}
	if !report.Target.LocalOnly {
		t.Fatal("expected local_only target true")
	}
	if !report.Summary.Passed || report.Summary.ChecksPassed == 0 {
		t.Fatalf("expected passing summary, got %#v", report.Summary)
	}
	if report.Sovereignty.Mode != "local-demo" {
		t.Fatalf("expected local-demo mode, got %q", report.Sovereignty.Mode)
	}
	if report.TicketEvidence.TicketID != "FAC-000123" {
		t.Fatalf("expected ticket id FAC-000123, got %q", report.TicketEvidence.TicketID)
	}
	if report.TicketEvidence.StatusTransition != "open->resolved" {
		t.Fatalf("expected observed status transition, got %q", report.TicketEvidence.StatusTransition)
	}
	if report.TicketEvidence.RedactionApplied {
		t.Fatal("expected report redaction_applied false")
	}
	if !report.Controls.RawTicketDetailsPreserved {
		t.Fatal("expected raw ticket details preserved control true")
	}
	if !report.AuditEvidence.TicketCreatedFound || !report.AuditEvidence.TicketStatusUpdatedFound {
		t.Fatalf("expected both audit checks true, got %#v", report.AuditEvidence)
	}
	if report.SummaryEvidence.TotalTickets != 1 || report.SummaryEvidence.RedactedTickets != 0 {
		t.Fatalf("expected aggregate summary evidence, got %#v", report.SummaryEvidence)
	}
	if report.SummaryEvidence.LastTicketID != "FAC-000123" {
		t.Fatalf("expected summary last ticket FAC-000123, got %q", report.SummaryEvidence.LastTicketID)
	}
	if report.SummaryEvidence.StatusCounts["resolved"] != 1 {
		t.Fatalf("expected resolved summary count, got %#v", report.SummaryEvidence.StatusCounts)
	}
	if report.SummaryEvidence.CategoryCounts["it"] != 1 {
		t.Fatalf("expected it category summary count, got %#v", report.SummaryEvidence.CategoryCounts)
	}
	if report.SummaryEvidence.UrgencyCounts["normal"] != 1 {
		t.Fatalf("expected normal urgency summary count, got %#v", report.SummaryEvidence.UrgencyCounts)
	}
}

func TestRunSmokeEvidenceReportOmitsBaseURLCredentials(t *testing.T) {
	server := newSuccessfulSmokeServer(t)
	defer server.Close()
	reportPath := filepath.Join(t.TempDir(), "evidence.json")
	baseURL := strings.Replace(server.URL, "http://", "http://user:secret@", 1)

	if err := runSmoke(smokeConfig{BaseURL: baseURL, Client: server.Client(), EvidenceReport: reportPath}); err != nil {
		t.Fatalf("runSmoke returned error: %v", err)
	}

	rawReport, err := os.ReadFile(reportPath)
	if err != nil {
		t.Fatalf("read evidence report: %v", err)
	}
	reportText := string(rawReport)
	if strings.Contains(reportText, "user:secret") || strings.Contains(reportText, "secret@") {
		t.Fatalf("evidence report leaked URL credentials: %s", reportText)
	}
	var report evidenceReport
	if err := json.Unmarshal(rawReport, &report); err != nil {
		t.Fatalf("decode evidence report: %v", err)
	}
	if strings.Contains(report.Target.BaseURL, "@") {
		t.Fatalf("expected sanitized target URL, got %q", report.Target.BaseURL)
	}
}

func TestRunSmokeAcceptsRedactionEnabledTicketFlow(t *testing.T) {
	server := newSuccessfulSmokeServer(t, true)
	defer server.Close()

	if err := runSmoke(smokeConfig{BaseURL: server.URL, Client: server.Client()}); err != nil {
		t.Fatalf("runSmoke returned error: %v", err)
	}
}

func TestWriteEvidenceReportRestrictsExistingFilePermissions(t *testing.T) {
	reportPath := filepath.Join(t.TempDir(), "evidence.json")
	if err := os.WriteFile(reportPath, []byte("{}\n"), 0o644); err != nil {
		t.Fatalf("seed report file: %v", err)
	}

	if err := writeEvidenceReport(reportPath, evidenceReport{ReportVersion: 1}); err != nil {
		t.Fatalf("write evidence report: %v", err)
	}

	info, err := os.Stat(reportPath)
	if err != nil {
		t.Fatalf("stat evidence report: %v", err)
	}
	if got := info.Mode().Perm(); got != 0o600 {
		t.Fatalf("expected evidence report mode 0600, got %o", got)
	}
}

func newSuccessfulSmokeServer(t *testing.T, redactionEnabled ...bool) *httptest.Server {
	t.Helper()
	var createdTicketID string
	var statusUpdated bool
	var readyChecked bool
	redacts := len(redactionEnabled) > 0 && redactionEnabled[0]
	return httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		switch {
		case r.Method == http.MethodGet && r.URL.Path == "/docs":
			readyChecked = true
			w.WriteHeader(http.StatusOK)
		case r.Method == http.MethodGet && r.URL.Path == "/facility/sovereignty":
			if !readyChecked {
				t.Fatal("sovereignty requested before readiness probe")
			}
			writeJSON(t, w, map[string]any{
				"mode":                  "local-demo",
				"data_residency_region": "local-dev",
				"storage_backend":       "sqlite-local",
				"pii_redaction_enabled": redacts,
				"audit_log_enabled":     true,
				"cloud_nim_allowed":     true,
				"runtime":               "local",
				"llm_provider":          "nvidia_nim",
				"asr_endpoint_type":     "cloud_nim",
				"tts_endpoint_type":     "cloud_nim",
				"llm_endpoint_type":     "cloud_nim",
				"api_key_configured":    true,
			})
		case r.Method == http.MethodPost && r.URL.Path == "/facility/tickets":
			createdTicketID = "FAC-000123"
			summary := "Parent email parent@example.edu and phone 555-123-4567 need follow up."
			transcriptSnippet := "Student ID S1234567A reported the issue."
			sensitivity := "standard"
			if redacts {
				summary = "Parent email [REDACTED_EMAIL] and phone [REDACTED_PHONE] need follow up."
				transcriptSnippet = "Student ID [REDACTED_STUDENT_ID] reported the issue."
				sensitivity = "redacted"
			}
			writeJSON(t, w, map[string]any{
				"ticket_id":          createdTicketID,
				"status":             "open",
				"summary":            summary,
				"transcript_snippet": transcriptSnippet,
				"sensitivity":        sensitivity,
				"redaction_applied":  redacts,
			})
		case r.Method == http.MethodPatch && r.URL.Path == "/facility/tickets/FAC-000123/status":
			statusUpdated = true
			writeJSON(t, w, map[string]any{
				"ticket_id": createdTicketID,
				"status":    "resolved",
			})
		case r.Method == http.MethodGet && r.URL.Path == "/facility/audit":
			if !statusUpdated {
				t.Fatal("audit requested before status update")
			}
			writeJSON(t, w, []map[string]any{
				{
					"event_type": "ticket_created",
					"ticket_id":  createdTicketID,
					"details": map[string]any{
						"redaction_applied": redacts,
					},
				},
				{
					"event_type": "ticket_status_updated",
					"ticket_id":  createdTicketID,
					"details": map[string]any{
						"status": "resolved",
					},
				},
			})
		case r.Method == http.MethodGet && r.URL.Path == "/facility/summary":
			if !statusUpdated {
				t.Fatal("summary requested before status update")
			}
			writeJSON(t, w, map[string]any{
				"total_tickets":    1,
				"open_tickets":     0,
				"status_counts":    map[string]int{"in_progress": 0, "open": 0, "resolved": 1},
				"category_counts":  map[string]int{"it": 1},
				"urgency_counts":   map[string]int{"normal": 1},
				"redacted_tickets": boolToInt(redacts),
				"audit_events":     2,
				"last_ticket_id":   createdTicketID,
			})
		default:
			http.NotFound(w, r)
		}
	}))
}

func boolToInt(value bool) int {
	if value {
		return 1
	}
	return 0
}

func writeJSON(t *testing.T, w http.ResponseWriter, value any) {
	t.Helper()
	if err := json.NewEncoder(w).Encode(value); err != nil {
		t.Fatalf("encode response: %v", err)
	}
}
