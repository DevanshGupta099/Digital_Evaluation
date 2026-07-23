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
| 4. Rubric evaluation | `backend/app/grading/` | Per-rubric-point grading; every mark must cite evidence lines; dual pass at temperature 0; confidence gating; calibration examples |
| 5. Annotation & report | `backend/app/annotation/`, `backend/app/reports/` | PyMuPDF coordinate overlay: green ticks, red crosses/underlines, circled marks badges, running total; JSON summary report |
| 6. Human review | `backend/app/api/routes.py`, `frontend/` | Side-by-side annotated PDF + AI reasoning; accept/override per question; marks final only after review |

## Anti-hallucination design

- A mark cannot be awarded without cited OCR line indices (enforced by a Pydantic validator, not just the prompt).
- Decomposed per-rubric-point scoring, never one holistic score.
- Two independent passes at temperature 0; disagreements above threshold are flagged, never averaged.
- Confidence gating on evaluation confidence and OCR legibility of cited lines.
- Citations of nonexistent lines and over-max marks are rejected/flagged.
- Unmatched answer segments become zero-mark flagged records — never silently graded or dropped.
- Full audit trail: OCR segments, both evaluation passes, evidence, flags, and human overrides stored as separate records.

## Backend (FastAPI + PyMuPDF + Anthropic)

```bash
cd backend
uv venv .venv && uv pip install -p .venv -e ".[dev]"   # or: pip install -e ".[dev]"
# optional cloud OCR extras: -e ".[dev,azure,google]"
cp .env.example .env                                    # set keys / provider
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

See `backend/.env.example`. `OCR_PROVIDER=mock` runs the whole pipeline offline;
set `azure` or `google` plus credentials for real handwriting OCR, and
`ANTHROPIC_API_KEY` for real grading.
