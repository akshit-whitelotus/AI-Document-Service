# AI Document Processing Service

An async FastAPI microservice that accepts document uploads, runs them through
a simulated AI processing pipeline in the background, and streams **live
progress updates** to clients over both **WebSocket** and **Server-Sent
Events (SSE)**. Built with production concerns in mind: correlation IDs,
latency logging, graceful startup/shutdown, and streaming I/O for large files.

---

## Features

- **Streaming uploads** — files are read and written in 1MB chunks, never
  fully loaded into memory (`app/api/v1/routes_documents.py`)
- **Background AI pipeline** — each upload is processed asynchronously through
  stages: `queued → extracting → analyzing → summarizing → done`
  (`app/services/document_processor.py`)
- **WebSocket endpoint** — real-time push of job progress, multiple clients
  per job supported (`/ws/jobs/{job_id}`)
- **SSE endpoint** — same progress stream for clients that can't use
  WebSockets, with 15s keep-alive pings (`/sse/jobs/{job_id}`)
- **Streaming downloads** — processed output is streamed back in chunks via
  `StreamingResponse`
- **Correlation ID middleware** — every request gets an `X-Correlation-ID`
  (generated or passed in), propagated via `contextvars` for async-safe log
  correlation
- **Latency logging middleware** — logs method, path, status code, and
  duration (ms) for every request
- **Lifespan management** — `JobManager` (in-memory job store + pub/sub) is
  created on startup and cleanly cancels background tasks on shutdown
- **Auto-generated Swagger docs** at `/docs`

---

## Architecture

```
Client
  │
  ├── POST /documents/upload ───────► streams file to disk, kicks off
  │                                    background DocumentProcessor task,
  │                                    returns job_id immediately
  │
  ├── WS   /ws/jobs/{job_id}   ─┐
  ├── SSE  /sse/jobs/{job_id}  ─┤──► both subscribe to JobManager's
  │                             │    in-memory pub/sub for that job_id
  │                             │
  │        DocumentProcessor ───┘    publishes JobProgress updates as it
  │                                  works through each pipeline stage
  │
  └── GET  /documents/{job_id}/download ─► streams the generated output
                                            file back once status = "done"
```

**Why in-memory instead of Redis?** For a single-process/single-worker
deployment this keeps the service dependency-free and simple. `JobManager`
is isolated behind a small interface (`publish` / `subscribe` / `create_task`
/ `shutdown`), so swapping in Redis pub/sub for multi-worker or multi-instance
deployments is a contained change — no route or middleware code would need
to change.

**Middleware order:** `CorrelationIdMiddleware` is registered before
`LatencyLoggingMiddleware` so the correlation ID is already bound to the
request context by the time latency is logged, keeping every log line for a
request traceable by the same ID.

### Project structure

```
app/
├── main.py                      # FastAPI app, middleware & router wiring
├── core/
│   ├── config.py                 # Settings (env-driven)
│   ├── logging.py                 # Logging setup
│   └── lifespan.py                # Startup/shutdown — creates/tears down JobManager
├── api/v1/
│   ├── routes_documents.py       # Upload / streaming download
│   ├── routes_ws.py              # WebSocket progress endpoint
│   └── routes_sse.py             # SSE progress endpoint
├── middleware/
│   ├── correlation_id.py         # X-Correlation-ID middleware
│   └── latency_logging.py        # Request latency logging middleware
├── services/
│   ├── document_processor.py     # Simulated AI pipeline
│   └── job_manager.py            # In-memory job store + pub/sub
├── schemas/
│   └── job.py                    # JobProgress pydantic model
├── models/
└── utils/
tests/
├── test_upload.py
├── test_ws.py
├── test_sse.py
├── test_middleware.py
└── test_lifespan.py
storage/
├── uploads/                      # Raw uploaded files
└── outputs/                      # Generated processed output
```

---

## Requirements

- Python 3.11+
- See `requirements.txt` for pinned dependencies (FastAPI, Uvicorn, Pydantic
  v2, aiofiles, sse-starlette, pytest stack)

---

## Setup

```bash
# 1. Clone and enter the project
git clone <your-repo-url>
cd ai-document-processing-service

# 2. Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment variables
cp .env.example .env            # edit values if needed
```

### Environment variables (`.env`)

