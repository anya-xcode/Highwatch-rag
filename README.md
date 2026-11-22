# Highwatch RAG

Ask questions about your Google Drive files and uploaded documents. Every answer cites its sources, and when your documents don't contain the answer, the app says so.

- **Ingestion:** PDF, DOCX, TXT and Markdown, from upload or Google Drive (incremental sync)
- **Retrieval:** local embeddings ([FastEmbed](https://github.com/qdrant/fastembed), `BAAI/bge-small-en-v1.5`) + [FAISS](https://github.com/facebookresearch/faiss) exact cosine search
- **Answers:** Groq free plan (default), Gemini via Google AI Studio free tier (optional), or **extractive** mode with no LLM at all
- **Persistence:** local disk / Docker volume by default; optional private Google Cloud Storage mirror for Cloud Run

> **Budget: $0.** The default setup (local Python or Docker + Groq free plan + local embeddings) uses no paid service and needs no cloud billing account. Some optional paths below (Cloud Run, Cloud Storage, Secret Manager) **require a Google Cloud billing account, and usage beyond free limits is billed** — read [Cost and billing warnings](#cost-and-billing-warnings) before enabling them. Nothing in this repository creates cloud resources by itself.

---

## Contents

1. [Architecture](#architecture)
2. [Quick start (local Python)](#quick-start-local-python)
3. [Docker](#docker)
4. [Configuration](#configuration)
5. [Google Drive setup](#google-drive-setup)
6. [API](#api)
7. [Testing](#testing)
8. [Free deployment options](#free-deployment-options)
9. [Google Cloud integrations (optional, learning path)](#google-cloud-integrations-optional-learning-path)
10. [Cost and billing warnings](#cost-and-billing-warnings)
11. [Cleanup](#cleanup)
12. [Upgrading from v1](#upgrading-from-v1)
13. [Troubleshooting](#troubleshooting)

---

## Architecture

```
 Google Drive ──OAuth (read-only)──► connectors/gdrive.py ──► storage/downloads/
 Browser upload ──POST /upload──► validation (type, size, content, duplicates) ──► storage/uploads/
                                         │
                         processing/parser.py     PDF (per page) · DOCX (headings, tables) · TXT/MD
                                         ▼
                         processing/chunker.py    paragraph/section/page-aware chunks with overlap
                                         ▼
                         embedding/embedder.py    FastEmbed, local CPU (passage vs. query embeddings)
                                         ▼
                         search/vector_store.py   FAISS IndexFlatIP + metadata + manifest (atomic saves)
                         processing/registry.py   per-document status, hash, stored original
                                         ▼
 POST /ask ─► embed query ─► top-k above threshold ─► api/llm_service.py ─► answer + [n] citations
                                  │ nothing relevant                │ model says INSUFFICIENT_CONTEXT
                                  └──────► "not in your documents" ◄┘
```

| Module | Responsibility |
|---|---|
| `main.py` | FastAPI app, startup (restore → load → register legacy docs → optional Drive sync), request logging |
| `api/routes.py` | HTTP endpoints, upload validation, citation building |
| `api/llm_service.py` | Provider calls (Groq / Gemini / extractive), prompt, citation & insufficient-context parsing |
| `api/dependencies.py` | Shared services, optional `X-API-Key` check |
| `connectors/gdrive.py` | OAuth, listing, streaming downloads, two-phase sync state |
| `processing/` | Parser, chunker, validation, document registry, ingestion pipeline |
| `embedding/embedder.py` | FastEmbed wrapper with cache |
| `search/vector_store.py` | FAISS index with crash-safe persistence and consistency checks |
| `persistence/` | Atomic file writes; `local` (default) or `gcs` mirror backend |
| `config/` | Environment-based settings, logging (console or Cloud Logging JSON) |
| `frontend/` | Static HTML/CSS/JS UI served by FastAPI (no build step) |

**What is stored where** (`STORAGE_DIR`, default `./storage`):

| File | Contents |
|---|---|
| `faiss_index.bin` | Vectors |
| `faiss_index_metadata.json` | Chunk text + metadata (one entry per vector) |
| `faiss_index_manifest.json` | Embedding model, dimension, vector count |
| `documents.json` | Document registry (status, hash, stored path, Drive link) |
| `sync_state.json` | Google Drive sync state |
| `uploads/`, `downloads/` | Original files (used by `POST /reindex`) |

All writes are atomic (temp file + rename). On startup, inconsistent or incompatible index files (e.g. a crash mid-save, or a changed `EMBEDDING_MODEL`) are **moved aside, never deleted**, and `POST /reindex` rebuilds the index from the stored originals.

---

## Quick start (local Python)

Requires Python 3.12+ (tested on 3.13; the pinned NumPy needs 3.12+).

```bash
git clone https://github.com/anya-xcode/Highwatch-rag.git
cd Highwatch-rag

python -m venv .venv
# Windows:  .venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env          # Windows: copy .env.example .env
```

Edit `.env` and set `GROQ_API_KEY` (free key from <https://console.groq.com/keys>), or set `LLM_PROVIDER=extractive` to run with no LLM at all.

```bash
python main.py
```

Open <http://localhost:8000> (UI) or <http://localhost:8000/docs> (API docs). The embedding model (~70 MB) downloads from Hugging Face on first use.

---

## Docker

Docker Compose keeps your data in a named volume, so it survives restarts and rebuilds.

```bash
cp .env.example .env          # add GROQ_API_KEY
mkdir -p secrets              # optional: put credentials.json / token.json here for Drive
docker compose up --build
```

- App: <http://localhost:8000> (bound to 127.0.0.1 only)
- Logs: `docker compose logs -f`
- Stop: `docker compose down` (data kept) · Delete data too: `docker compose down -v`

Without Compose:

```bash
docker build -t highwatch-rag .
docker run --rm -p 127.0.0.1:8000:8000 --env-file .env \
  -v highwatch-storage:/app/storage \
  -v "$(pwd)/secrets:/app/secrets" \
  -e GOOGLE_CREDENTIALS_PATH=/app/secrets/credentials.json \
  -e GOOGLE_TOKEN_PATH=/app/secrets/token.json \
  highwatch-rag
```

Image details: Python 3.13 slim, runs as a non-root user, embedding model baked in (no download at cold start), honors `$PORT`, health check fails on any non-2xx response. `.dockerignore` keeps `.env`, `credentials.json`, `token.json`, `secrets/` and `storage/` out of the image.

---

## Configuration

All settings are environment variables (or `.env`). See [.env.example](.env.example) for the full list. The important ones:

| Variable | Default | Notes |
|---|---|---|
| `LLM_PROVIDER` | `groq` | `groq`, `gemini` or `extractive`. Paid-only providers (e.g. `openai`) are **rejected at startup**. |
| `GROQ_API_KEY` | – | Free plan key. Without it, answers fall back to excerpts with a visible warning. |
| `GROQ_MODEL` | `openai/gpt-oss-120b` | Groq shut down `llama-3.1-70b-versatile` (2025-01-24) and lists `llama-3.3-70b-versatile` as shut down for free/developer tiers on 2026-08-16. |
| `GEMINI_API_KEY` / `GEMINI_MODEL` | – / `gemini-3.5-flash-lite` | AI Studio key from a project **without billing**. See data-use warning below. |
| `EMBEDDING_MODEL` | `BAAI/bge-small-en-v1.5` | Changing it requires `POST /reindex`. |
| `SIMILARITY_THRESHOLD` | `0.55` | Minimum cosine similarity for "relevant". Measured with bge-small: related questions ≥ 0.685, unrelated ≤ 0.44. Pinned by an integration test. |
| `EMBEDDING_QUERY_PREFIX` | auto | BGE's retrieval instruction is prepended to questions for BGE English models (FastEmbed doesn't add it). Set empty to disable. |
| `CHUNK_SIZE` / `CHUNK_OVERLAP` / `MIN_CHUNK_SIZE` | `1000` / `150` / `200` | Characters. |
| `MAX_UPLOAD_MB` / `ALLOWED_EXTENSIONS` | `10` / `.pdf,.docx,.txt,.md` | Legacy `.doc` is not supported. |
| `API_KEY` | – | **Set this before exposing the app publicly.** Protects every endpoint except `/health*` and `/config`. |
| `CORS_ORIGINS` | – | Only needed when another website calls the API. |
| `STORAGE_BACKEND` | `local` | `gcs` mirrors storage to a private bucket (billing required). |
| `LOG_FORMAT` | `console` | `json` emits Cloud Logging-compatible lines (`severity`, `message`, trace). |
| `GOOGLE_OAUTH_INTERACTIVE` | `true` | Set `false` on servers; the Docker image already does. |
| `AUTO_SYNC_ON_STARTUP` | `false` | Re-sync Drive at startup (hosts with ephemeral disks). |

---

## Google Drive setup

The Drive API has no charge for standard use, and you don't need a billing account for it.

1. In the [Google Cloud console](https://console.cloud.google.com/), create a project. **Do not link a billing account** to it (Google has announced charges for exceeding Drive API quotas, billed to a linked billing account; without one there is nothing to bill).
2. Enable the **Google Drive API**.
3. Configure the OAuth consent screen. If the **Personal** user type is offered, choose it: Google documents that personal-mode apps need no verification and are not subject to the 7-day token expiry (it can't be changed later). Otherwise choose **External**, keep the app in **Testing**, and add yourself as a test user — but note that **refresh tokens of Testing apps expire after 7 days**.
4. Create an OAuth client ID of type **Desktop app** and download it as `credentials.json` (project root, or `secrets/` for Docker).
5. Create a token once, on your own machine (opens a browser):
   ```bash
   python -m connectors.gdrive auth
   ```
   This writes `token.json`. For Docker, move both files to `secrets/`. For hosts without files, paste their JSON contents into `GOOGLE_CREDENTIALS_JSON` / `GOOGLE_TOKEN_JSON`.
6. Optionally set `GOOGLE_DRIVE_FOLDER_IDS` (the ID is the last part of the folder URL). Only files directly inside those folders are synced; subfolders are not.

Sync behaviour:
- Only new or changed files are downloaded and indexed.
- A file's sync state is saved **only after it was indexed successfully**, so failures are retried on the next sync.
- Files deleted (or trashed) in Drive are removed from the index.
- Deleting a Drive document in the UI is temporary: Drive is the source of truth, so the next sync re-adds it. Move the file out of the synced folder to exclude it.

---

## API

Every endpoint is available under `/api/v1` (documented) and at the root (backwards compatible).

| Method & path | Purpose |
|---|---|
| `GET /health` | Liveness + index statistics |
| `GET /health/ready` | Readiness: storage, index, registry, LLM config (`ready`/`degraded` = 200, `not_ready` = 503) |
| `GET /config` | Non-secret settings for the UI |
| `POST /upload` | Upload + index one file. 400 invalid, 409 duplicate content, 413 too large, 422 no extractable text |
| `POST /sync-drive` | Sync Google Drive (409 if a sync is already running) |
| `POST /ask` | Ask a question |
| `GET /documents` · `GET /documents/{id}` | List documents / one document with status |
| `DELETE /documents/{id}` | Remove a document, its chunks and stored file |
| `POST /reindex` | Rebuild the index from stored originals |
| `DELETE /clear` | Remove everything (index, registry, sync state, stored files) |

```bash
curl -F "file=@policy.pdf" http://localhost:8000/api/v1/upload
curl -H "Content-Type: application/json" -d '{"query":"What is the refund window?"}' \
     http://localhost:8000/api/v1/ask
# with API_KEY set:  -H "X-API-Key: <your key>"
```

`POST /ask` returns the v1 fields (`answer`, `sources`, `source_details`, `query`, `chunks_retrieved`) plus:

| Field | Meaning |
|---|---|
| `answer_status` | `answered` · `extractive` (no LLM) · `insufficient_context` · `no_documents` · `llm_error` |
| `citations` | `[{number, file_name, page, section, snippet, score, url, …}]` — `number` matches `[n]` in the answer |
| `provider`, `model` | Which LLM produced the answer |
| `warning` | e.g. the LLM failed (excerpts shown instead) or the answer has no citations |

"Not in your documents" is detected twice: when no chunk clears `SIMILARITY_THRESHOLD` (the LLM is not called at all), and when the model replies `INSUFFICIENT_CONTEXT`. If the LLM fails, the response says so explicitly; the app never switches to another provider on its own.

---

## Testing

```bash
pip install -r requirements-dev.txt

pytest -m "not integration and not live"   # fast unit + API tests, fully offline
pytest -m integration                      # real FastEmbed model (downloads ~70 MB once)
pytest                                     # everything except opt-in live tests
```

| Area | Tests |
|---|---|
| Ingestion | `test_parser.py`, `test_validation.py`, `test_api.py` (upload types, rejections, duplicates, sanitized names) |
| Chunking | `test_chunker.py` (no text lost, sizes, overlap, sections, pages, IDs) |
| Embeddings + FAISS | `test_integration_embeddings.py` (real model, retrieval, threshold), `test_vector_store.py` |
| Groq / Gemini | `test_llm_service.py` (request shape, errors, rate-limit reporting — faked clients, no network) |
| Citations / insufficient context | `test_api.py`, `test_llm_service.py` |
| Persistence & recovery | `test_vector_store.py`, `test_registry_and_persistence.py`, `test_api.py` (restart, corrupt index → reindex, GCS restore) |
| Google Drive sync | `test_gdrive_sync.py` (fake Drive: new/updated/unchanged/removed, retry after failure, re-sync after clear) |

Optional live Groq test (2 tiny requests on your free plan):

```bash
RUN_LIVE_LLM_TESTS=1 GROQ_API_KEY=... pytest -m live
```

CI ([.github/workflows/ci.yml](.github/workflows/ci.yml)) runs unit tests, integration tests and a Docker build + smoke test on GitHub-hosted runners, which are free for public repositories. No secrets are used.

---

## Free deployment options

Facts below were checked against the providers' official pages on **2026-11-19**. Free tiers change; re-check before relying on them.

| Option | Cost | Billing / card | Persistence | Good for |
|---|---|---|---|---|
| **Local Python / Docker** (recommended) | $0 | None | Yes (disk / Docker volume) | Everyday use, development |
| **Render free web service** | $0 within limits | Not required; without a payment method Render suspends the service instead of billing when bandwidth/build-minute allowances run out | **No** — disk is wiped on every redeploy, restart and spin-down; free services can't attach disks | A public demo |
| **Google Cloud Run** | Free tier, then billed | **Billing account required** | Only with the GCS mirror (also needs billing) | Learning GCP — see next section |

**Render notes** ([render.com/docs/free](https://render.com/docs/free)): 750 free instance hours per workspace per month; spins down after 15 minutes without traffic and takes about a minute to wake; may restart at any time. Because the disk is ephemeral, uploaded files are lost — use Google Drive as the source and set `AUTO_SYNC_ON_STARTUP=true`, plus `GOOGLE_OAUTH_INTERACTIVE=false`, `GOOGLE_CREDENTIALS_JSON`, `GOOGLE_TOKEN_JSON`, `GROQ_API_KEY` and **`API_KEY`** (the URL is public). Testing-mode OAuth tokens expire after 7 days (see [Drive setup](#google-drive-setup)).

**GitHub Actions** ([docs](https://docs.github.com/en/billing/concepts/product-billing/github-actions)): standard GitHub-hosted runners are free for public repositories. For private repositories the Free plan includes $12/month of compute (≈2,000 Linux minutes); without a payment method, usage is blocked (not billed) once it's used up.

---

## Google Cloud integrations (optional, learning path)

Every GCP integration is **off by default**. The code supports them; nothing is created unless you run the commands below yourself.

| Service | How this project uses it | Free allowance (checked 2026-11-19) | Billing account? |
|---|---|---|---|
| **Drive API** | Document source | No charge for standard use; overage charges announced "later in 2026" | **No** |
| **OAuth** | Drive login | Free | No |
| **Cloud Run** | Hosts the container | Request-based billing: 2M requests, 180,000 vCPU-s, 360,000 GiB-s, 1 GB North-America egress / month | **Yes** |
| **Cloud Storage** | `STORAGE_BACKEND=gcs` mirror so the index survives restarts | 5 GB-months Standard storage in `us-central1`, `us-east1`, `us-west1`; 5,000 Class A + 50,000 Class B ops / month | **Yes** |
| **Secret Manager** | `GROQ_API_KEY`, `API_KEY`, `GOOGLE_TOKEN_JSON` as Cloud Run secrets (no code needed) | 6 active secret versions, 10,000 access operations, 3 rotation notifications / month | **Yes** |
| **Cloud Logging** | `LOG_FORMAT=json` lines are parsed automatically on Cloud Run (severity, request trace) | First 50 GiB / project / month | Comes with Cloud Run |
| **Artifact Registry** | Stores the container image | 0.5 GB / month | **Yes** — the image is larger than this (see warnings) |
| **Cloud Build** | Builds the image for `gcloud run deploy --source` | 2,500 build-minutes / month on `e2-standard-2` (another Google page says 120/day) | **Yes** |
| **Vertex AI** | **Not used** (paid). The optional Gemini provider uses the AI Studio API instead. | — | — |

Sources: [Free features & trial](https://docs.cloud.google.com/free/docs/free-cloud-features), [Cloud Run pricing](https://cloud.google.com/run/pricing), [Cloud Storage pricing](https://cloud.google.com/storage/pricing), [Secret Manager pricing](https://cloud.google.com/secret-manager/pricing), [Observability pricing](https://cloud.google.com/stackdriver/pricing), [Artifact Registry pricing](https://cloud.google.com/artifact-registry/pricing), [Cloud Build pricing](https://cloud.google.com/build/pricing), [Drive API limits](https://developers.google.com/workspace/drive/api/guides/limits). Free-tier limits are calculated per billing account (Logging: per project) and Google can change them with 30 days' notice.

### The only zero-risk way to try Cloud Run: the Free Trial

Google's Free Trial gives a $300 credit for 90 days and states you are **not billed unless you manually upgrade** to a paid account. When the trial ends, billing is disabled, a 30-day grace period starts, and then the trial's resources are deleted. So: sign up for the Free Trial, follow the steps below, **never click "Upgrade"/"Activate full account"**, and delete the project when you're done. Note: the trial credit can't pay for Gemini API usage in AI Studio.

After the trial, using Cloud Run's free tier means a paid billing account, where anything over the free limits is charged. That does not meet a strict $0 budget; prefer local Docker.

A new **Starter Tier** (Google-managed project, no billing account) was announced recently; its service list and limits were unclear/contradictory when checked, so this project doesn't rely on it.

### Deploy to Cloud Run (only after you've read the warnings)

```bash
PROJECT_ID=your-project-id
REGION=us-central1                 # an Always Free region for Cloud Storage
BUCKET=${PROJECT_ID}-highwatch-rag
SA=highwatch-run@${PROJECT_ID}.iam.gserviceaccount.com

gcloud config set project $PROJECT_ID
gcloud services enable run.googleapis.com artifactregistry.googleapis.com \
  cloudbuild.googleapis.com secretmanager.googleapis.com storage.googleapis.com

# 1. Private bucket (public access prevention + uniform access)
gcloud storage buckets create gs://$BUCKET --location=$REGION \
  --uniform-bucket-level-access --public-access-prevention

# 2. Service account with access to only this bucket and these secrets
gcloud iam service-accounts create highwatch-run
gcloud storage buckets add-iam-policy-binding gs://$BUCKET \
  --member=serviceAccount:$SA --role=roles/storage.objectAdmin

# 3. Secrets (3 secret versions; free tier is 6)
printf %s "$GROQ_API_KEY" | gcloud secrets create groq-api-key --data-file=-
printf %s "$(openssl rand -hex 24)" | gcloud secrets create app-api-key --data-file=-
gcloud secrets create google-token-json --data-file=secrets/token.json
for s in groq-api-key app-api-key google-token-json; do
  gcloud secrets add-iam-policy-binding $s --member=serviceAccount:$SA \
    --role=roles/secretmanager.secretAccessor
done

# 4. Deploy: private (IAM-only), scale to zero, at most one instance
gcloud run deploy highwatch-rag --source . --region $REGION \
  --service-account $SA --no-allow-unauthenticated \
  --memory 1Gi --cpu 1 --min-instances 0 --max-instances 1 --concurrency 10 --timeout 300 \
  --set-env-vars LLM_PROVIDER=groq,STORAGE_BACKEND=gcs,GCS_BUCKET=$BUCKET,LOG_FORMAT=json,GOOGLE_CLOUD_PROJECT=$PROJECT_ID \
  --set-secrets GROQ_API_KEY=groq-api-key:latest,API_KEY=app-api-key:latest,GOOGLE_TOKEN_JSON=google-token-json:latest

# 5. Use it through an authenticated local proxy (no public URL to abuse)
gcloud run services proxy highwatch-rag --region $REGION --port 8080
# open http://localhost:8080 and enter the API key (gcloud secrets versions access latest --secret app-api-key)
```

Why these flags: `--no-allow-unauthenticated` means only you can send requests (no strangers consuming your free tier); `--min-instances 0` means no charge while idle; `--max-instances 1` caps parallel cost and is required because the GCS mirror is last-writer-wins. Processing happens inside requests because Cloud Run throttles CPU after a response is sent.

### Budget alerts and spend caps

```bash
gcloud billing budgets create --billing-account=XXXXXX-XXXXXX-XXXXXX \
  --display-name="highwatch-1-usd" --budget-amount=1USD \
  --threshold-rule=percent=0.5 --threshold-rule=percent=0.9 --threshold-rule=percent=1.0
```

- **Budget alerts are not spending caps.** Google: budgets "don't automatically cap" usage or spending; costs appear with a delay.
- **Spend caps** (generally available since 2026-10-13) can pause **Cloud Run** usage in one project when a monthly cap is reached, but they apply to a single project and service, are based on gross estimated cost, are **not instant, and overages are still billed**. They don't stop storage charges (Cloud Storage, Artifact Registry).
- Google's "disable billing via Pub/Sub" automation also comes with the caveat that it "doesn't guarantee" you won't exceed the budget, and it shuts down everything in the project.

---

## Cost and billing warnings

- **Nothing here is guaranteed free once a billing account is linked.** Free tiers have limits, are per billing account, and can change.
- **Artifact Registry**: the container image (Python + ONNX runtime + FAISS + embedding model) is larger than the 0.5 GB free storage, and every `gcloud run deploy --source` adds a new image. On a paid billing account this is billed monthly. Delete old images (see [Cleanup](#cleanup)).
- **Cloud Storage**: use `us-central1`, `us-east1` or `us-west1` and the Standard class; other regions, multi-region buckets and other classes are not covered by Always Free.
- **Public endpoints cost money**: a public Cloud Run URL lets anyone generate requests. Keep `--no-allow-unauthenticated`, or at least set `API_KEY`.
- **Gemini free tier data use**: Google's terms say unpaid-service prompts and responses are used to improve Google products and **may be read by human reviewers** — don't send confidential documents. In the EEA, Switzerland and the UK, apps for users there must use paid services. Linking billing to the AI Studio project turns usage into a paid service.
- **Vertex AI is paid** and not used. The Free Trial credit can't be used for Gemini platform (Vertex AI) services for sign-ups on or after 2026-11-16.
- **Groq**: stay on the free plan (requests over its rate limits get HTTP `429`, which the app reports). Don't add a payment method or upgrade if you need $0. Free-plan limits shown for `openai/gpt-oss-120b` were 30 requests/min, 1,000/day, 8,000 tokens/min, 200,000 tokens/day.
- **Drive API**: Google has announced charges for exceeding quotas "later in 2026" (at least 90 days' notice), billed to the project's billing account. Keep the OAuth project without billing.
- **Render**: without a payment method the service is suspended (not billed) when free allowances run out.
- **GitHub Actions**: free for public repos; private repos without a payment method are blocked, not billed, after the included $12/month.

---

## Cleanup

**Local**
```bash
docker compose down -v                 # container + data volume
docker image rm highwatch-rag:local
rm -rf storage/ .fastembed_cache/      # local Python data (Windows: rmdir /s storage)
```

**Revoke access**
- Groq: delete the key at <https://console.groq.com/keys>
- Google OAuth: <https://myaccount.google.com/permissions> → remove the app; delete `token.json` / `secrets/token.json`

**Render**: delete the service in the dashboard (removes its environment variables too).

**Google Cloud** (if you deployed)
```bash
gcloud run services delete highwatch-rag --region $REGION
gcloud artifacts repositories delete cloud-run-source-deploy --location $REGION   # deployed images
gcloud storage rm --recursive gs://$BUCKET
gcloud secrets delete groq-api-key && gcloud secrets delete app-api-key && gcloud secrets delete google-token-json
gcloud iam service-accounts delete $SA
# Or remove everything at once (30-day pending-deletion period):
gcloud projects delete $PROJECT_ID
```
Then check **Billing → Reports** a few days later to confirm no charges.

---

## Upgrading from v1

- `LLM_PROVIDER` now defaults to `groq`; `openai` is rejected (paid). Set `GROQ_MODEL` only if you need a model other than `openai/gpt-oss-120b`.
- Existing indexes load as-is and their documents appear in the list. **Run `POST /reindex` once** to benefit from the fixed parser (paragraphs were previously collapsed) and the new chunker (short sections were previously dropped). Re-syncing Drive re-indexes Drive files automatically.
- `/health` no longer lists document IDs. New: `/health/ready`, `/config`, `GET /documents/{id}`, `/reindex`.
- Legacy `.doc` uploads are rejected with a clear message (they could never be parsed).

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| Startup error mentioning `$0 budget` | `LLM_PROVIDER=openai` in `.env`; change it to `groq`, `gemini` or `extractive`. |
| Answers say "The AI model (groq) failed: … 429" | Groq free-plan rate limit; wait and retry, or use a smaller model. |
| `model_not_found` / decommissioned | List models with your key: `curl https://api.groq.com/openai/v1/models -H "Authorization: Bearer $GROQ_API_KEY"`, then set `GROQ_MODEL`. |
| Sync: "OAuth token has expired or was revoked" | Testing-mode tokens expire after 7 days. Run `python -m connectors.gdrive auth` again. |
| Status "Degraded — vector store: … moved aside" | Index was inconsistent or built with another model. Run `POST /reindex`. |
| Upload returns 422 "No extractable text" | Scanned/image-only PDF; OCR isn't supported. |
| Everything is "not in your documents" | Check the document was indexed, then lower `SIMILARITY_THRESHOLD` slightly (e.g. 0.5). If you changed `EMBEDDING_MODEL`, re-calibrate with `pytest -m integration -s`. |
