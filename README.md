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

Backend and frontend run instructions will be added as Phase 1 (FastAPI Foundation) and
Phase 2 (React Foundation) land.

## Development Status

Implemented in phases, verified end-to-end before moving forward (see `DATAQX.pdf` §64–66
for the mandated PLAN → IMPLEMENT → TEST → VERIFY workflow).

- [x] **Phase 0 — Environment & Architecture**: directory scaffolding, docs, environment
      verification. *(current)*
- [ ] Phase 1 — FastAPI Foundation (health endpoint, config, logging, filesystem utils)
- [ ] Phase 2 — React Foundation (routing, layout, dashboard shell)
- [ ] Phase 3+ — Upload, ingestion, profiling, issue detection, cleaning, validation,
      lineage, drift, Power BI readiness, reporting, full UI (see `DATAQX.pdf` §65)

### Known environment gap

Node.js/npm are **not currently installed** on this machine. This does not block Phase 0
or Phase 1 (backend-only) but must be resolved before Phase 2 (React Foundation) begins.