| Variable            | Description                              | Example                |
|---------------------|-------------------------------------------|-------------------------|
| `APP_NAME`           | Service name shown in Swagger/health check| `AI Document Processing Service` |
| `ENVIRONMENT`         | Environment label                        | `development`           |
| `UPLOAD_DIR`          | Directory raw uploads are streamed to     | `storage/uploads`       |
| `OUTPUT_DIR`          | Directory processed output is written to  | `storage/outputs`       |
| `MAX_UPLOAD_SIZE_MB`  | Upload size guard (MB)                   | `500`                    |
| `LOG_LEVEL`           | Logging verbosity                        | `INFO`                   |

---

## Running the service

```bash
uvicorn app.main:app --reload --port 8000
```

- Swagger UI: http://127.0.0.1:8000/docs
- ReDoc: http://127.0.0.1:8000/redoc
- Health check: `GET /` → `{"service": "...", "status": "Healthy"}`

---

## API usage

### 1. Upload a document

```bash
curl -X POST http://127.0.0.1:8000/documents/upload \
  -F "file=@/path/to/document.pdf"
```

Response:
```json
{ "job_id": "f1b78934-6bfe-4a2c-9e97-12bcf2fd6039", "status": "queued" }
```

### 2. Track progress — WebSocket

```python
import asyncio, websockets, json

async def main():
    job_id = "f1b78934-6bfe-4a2c-9e97-12bcf2fd6039"
    async with websockets.connect(f"ws://127.0.0.1:8000/ws/jobs/{job_id}") as ws:
        async for message in ws:
            print(json.loads(message))

asyncio.run(main())
```

### 3. Track progress — SSE

```bash
curl -N http://127.0.0.1:8000/sse/jobs/f1b78934-6bfe-4a2c-9e97-12bcf2fd6039
```

```javascript
// Browser client
const jobId = "f1b78934-6bfe-4a2c-9e97-12bcf2fd6039";
const source = new EventSource(`http://127.0.0.1:8000/sse/jobs/${jobId}`);
source.addEventListener("progress", (e) => {
  console.log(JSON.parse(e.data));
});
```

Each progress message looks like:
```json
{
  "job_id": "f1b78934-6bfe-4a2c-9e97-12bcf2fd6039",
  "status": "extracting",
  "progess": 30,
  "timestamp": "2026-07-21T12:13:20.123456+00:00"
}
```

### 4. Download the processed result

Once a client observes `"status": "done"`, fetch the output:

```bash
curl -OJ http://127.0.0.1:8000/documents/f1b78934-6bfe-4a2c-9e97-12bcf2fd6039/download
```

The response is streamed via `StreamingResponse` with the correct
`Content-Disposition` and `Content-Type` headers.

---

## Correlation IDs & latency logs

Every response includes an `X-Correlation-ID` header (either echoed back from
your request or generated). Every request is logged with method, path,
status, and latency:

```
2026-07-21 12:13:19 INFO request-latency - POST /documents/upload 200 3.01ms
```

Pass your own ID to trace a request across services:

```bash
curl -H "X-Correlation-ID: my-trace-id" http://127.0.0.1:8000/
```

---

## Running tests

```bash
pytest -v
```

Test suite covers:
- `test_upload.py` — streaming upload + job creation
- `test_ws.py` — WebSocket connection and progress message flow
- `test_sse.py` — SSE stream and event formatting
- `test_middleware.py` — correlation ID propagation, latency logging
- `test_lifespan.py` — startup/shutdown behavior of `JobManager`

---

## Notes

- The AI processing pipeline in `document_processor.py` performs real text
  extraction: `.pdf` files are parsed with `pypdf`, and non-PDF files are
  read as plain text. If a PDF has no extractable text layer (i.e. it's a
  scanned/image-only PDF), it falls back to OCR via `pytesseract` +
  `pdf2image` when the system packages `tesseract-ocr` and `poppler-utils`
  are installed; otherwise the output explains that no text could be
  extracted rather than failing silently. The `analyzing`/`summarizing`
  stages are still simulated (fixed timed delays) — swap those for a real
  LLM call as needed.
- `JobManager` is in-memory and per-process — for multi-worker or
  multi-instance deployments, replace it with a Redis-backed pub/sub
  implementation behind the same interface.