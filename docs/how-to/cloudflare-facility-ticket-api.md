# Cloudflare Facility Ticket API

This Worker deploys the school facility ticket operator surface to Cloudflare Workers with D1 storage.

It does not replace the Python WebRTC voice backend. The voice agent still needs a Python runtime for Pipecat/WebRTC and NVIDIA ASR/TTS/LLM calls. Cloudflare hosts the ticket API and operator landing page.

## Endpoints

```text
GET    /
GET    /health
POST   /facility/tickets
GET    /facility/tickets
GET    /facility/tickets/FAC-000001
PATCH  /facility/tickets/FAC-000001/status
```

## Deploy

From `cloudflare/facility-ticket-worker`:

```bash
wrangler d1 create nvidia-blueprint-facility-tickets
```

Copy the returned `database_id` into `wrangler.jsonc`, then run:

```bash
wrangler d1 migrations apply nvidia-blueprint-facility-tickets --remote --config wrangler.jsonc
wrangler deploy --config wrangler.jsonc
```

Current deployment:

```text
Worker URL: https://nvidia-blueprint-facility-tickets.wemaker.workers.dev
D1 database: nvidia-blueprint-facility-tickets
D1 database_id: f5acc479-7c19-4bc2-bc01-754a67f41d0c
```

## Smoke Test

```bash
curl https://nvidia-blueprint-facility-tickets.wemaker.workers.dev/health

curl -X POST https://nvidia-blueprint-facility-tickets.wemaker.workers.dev/facility/tickets \
  -H 'Content-Type: application/json' \
  -d '{
    "category": "hvac",
    "location": "Classroom 3A",
    "summary": "Air conditioner leaking near an electrical plug.",
    "urgency": "urgent",
    "reporter": "Ms Tan",
    "transcript_snippet": "The air conditioner in classroom 3A is leaking near a plug."
  }'
```
