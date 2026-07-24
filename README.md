# AI Voice Call Platform

> An automated AI calling platform — replacing marketing staff, handling concurrent calls at scale, with conversations powered by a real human's cloned voice.

---

## Table of Contents

- [Overview](#overview)
- [Operating Model](#operating-model)
- [System Architecture](#system-architecture)
- [Tech Stack](#tech-stack)
- [VRAM & AI Pipeline](#vram--ai-pipeline)
- [Call Flow](#call-flow)
- [Core Features](#core-features)
- [Roadmap](#roadmap)
- [Operating Costs](#operating-costs)
- [Security](#security)
- [Risks & Mitigation](#risks--mitigation)

---

## Overview

AI Voice Call Platform is a B2B2C SaaS product that enables businesses to run automated outbound calling campaigns using an AI voice cloned from a real person. All conversation content is recorded, transcribed, and summarized, then returned to the business for follow-up actions.

**MVP target:** handle 5–8 concurrent calls, operating cost < $30/month, running on a personal GPU (RTX 4050 6 GB).

---

## Operating Model

```
Party A (platform provider)
  └── builds & operates the entire platform
        │
        ▼
Party B (business client)
  └── uploads internal documents, configures scripts, manages campaigns
        │
        ▼
Party C (end customer)
  └── receives calls from the AI, does not interact with the system directly
```

Each Party B is an **independent tenant** — data, knowledge base, and AI voice are fully isolated from one another.

---

## System Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Gateway & Auth Layer                                   │
│  FastAPI · JWT/OAuth2 · Rate Limiting                   │
└───────────────────────────┬─────────────────────────────┘
                            │
         ┌──────────────────┼──────────────────┐
         ▼                  ▼                  ▼
┌──────────────┐  ┌──────────────────┐  ┌─────────────────┐
│  Telephony   │  │  AI Orchestration│  │  RAG & Knowledge│
│  SIP Trunk   │  │  STT · LLM · TTS │  │  Qdrant · Embed │
│  FreeSWITCH  │  │  Dialogue Manager│  │  Doc Processor  │
└──────┬───────┘  └────────┬─────────┘  └────────┬────────┘
       │                   │                     │
       └───────────────────┼─────────────────────┘
                           ▼
         ┌─────────────────────────────────┐
         │  Data & Storage Layer           │
         │  PostgreSQL · MongoDB · Redis   │
         │  Object Storage (S3/local)      │
         └─────────────────┬───────────────┘
                           ▼
         ┌─────────────────────────────────┐
         │  Analytics & Report Layer       │
         │  Transcript · Summary · Webhook │
         └─────────────────────────────────┘
```

---

## Tech Stack

### AI / Voice

| Component | Technology | Notes |
|---|---|---|
| STT | **PhoWhisper small** | Pre-fine-tuned for Vietnamese, ~1.5 GB VRAM |
| LLM | **Qwen2.5-3B Q4\_K\_M** via `llama.cpp` | Strong Vietnamese support, ~2.0 GB VRAM, `--n-gpu-layers 999` |
| TTS / Voice cloning | **XTTS v2** (Coqui) | Clone from ~6s voice sample, ~1.2 GB VRAM |
| Embedding / RAG | **BGE-M3** | Multilingual, ~0.5 GB VRAM |

### Telephony

| Component | Technology | Notes |
|---|---|---|
| Media server | **FreeSWITCH** | Self-hosted, handles N concurrent SIP sessions |
| SIP trunk | **Twilio** (MVP) | ~$0.013/min to VN numbers; migrate to local carrier later |
| Audio bridge | `mod_audio_stream` / WebSocket | Pipes RTP → STT worker |

### Backend & Infrastructure

| Component | Technology |
|---|---|
| API | FastAPI (Python 3.11+) |
| Message queue | Redis Streams |
| Primary DB | PostgreSQL |
| Log / transcript DB | MongoDB |
| Vector DB | Qdrant (self-hosted) |
| File storage | Local or MinIO (MVP) → S3 (production) |
| Public exposure | **Cloudflare Tunnel** — free, no VPS required |
| Frontend | React + Vite + Zustand + React Query |

---

## VRAM & AI Pipeline

### VRAM Allocation (RTX 4050 6 GB)

```
┌─────────────────────────────────────────────────┐
│  RTX 4050 — 6 GB VRAM                          │
│                                                 │
│  ┌───────────────────┐  ┌──────────────────┐   │
│  │  PhoWhisper small │  │  Qwen2.5-3B Q4   │   │
│  │  STT  — ~1.5 GB   │  │  LLM  — ~2.0 GB  │   │
│  └───────────────────┘  └──────────────────┘   │
│                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────┐  │
│  │  XTTS v2     │  │  BGE-M3      │  │ Buf  │  │
│  │  TTS ~1.2 GB │  │  RAG ~0.5 GB │  │ 0.8G │  │
│  └──────────────┘  └──────────────┘  └──────┘  │
│                                                 │
│  ░░░░░░░░ Activation workspace (shared) ░░░░░░  │
│           ~0.3–0.6 GB temporarily per inference │
└─────────────────────────────────────────────────┘
Resident footprint ≈ 5.2 GB   Buffer + activation: 0.8 GB
```

### Serial Inference Strategy

All 4 models are **permanently resident** in VRAM at server startup (no hot-swapping). Inference runs **sequentially** in order:

```
audio chunk (1.5s)
      │
      ▼
[STT — 0.4s] ──► text
                   │
                   ▼
             [RAG query — 0.1s] ──► context docs
                                        │
                                        ▼
                                  [LLM — 0.8s] ──► response text
                                                        │
                                                        ▼
                                                  [TTS — 0.6s] ──► audio
                                                                      │
                                                                      ▼
                                                             played to Party C
```

**Estimated latency per turn:** ~1.8–2.5 seconds

**Concurrency:** FreeSWITCH handles N SIP sessions in parallel using CPU. The GPU queue processes inference in priority order. With 5–8 concurrent calls, the maximum wait time is ~4 seconds per call — acceptable for natural conversation.

### Key VRAM Optimization Tips

```bash
# Qwen2.5-3B: run entirely on GPU, no RAM offload
llama-server --model qwen2.5-3b-q4_k_m.gguf --n-gpu-layers 999

# PhoWhisper: use float16 instead of float32
model = WhisperModel("PhoWhisper-small", compute_type="float16")

# XTTS v2: load once at startup, keep resident in VRAM
tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to("cuda")
```

---

## Call Flow

```
Campaign Engine
      │  (fetch phone number list)
      ▼
Call Queue (Redis)
      │
      ▼
Dialer Service
      │  (dial out via SIP)
      ▼
SIP Trunk (Twilio) ◄──────────────────────────────┐
      │                                            │
      │  Party C answers                          │ audio playback
      ▼                                            │
FreeSWITCH Media Server ──────────────────────────►│
  • receive RTP stream                            TTS Engine (XTTS v2)
  • chunk into 1.5s segments                           ▲
  • record full audio                                  │ response text
      │                                                │
      ▼                                          LLM Inference (Qwen2.5)
STT Worker (PhoWhisper)                                ▲
      │ text                                           │ text + context
      ▼                                                │
Dialogue Manager ──────────────────────────────► RAG Query (Qdrant)
  • script state machine
  • intent detection
  • branch decision
      │
      │  (call ends)
      ▼
Post-call Processing
  • Summary Engine summarizes
  • result classification
  • save to PostgreSQL + MongoDB
      │
      ├──► Party B Dashboard (transcript + summary)
      └──► Webhook / CRM push
```

### Detected Intents During a Call

| Intent | AI Action |
|---|---|
| Interested, wants to know more | Continue script, provide information from RAG |
| Not interested | Politely end call, flag `not_interested` |
| Wants a callback | Record preferred time, flag `callback_requested` |
| Requests a human agent | Politely end call, flag `needs_human` |
| Extended silence | Repeat question; after 2 attempts → end call |

---

## Core Features

### Knowledge Base Module (self-configured by Party B)

- Upload internal documents: PDF, DOCX, XLSX, TXT (up to 100 MB/file)
- Auto pipeline: chunk → embed → upsert into tenant-specific Qdrant namespace
- **Chat preview** UI to test the chatbot before launching a campaign
- Document versioning: updates/deletions do not affect calls already in progress

### Campaign Module

- Create campaign: upload number list (CSV/Excel), set schedule, choose script
- Smart scheduling: calling hours window, automatic retry on no answer
- Real-time monitoring: active call count, per-call status, reach rate
- Stop / pause / resume at any time
- DNC list: do-not-call numbers automatically excluded from campaigns

### Reporting Module

- Full transcript: AI vs Party C speech labeled separately, timestamp per segment
- AI summary: key highlights, customer reactions, collected information
- Automatic result classification by detected intent
- Export: CSV, Excel, PDF
- Webhook API to push results to Party B's CRM

---

## Roadmap

### Phase 0 — Foundation *(Month 1–2)*

- [x] ERD design, API contract, repo structure
- [x] FastAPI skeleton + JWT auth + tenant management
- [x] PostgreSQL + MongoDB + Redis local setup
- [x] CI/CD pipeline (GitHub Actions)
- [x] Cloudflare Tunnel to expose dev server

### Phase 1 — Core Call Engine *(Month 3–4)*

- [ ] FreeSWITCH installation + `mod_audio_stream` configuration
- [ ] Twilio SIP trunk connection
- [ ] PhoWhisper STT worker (WebSocket streaming)
- [ ] XTTS v2 server + voice cloning from sample audio
- [ ] Qwen2.5-3B via `llama.cpp` server
- [ ] Basic Dialogue Manager state machine
- [ ] **Milestone:** complete one end-to-end AI call

### Phase 2 — Knowledge Base & RAG *(Month 5–6)*

- [ ] Document processor pipeline (chunk + embed + upsert Qdrant)
- [ ] BGE-M3 embedding service
- [ ] RAG injection into LLM context
- [ ] Chat preview UI for Party B testing
- [ ] Document version management
- [ ] **Milestone:** Party B can self-configure AI from their own documents

### Phase 3 — Campaign & Dashboard *(Month 7–8)*

- [ ] Campaign management UI (3-step wizard)
- [ ] Call queue + dialer service (Redis Streams)
- [ ] Handle 5–8 concurrent calls
- [ ] Real-time monitoring (WebSocket)
- [ ] Post-call summary + intent classification
- [ ] CSV/Excel report export
- [ ] **Milestone:** MVP ready for real pilot with Party B

### Phase 4 — Enterprise Ready *(Month 9–10)*

- [ ] Webhook API for CRM integration
- [ ] Full audit log of all Party B actions
- [ ] Fully mobile-responsive UI
- [ ] Upgrade to Qwen2.5-7B Q4 (partial RAM offload)
- [ ] Advanced analytics dashboard
- [ ] **Milestone:** product ready for commercialization

### Phase 5 — Scale *(Month 11–12)*

- [ ] Migrate infrastructure to cloud (hourly GPU instances)
- [ ] Scale to 20–50 concurrent calls
- [ ] Strict multi-tenant isolation at DB layer
- [ ] SLA monitoring + alerting
- [ ] **Milestone:** stable support for multiple Party B tenants simultaneously

---

## Operating Costs

### MVP — personal machine (RTX 4050)

| Item | Est. / month | Notes |
|---|---|---|
| Electricity (GPU ~8h/day) | ~$5–10 | Depends on local power rate |
| SIP Trunk (Twilio, ~500 min) | ~$7–15 | ~$0.013/min to VN numbers |
| Domain + SSL | ~$1–2 | Namecheap or Cloudflare |
| Cloudflare Tunnel | $0 | Free |
| All AI (STT, LLM, TTS, RAG) | $0 | Self-hosted on personal GPU |
| **Total** | **~$13–27/month** | |

### Scale — when revenue allows (GPU cloud)

| Item | Est. / month | Notes |
|---|---|---|
| GPU instance (Lambda Labs A10) | ~$80–150 | Only on during campaigns |
| SIP Trunk (local VN carrier) | ~$30–60 | ~3–5x cheaper than Twilio |
| CPU VPS (backend, DB) | ~$20–40 | Hetzner or DigitalOcean |
| Storage | ~$5–10 | Cloudflare R2 or Backblaze |
| **Total** | **~$135–260/month** | Supports 20–50 concurrent calls |

---

## Security

### Tenant Isolation

```
Party B (tenant_id: abc123)
  ├── PostgreSQL: dedicated schema
  ├── MongoDB: namespaced collection prefix
  ├── Qdrant: dedicated namespace
  └── Object storage: dedicated key prefix
```

### Key Measures

- **Encryption at rest:** AES-256 for all stored files
- **Encryption in transit:** TLS 1.3 for HTTP, SRTP for media audio
- **Auth:** OAuth2 + JWT (access token 15 min, refresh token 7 days)
- **MFA:** mandatory for Party B Admin accounts
- **Audit log:** every action recorded (who did what, when)
- **Party B document data:** used only within that tenant's RAG, never for model training

### Legal Compliance (Vietnam)

- Compliant with Decree 13/2023/ND-CP on personal data protection
- AI automatically announces recording at the start of every call
- DNC List automatically excludes opted-out numbers
- Calls made only within permitted hours (default 8:00–20:00)

---

## Risks & Mitigation

| Risk | Severity | Mitigation |
|---|---|---|
| AI latency disrupts conversation flow | High | Serial pipeline + 1.5s STT chunks; target < 2.5s/turn |
| Low STT accuracy for Vietnamese (accents, noise) | High | PhoWhisper fine-tuning; fallback silence handling |
| VRAM insufficient under concurrent load | Medium | Permanent resident load + serial inference; monitor `nvidia-smi` |
| Violation of calling/spam regulations | High | DNC list; rate limiting; recording notice; binding Party B terms |
| Voice cloning misuse | Medium | Clone only with explicit consent; strict terms of service |
| SIP trunk blocked or low answer rate | Medium | Retry logic; track answer rate stats to tune campaigns |
| Personal machine goes offline, SLA loss | Low (MVP) | Schedule campaigns in fixed hours; alert on connectivity loss |

---

## Repository Structure (planned)

```
ai-voice-call-platform/
├── backend/
│   ├── app/
│   │   ├── api/          # FastAPI routers
│   │   ├── core/         # config, auth, deps
│   │   ├── models/       # SQLAlchemy + Beanie models
│   │   ├── services/
│   │   │   ├── stt/      # PhoWhisper worker
│   │   │   ├── llm/      # llama.cpp client
│   │   │   ├── tts/      # XTTS v2 server
│   │   │   ├── rag/      # Qdrant + BGE-M3
│   │   │   ├── dialogue/ # state machine
│   │   │   └── telephony/# FreeSWITCH bridge
│   │   └── tasks/        # post-call processing
│   └── tests/
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   ├── components/
│   │   ├── stores/       # Zustand
│   │   └── api/          # React Query hooks
│   └── public/
├── freeswitch/
│   └── conf/             # ESL config, dialplan
├── infra/
│   ├── docker-compose.yml
│   └── cloudflare/       # tunnel config
└── docs/
    └── api/              # OpenAPI spec
```

---

*Internal document — last updated: 07/2026*
