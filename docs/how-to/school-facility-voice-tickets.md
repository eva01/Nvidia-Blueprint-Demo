# School Facility Voice Tickets

This scaffold adapts the WebRTC browser microphone demo into a school facility support intake flow with local SQLite ticket storage.

## What This Includes

- Dashboard-first operator review with browser microphone voice intake.
- A school facilities prompt at `nemotron-3-nano/school_facility_support`.
- Local SQLite ticket storage.
- Optional school knowledge retrieval using sqlite-vec or FAISS with NVIDIA hosted Embed/Rerank.
- HTTP endpoints for creating, inspecting, and summarizing tickets.

The browser UI opens to the ticket dashboard first. Operators can switch to voice intake from there.

## Configure

Use the cloud demo environment file for the browser microphone demo:

```bash
cp config/env.cloud.example .env
${EDITOR:-nano} .env
npm --prefix frontend/webrtc_ui ci
python3 scripts/check_cloud_nim_config.py --env-file .env
./demo
```

`config/env.example` is the fuller Docker/local-NIM oriented template. For this quick demo, prefer `config/env.cloud.example`.

It is safe to keep the API key in your local root `.env` because `.env` and `.env.*` are ignored by Git. Do not paste keys into committed example files, docs, source code, Beads notes, or shell history. If a key was shared in chat or logs, rotate it before using the demo long term.

## School Knowledge RAG

The default knowledge mode uses the configured YAML school KB with local fuzzy search, so the demo runs without extra retrieval API calls:

```text
SCHOOL_KNOWLEDGE_BACKEND=fuzzy
```

To try NVIDIA hosted embeddings with local sqlite-vec storage:

```text
SCHOOL_KNOWLEDGE_BACKEND=sqlite-vec
SCHOOL_VECTOR_DB_PATH=./data/school_knowledge_vectors.db
NVIDIA_EMBED_MODEL=nvidia/llama-nemotron-embed-vl-1b-v2
ENABLE_NVIDIA_RERANK=false
```

Set `ENABLE_NVIDIA_RERANK=true` only when your NVIDIA Build account has access to the rerank endpoint.

To use FAISS instead of sqlite-vec:

```text
SCHOOL_KNOWLEDGE_BACKEND=faiss
SCHOOL_FAISS_INDEX_PATH=./data/school_knowledge.faiss
```

To add NVIDIA Safety Guard output filtering before TTS:

```text
ENABLE_NVIDIA_SAFETY_GUARD=true
NVIDIA_SAFETY_MODEL=nvidia/llama-3.1-nemotron-safety-guard-8b-v3
```

Quick search check:

```bash
curl 'http://localhost:7860/facility/knowledge/search?q=where%20do%20visitors%20register'
```

Nemotron Parse is a planned future ingestion path for scanned PDFs, forms, tables, and charts. Documents are not automatically parsed by Nemotron Parse in this version.

## Browser Microphone Demo

Start the WebRTC application, then open the dashboard-first UI at `http://127.0.0.1:9000/`.

For fixed-answer questions, the UI shows quick-reply chips. Category questions show the allowed facility categories, and urgency questions show low, normal, and urgent. Click a chip when you want to answer without using the microphone.

The voice agent should begin with:

```text
School facilities support. What issue should I report?
```

Example intake:

```text
User: The air conditioner in classroom 3A is leaking near a plug.
Agent: Is classroom 3A the exact location?
User: Yes.
Agent: Who should I list as the reporter?
User: Ms Tan.
Agent: Ticket FAC-000001 created for an urgent hvac issue in Classroom 3A.
```

## Ticket API

Create a ticket for demo verification:

```bash
curl -X POST http://localhost:7860/facility/tickets \
  -H 'Content-Type: application/json' \
  -d '{
    "category": "hvac",
    "location": "Classroom 3A",
    "summary": "Air conditioner is leaking near an electrical plug.",
    "urgency": "urgent",
    "reporter": "Ms Tan",
    "transcript_snippet": "The air conditioner in classroom 3A is leaking near a plug."
  }'
```

List tickets:

```bash
curl http://localhost:7860/facility/tickets
```

Inspect one ticket:

```bash
curl http://localhost:7860/facility/tickets/FAC-000001
```

Update ticket status:

```bash
curl -X PATCH http://localhost:7860/facility/tickets/FAC-000001/status \
  -H 'Content-Type: application/json' \
  -d '{"status": "in_progress"}'
```

## Sovereign AI Demo Evidence

This local demo includes a small governance layer for enterprise and sovereign AI conversations:

- Tickets are stored locally in SQLite at `FACILITY_TICKETS_DB_PATH`.
- Email addresses, phone numbers, and student-style IDs are preserved by default for the functional demo.
- Optional redaction can be re-enabled later with `PII_REDACTION_ENABLED=true`.
- Ticket creation and status updates create local audit events.
- `/facility/sovereignty` reports secret-safe policy state, including whether hosted cloud NIM is explicitly allowed.

Check the policy state:

```bash
curl http://localhost:7860/facility/sovereignty
```

Create a ticket with contact details to verify the functional ticket path:

```bash
curl -X POST http://localhost:7860/facility/tickets \
  -H 'Content-Type: application/json' \
  -d '{
    "category": "it",
    "location": "Library counter",
    "summary": "Parent email parent@example.edu and phone 555-123-4567 need follow up.",
    "urgency": "normal",
    "reporter": "office",
    "transcript_snippet": "Student ID S1234567A reported the issue."
  }'
```

