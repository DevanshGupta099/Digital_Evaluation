# AI Answer Script Grader

Grades handwritten exam answer scripts against a marking rubric, annotates the
script PDF with ticks/crosses/marks at exact coordinates, and routes anything
uncertain to a human review screen.

Five separate modules with clean interfaces — each stage's output is verifiable
input for the next:

| Stage | Module | What it does |
|---|---|---|
| 1. Ingestion | `backend/app/ocr/preprocess.py` | Normalizes PDFs/images to 300-DPI page images; originals stored untouched |
| 2. OCR | `backend/app/ocr/` | Handwriting OCR with word/line bounding boxes + confidence (Azure Document Intelligence, Google Vision, or mock) |
| 3. Segmentation & matching | `backend/app/segmentation/` | Detects question boundaries (incl. "Q2 continued"), matches segments to questions semantically, flags unattributable segments for review |
| 4. Rubric evaluation | `backend/app/grading/` | **Dual-model dual-pass**: Gemini grades first (primary), Grok grades independently (cross-check); every mark must cite evidence lines; confidence gating; calibration examples |
| 5. Annotation & report | `backend/app/annotation/`, `backend/app/reports/` | PyMuPDF coordinate overlay: green ticks, red crosses/underlines, circled marks badges, running total; JSON summary report |
| 6. Human review | `backend/app/api/routes.py`, `frontend/` | Side-by-side annotated PDF + AI reasoning; accept/override per question; marks final only after review |

## Stage 4 — Dual-Model Cross-Check Design

Stage 4 uses **two completely independent LLMs** to eliminate single-model bias:

| Pass | Model | Role |
|---|---|---|
| Pass 1 (primary) | **Google Gemini** (`GEMINI_MODEL`) | Produces the authoritative grading result |
| Pass 2 (cross-check) | **xAI Grok** (`GROK_MODEL`) | Independent second opinion; result stored alongside pass 1 |

When the two models disagree by more than `DISAGREEMENT_THRESHOLD` (default 15 % of total marks),
the question is automatically flagged for human review. Neither model's result is silently
preferred or averaged — the flag makes the discrepancy transparent.

## Anti-hallucination design

- A mark cannot be awarded without cited OCR line indices (enforced by a Pydantic validator, not just the prompt).
- Decomposed per-rubric-point scoring, never one holistic score.
- Two **independent models** at temperature 0; disagreements above threshold are flagged, never averaged.
- Confidence gating on evaluation confidence and OCR legibility of cited lines.
- Citations of nonexistent lines and over-max marks are rejected/flagged.
- Unmatched answer segments become zero-mark flagged records — never silently graded or dropped.
- Full audit trail: OCR segments, both evaluation passes, evidence, flags, and human overrides stored as separate records.

## Backend (FastAPI + PyMuPDF + Gemini + Grok)

```bash
cd backend
uv venv .venv && uv pip install -p .venv -e ".[dev]"   # or: pip install -e ".[dev]"
# optional cloud OCR extras: -e ".[dev,azure,google]"
cp .env.example .env                                    # set keys — see below
.venv/Scripts/uvicorn app.main:app --reload             # http://localhost:8000
```

Run tests (offline — mock OCR + fake LLM):

```bash
.venv/Scripts/python -m pytest
.venv/Scripts/ruff check app tests
```

## Frontend (React review UI)

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173 (proxies /api to :8000)
```

## API sketch

- `POST /api/rubrics` — add a question + decomposed rubric (+ optional calibration examples)
- `POST /api/scripts` — upload a script (PDF/image); pipeline runs in background
- `GET /api/scripts/{id}` — status, per-question evaluations, evidence, flags
- `GET /api/scripts/{id}/annotated.pdf` — annotated copy of the script
- `POST /api/evaluations/{id}/review` — accept/override a question's marks

## Configuration

Copy `backend/.env.example` to `backend/.env` and fill in the values below.

### Required API keys for Stage 4

| Variable | Where to get it | Default model |
|---|---|---|
| `GEMINI_API_KEY` | [Google AI Studio](https://aistudio.google.com/apikey) | `gemini-2.5-pro` |
| `GROK_API_KEY` | [xAI Console](https://console.x.ai/) | `grok-3-mini` |

> **OCR** — `OCR_PROVIDER=mock` runs the whole pipeline offline; set `azure` or `google`
> plus credentials for real handwriting OCR.

### Full `.env` reference

```env
# Storage / DB
DATABASE_URL=sqlite:///./grader.db
STORAGE_DIR=./storage

# OCR provider: mock | azure | google
OCR_PROVIDER=mock
AZURE_DOCINT_ENDPOINT=
AZURE_DOCINT_KEY=
GOOGLE_APPLICATION_CREDENTIALS=

# Stage 4 — Pass 1 (primary): Google Gemini
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-2.5-pro

# Stage 4 — Pass 2 (cross-check): xAI Grok
GROK_API_KEY=your_grok_api_key_here
GROK_MODEL=grok-3-mini

# Shared grading parameters
GRADING_TEMPERATURE=0.0
GRADING_PASSES=2
DISAGREEMENT_THRESHOLD=0.15
CONFIDENCE_THRESHOLD=0.75
OCR_CONFIDENCE_THRESHOLD=0.60

# Rendering
RENDER_DPI=300
```
