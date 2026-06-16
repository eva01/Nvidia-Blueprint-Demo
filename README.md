# School Facility Voice Support Demo

This project adapts NVIDIA's Nemotron Voice Agent blueprint into a school facility support and issue-tracking demo.

The demo lets a user report a facility problem through a browser microphone, turns the conversation into a structured support ticket, stores tickets in local SQLite, and gives an operator a simple browser dashboard to review and open or close tickets.

## What It Shows

- Voice intake using NVIDIA ASR, LLM, and TTS services through the existing WebRTC voice agent pipeline.
- School knowledge-base retrieval with a fuzzy fallback and optional sqlite-vec semantic search.
- A school facility support prompt that collects category, location, urgency, reporter, and issue summary.
- Local ticket persistence with SQLite.
- A dashboard-first browser UI for reviewing tickets before entering the voice agent.
- Local audit and summary endpoints for demo evidence.
- A functional-first configuration that preserves contact details by default; optional redaction can be enabled later with `PII_REDACTION_ENABLED=true`.

## NVIDIA Stack

The current demo uses NVIDIA as the voice and reasoning layer while keeping school operations data local.

| Layer | Current demo | Notes |
| --- | --- | --- |
| Voice input | NVIDIA Riva / Parakeet ASR through cloud NIM | Browser microphone audio is transcribed before ticket intake or KB lookup. |
| Conversation reasoning | `nvidia/nemotron-3-nano-30b-a3b` through NVIDIA NIM | Drives the school facility support prompt and knowledge-grounded answers. |
| Voice output | NVIDIA Riva / Magpie TTS through cloud NIM | Spoken responses are streamed back to the browser. |
| RAG embedding | `nvidia/llama-nemotron-embed-vl-1b-v2` when `SCHOOL_KNOWLEDGE_BACKEND=sqlite-vec` | School KB chunks stay local; only text for embedding is sent to NVIDIA. |
| RAG reranking | `nvidia/llama-nemotron-rerank-vl-1b-v2` when `ENABLE_NVIDIA_RERANK=true` | Optional because free accounts may not have rerank capacity. |
| Local retrieval store | SQLite plus `sqlite-vec`, or FAISS with `SCHOOL_KNOWLEDGE_BACKEND=faiss` | Vectors, tickets, audit records, and KB markdown remain on the machine. |
| Voice orchestration | NVIDIA Pipecat blueprint pipeline | WebRTC connects browser audio, ASR, RAG context injection, LLM, ticket creation, and TTS. |
| Document extraction | Future: Nemotron Parse / OCR | Not wired into this version. Current ingestion uses YAML and Markdown school KB files. |
| Safety guardrails | `nvidia/llama-3.1-nemotron-safety-guard-8b-v3` when `ENABLE_NVIDIA_SAFETY_GUARD=true` | Optional output filtering before TTS, disabled by default for free-account safety. |

## High-Level Flow

```text
Browser microphone
  -> WebRTC voice pipeline
  -> NVIDIA ASR / LLM / TTS
  -> school KB retrieval
  -> ticket marker
  -> SQLite ticket store
  -> operator dashboard
```

With sqlite-vec RAG enabled:

```text
School YAML / Markdown KB
  -> NVIDIA Embed
  -> local sqlite-vec index
  -> optional NVIDIA Rerank
  -> retrieved context
  -> Nemotron LLM spoken answer
```

With FAISS RAG enabled, replace the local vector index step with:

```text
SCHOOL_KNOWLEDGE_BACKEND=faiss
SCHOOL_FAISS_INDEX_PATH=./data/school_knowledge.faiss
```

## Run Locally

Create a local `.env` from the cloud example and add your NVIDIA API key:

```bash
cp config/env.cloud.example .env
npm --prefix frontend/webrtc_ui ci
```

Start the demo:

```bash
./demo
```

Open the browser UI:

```text
http://127.0.0.1:9000/
```

The first screen is the ticket dashboard. Use **Voice agent** or **Voice intake** to start the microphone flow.

To test the sqlite-vec RAG path:

```bash
SCHOOL_KNOWLEDGE_BACKEND=sqlite-vec \
SCHOOL_KNOWLEDGE_MARKDOWN_DIR=docs/school_kb \
ENABLE_NVIDIA_RERANK=false \
./demo
```

To test the FAISS RAG path:

```bash
SCHOOL_KNOWLEDGE_BACKEND=faiss \
SCHOOL_KNOWLEDGE_MARKDOWN_DIR=docs/school_kb \
ENABLE_NVIDIA_RERANK=false \
./demo
```

To enable NVIDIA Safety Guard output filtering:

```bash
ENABLE_NVIDIA_SAFETY_GUARD=true ./demo
```

## Useful Local Endpoints

```text
GET /facility/summary
GET /facility/tickets
GET /facility/audit
GET /facility/sovereignty
GET /facility/knowledge/search?q=visitor
```

Nemotron Parse is a planned future ingestion path for scanned PDFs, forms, tables, and charts. Documents are not automatically parsed by Nemotron Parse in this version.

Default backend:

```text
http://127.0.0.1:7860
```

## Jetson Orin 16GB Profile

This codebase is shaped so the same school facility workflow can be demonstrated on a Jetson Orin 16GB class device, especially Jetson Orin NX 16GB. Treat Orin 16GB as an edge deployment target, not as a replacement for every large hosted NIM in the current Mac demo.

Recommended Orin 16GB split:

```text
Runs on Orin 16GB:
  -> FastAPI backend
  -> WebRTC UI
  -> SQLite ticket store
  -> sqlite-vec or FAISS school KB index
  -> Markdown/YAML knowledge ingestion
  -> optional small local LLM endpoint from config/env.jetson.example

Can stay on NVIDIA cloud NIM:
  -> large Nemotron LLM
  -> Nemotron Embed / Rerank
  -> Riva ASR / TTS if local speech services are not deployed
```

Why this is realistic:

- Orin 16GB has enough memory for the app, local database, vector index, and a small quantized local model profile.
- The repository already includes `config/env.jetson.example` with a local OpenAI-compatible LLM endpoint shape, `NVIDIA_LLM_URL=http://localhost:9000/v1`.
- Heavy models such as `nemotron-3-nano-30b-a3b`, multimodal Embed/Rerank, and future Parse are better treated as hosted NIM calls unless a larger NVIDIA GPU target is available.
- The sovereignty story still holds because operational data, tickets, audit records, and vector storage stay on the edge device; cloud calls can be limited to inference.

Orin 16GB interview framing:

> On a Jetson Orin 16GB deployment, I would run the school support application, SQLite ticket store, and sqlite-vec retrieval index locally at the edge. For the first production cut, I would keep large Nemotron reasoning, embedding, reranking, and speech services on NVIDIA NIM endpoints. If the site requires offline mode, I would switch the LLM to a smaller quantized local endpoint and keep cloud RAG models as optional accelerators.

## Smoke Test

With the backend running:

```bash
./demo smoke
```

For a no-key local operator API check:

```bash
./demo operator --dry-run
```

## More Detail

- [School facility voice tickets](docs/how-to/school-facility-voice-tickets.md)
- [Pipeline performance tuning](docs/how-to/tune-pipeline-performance.md)
- [NVIDIA Pipecat overview](docs/05-nvidia-pipecat.md)

## License

This project is based on the NVIDIA Nemotron Voice Agent blueprint and keeps the upstream BSD 2-Clause licensing. See [LICENSE](LICENSE) and [third_party_oss_license.txt](third_party_oss_license.txt).