The response should include `sensitivity: "standard"`, `redaction_applied: false`, and the original email, phone number, and student ID values.

Inspect the local audit trail:

```bash
curl http://localhost:7860/facility/audit
```

## Go Smoke Tester

After the backend is running, use the local Go smoke tester to exercise the sovereign demo path without Chrome:

```bash
./demo smoke
```

Write a portable smoke evidence report for the same run:

```bash
./demo smoke --evidence-report evidence/facility-sovereign-smoke.json
```

That shortcut runs:

```bash
go run ./cmd/facility-smoke
```

The default backend URL is `http://127.0.0.1:7860`. Override it when using a different local port:

```bash
FACILITY_BACKEND_URL=http://127.0.0.1:8787 ./demo smoke
```

`./demo smoke` also honors `VOICE_BACKEND_PORT`, so it targets the same local backend port as `./demo` when you set one:

```bash
VOICE_BACKEND_PORT=8787 ./demo smoke
```

You can also set the same local URL with `FACILITY_BACKEND_URL`:

```bash
FACILITY_BACKEND_URL=http://127.0.0.1:8787 go run ./cmd/facility-smoke
```

The smoke tester checks `/docs` readiness, reads `/facility/sovereignty`, creates a ticket containing sample contact details, confirms the details are preserved, updates the ticket status, verifies `ticket_created` plus `ticket_status_updated` audit events, and reads `/facility/summary` aggregate operations metrics. It does not require or print `NVIDIA_API_KEY`, but it does create a real ticket in the configured local SQLite database.
It rejects non-local backend URLs so it is not accidentally used against a deployed environment.
The evidence report is secret-safe smoke evidence, not a compliance certification. It records policy state, ticket-detail preservation, ticket ID, status transition, required audit event checks, and aggregate summary counts without raw ticket text, transcript snippets, NVIDIA API keys, or audit details.

## No-Key Operator Demo

Use the operator runner when you want a local ticket API demo without configuring `NVIDIA_API_KEY`:

```bash
./demo operator --evidence-report evidence/local-operator.json
```

The command starts the local Python backend on `http://127.0.0.1:7860`, uses a temporary SQLite database under `${TMPDIR:-/tmp}` unless `--db-path` is provided, waits for `/docs`, runs the sovereign smoke checks, and prints the operator URLs for sovereignty, summary, tickets, and audit inspection.

Preview the exact backend and smoke commands without starting the backend:

```bash
./demo operator --dry-run
```

Use a different local port or persistent SQLite database when needed:

```bash
./demo operator --port 8787 --db-path ./data/local-operator.db --timeout 5s
```

## Local Verification

This repository does not include GitHub Actions workflows. Run verification locally before pushing changes to avoid hosted CI minutes:

```bash
uv run ruff check .
uv run python -m unittest discover -s tests -v
go test ./...
npm --prefix frontend/webrtc_ui run lint
npm --prefix frontend/webrtc_ui run test:quick-replies
npm --prefix frontend/webrtc_ui run test:config
npm --prefix frontend/webrtc_ui run test:facility-tickets
npm --prefix frontend/webrtc_ui run build
npm --prefix cloudflare/facility-ticket-worker test
bash -n demo scripts/run_cloud_demo.sh scripts/check_cloud_nim_config.py
```

## Operator Handoff

The local browser UI opens to an operator dashboard first. Use it to review tickets, filter by status, and mark tickets open or closed before switching into the voice agent view.

Local operator API:

```text
GET /facility/sovereignty
GET /facility/summary
GET /facility/tickets
GET /facility/audit
```

`/facility/summary` returns aggregate counts for ticket totals, open tickets, status/category/urgency breakdowns, redacted-ticket count, audit events, the latest ticket ID, and the current sovereignty policy. It is designed for demos and dashboards, so it omits raw summaries, reporters, transcript snippets, and audit details.

Cloudflare operator API:

```text
https://nvidia-blueprint-facility-tickets.wemaker.workers.dev
```

The local Python API stores tickets in SQLite at `FACILITY_TICKETS_DB_PATH`. The Cloudflare API stores operator tickets in D1. Keep runtime files such as `.env`, `data/`, SQLite databases, audio dumps, and caches out of Git.

## Automatic Ticket Creation

When `ENABLE_FACILITY_TICKET_AUTOCREATE=true`, the LLM emits a strict internal marker after it has all required fields. The pipeline intercepts that marker before TTS, writes the ticket to SQLite, and replaces the marker with a spoken confirmation containing the generated ticket ID.

## Cloud NIM Preflight

Run the preflight before starting Docker Compose:

```bash
python3 scripts/check_cloud_nim_config.py --env-file .env
```

After adding `NVIDIA_API_KEY` to `.env`, you can also verify visible ASR and TTS cloud functions:

```bash
python3 scripts/check_cloud_nim_config.py --env-file .env --resolve-functions
```

The preflight masks secret values in output. It checks the WebRTC transport, school facility prompt selector, cloud ASR/TTS/LLM endpoints, prompt catalog, and writable SQLite ticket path.
It also reports the sovereign mode, data residency label, optional redaction setting, audit logging, and explicit cloud NIM allowance.
