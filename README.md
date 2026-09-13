# DataQX — Intelligent Data Quality & Preparation Platform

DataQX is a stateless, project-aware Data Quality & Preparation Platform. It profiles,
detects, cleans, validates, audits, tracks lineage, detects data drift, evaluates Power BI
readiness, and generates professional analytics-ready datasets and reports from messy
uploaded data — without ever writing to a database.

Full specification: `DATAQX.pdf` (single source of truth for this project).

## Absolute Architecture Rules

- **No database of any kind** — no PostgreSQL, MySQL, MongoDB, SQLite, Supabase/Neon/Firebase
  database, Redis-as-storage, or any SQL/NoSQL/cloud database.
- **No ORM** — no SQLAlchemy, Prisma, Django ORM, MongoEngine, Tortoise, or any ORM layer.
- **No database infrastructure** — no schemas, tables, migrations, connections, CRUD APIs,
  models, repositories, or database-backed auth/sessions.
- **No Docker** — no Docker, Docker Compose, Kubernetes, or containers. Runs directly on a
  normal machine with Python + Node.js + npm.
- **Stateless & file-based only** — all run artifacts (profiles, logs, lineage, drift
  history, reports) are written to and read from the filesystem (`data/`, `reports/`,
  `logs/`). Run identity flows through a `run_id`, not server-side session state.
- **Original data protection** — raw uploads under `data/input/` are never overwritten.
  Cleaned output goes to `data/output/`; scratch work goes to `data/temp/`.

## Technology Stack

**Frontend:** React, Vite, TypeScript (where practical), Tailwind CSS, Recharts — deployed to Vercel.

**Backend:** Python, FastAPI, Pandas, NumPy, PyArrow, OpenPyXL, PyYAML, ReportLab, SciPy,
scikit-learn (where useful) — deployed to Render.

**Testing:** pytest (backend), Vitest or similar (frontend).

## Project Directory

```
dataqx/
├── backend/            FastAPI app (app/api, app/core, app/models, app/services, app/utils) + tests
├── frontend/            React + Vite app (src/components, pages, services, hooks, types, utils) + tests
├── data/
│   ├── input/           Raw uploads — NEVER modified
│   ├── output/          Cleaned/generated datasets
│   ├── temp/             Ephemeral processing scratch space
│   └── samples/         Sample/test datasets with known, intentional issues
├── project/
│   └── project_plan.md  User-provided project requirements (drives project-aware cleaning)
├── reports/
│   ├── runs/            Per-run artifact directories (file-based run metadata)
│   └── history/         Historical profile snapshots (used for drift detection)
├── logs/                 audit_log.csv, cleaning_log.csv, errors.log, performance.log
├── config/               Non-secret runtime configuration
└── DATAQX.pdf            Full specification
```

## Local Development

Requires only:
- Python 3.12+
- Node.js + npm

No Docker, no database server, no external services.

**Backend** (from `backend/`):
```
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python -m uvicorn main:app --reload
```
Runs at `http://localhost:8000`. Health check: `GET /health`.

**Frontend** (from `frontend/`), in a second terminal:
```
npm install
npm run dev
```
Runs at `http://localhost:5173` and talks to the backend at `http://localhost:8000`
(CORS is already configured for this origin). Open it, go to **Upload Dataset**, choose
a CSV/Excel/JSON/Parquet file, and click **Analyze Dataset** — this runs the real
upload → analyze → clean → validate chain against the backend and lands on a live
**Dashboard** populated entirely from real API responses.

Run the test suites:
```
cd backend && .venv\Scripts\python -m pytest
cd frontend && npm run test
cd frontend && npm run test:e2e   # real Playwright browser test against both live servers
```

## Development Status

Implemented in phases, verified end-to-end before moving forward (see `DATAQX.pdf` §64–66
for the mandated PLAN → IMPLEMENT → TEST → VERIFY workflow).

- [x] Phase 0 — Environment & Architecture
- [x] Phase 1 — FastAPI Foundation (health endpoint, config, logging, filesystem utils)
- [x] Phase 2 — React Foundation (routing, layout, dashboard shell)
- [x] Phase 3 — Upload System
- [x] Phase 4 — Multi-Format Ingestion (CSV/TSV/Excel/JSON/Parquet/Feather/XML)
- [x] Phase 5 — Dataset Profiling
- [x] Phase 6 — Issue Detection
- [x] Phase 7 — Confidence Engine (HIGH/MEDIUM/LOW)
- [x] Phase 8 — Cleaning Engine
- [x] Phase 9 — Audit Logging (file-based, `logs/audit_log.csv`/`cleaning_log.csv`)
- [x] Phase 10 — Data Lineage
- [x] Phase 11 — Validation Engine
- [x] Phase 12 — Validation Gates & Rollback
- [x] Phase 13 — Project Plan Integration
- [x] Phase 14 — File-Based Run Metadata
- [x] Phase 15 — Data Drift
- [x] Phase 16 — Power BI Validation
- [x] Phase 17 — Data Dictionary & Summaries (Quality Score, Before/After)
- [x] Phase 18 — PDF Reporting (`DataQX_Report.pdf`)
- [x] Phase 19 — Dashboard Integration: Upload + Dashboard pages wired to real
      backend results, no hardcoded metrics.
- [x] Phase 20 — Lineage / Drift / Power BI UI: before/after, data dictionary, and
      download endpoints wired to the remaining sidebar pages.
- [x] Phase 21 — Performance: performance logging (`performance_log.csv`), pipeline
      result caching, processing-time surfaced in the frontend.
- [x] **Phase 22 — Security & Error Handling**: friendly `IngestionError` reasons for
      corrupt Excel/Parquet/Feather files, a global unhandled-exception safety net
      (`main.py`) that guarantees no raw stack trace ever reaches a client, basic
      hardening response headers, and a dedicated `test_security.py` /
      `test_malformed_inputs.py` suite covering path traversal, unsafe filenames,
      extension spoofing, and corrupt/malformed dataset files.
- [x] **Phase 23 — Full Testing**: a full-chain backend pipeline test
      (`test_full_pipeline_e2e.py`, upload→analyze→clean→validate→lineage→drift→
      Power BI→dictionary→before/after→quality→report→download→performance in one
      run), `pytest-cov` coverage reporting (270 backend tests, 96% coverage),
      stress/concurrency tests (`test_performance_stress.py`, a 100k-row run and two
      interleaved runs proving per-run artifact isolation), and a real Playwright
      browser E2E test (`frontend/e2e/full-journey.spec.ts`) driving the actual dev
      servers through the full user journey — upload, every sidebar page, and a real
      file download. *(current)*
- [ ] Phase 24 — Final End-to-End Validation (see `DATAQX.pdf` §65)
