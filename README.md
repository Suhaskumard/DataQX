# DataQX

## Intelligent data quality and analytics preparation

DataQX is a stateless, project-aware data quality platform for turning messy business
datasets into validated, analytics-ready outputs. It combines profiling, issue detection,
confidence-based cleaning, validation, lineage, drift analysis, and Power BI readiness in
one repeatable workflow.

Upload a dataset, describe the intended use of the data, review the findings, and download
the complete output package, including cleaned data, validation results, audit evidence,
and a professional PDF report.

## Why DataQX

- **Project-aware cleaning**: business requirements and protected columns take priority over
  generic transformation rules.
- **Multi-format ingestion**: CSV, TSV, Excel, JSON, Parquet, Feather, and XML.
- **Transparent decisions**: every detected issue and cleaning action can be reviewed through
  audit logs, before/after comparisons, confidence levels, and lineage.
- **Analytics readiness**: quality scoring, data dictionaries, referential-integrity checks,
  drift detection, and Power BI-oriented validation.
- **Safe processing**: source uploads are preserved; cleaned datasets and run artifacts are
  written separately.
- **Operationally simple**: no database, ORM, Docker, or external stateful service is
  required.

## Workflow

```text
Upload -> Analyze -> Profile -> Detect issues -> Clean -> Validate -> Report -> Download
```

Each run is identified by a `run_id`. The platform produces an isolated artifact set for
that run, making results reproducible and easy to inspect.

## Capabilities

### Data quality

- Dataset profiling and type inference
- Missing-value, duplicate, mixed-type, outlier, format, and consistency detection
- Numeric, text, category, date, identifier, and currency normalization
- Confidence levels for automated recommendations and cleaning actions
- Business-rule and referential-integrity validation
- Validation gates with rollback protection

### Governance and analytics

- File-based audit and cleaning logs
- Before/after comparisons
- Data lineage and run metadata
- Historical drift detection
- Data dictionary and quality score
- Power BI readiness analysis
- Performance metrics and processing-time visibility
- Downloadable CSV/JSON/Excel outputs and PDF reporting

## Architecture

DataQX is intentionally stateless and file-based:

- **Frontend**: React, TypeScript, Vite, Tailwind CSS, Recharts, and Lucide icons.
- **Backend**: Python, FastAPI, Pandas, NumPy, PyArrow, OpenPyXL, SciPy, scikit-learn,
  PyYAML, and ReportLab.
- **Storage model**: raw inputs, generated outputs, reports, and logs live on the filesystem
  under `data/`, `reports/`, and `logs/`.
- **API contract**: the frontend communicates with the backend over HTTP using the REST API.

The architecture does not use a database, ORM, Docker, or database-backed sessions. Raw
uploads under `data/input/` are never overwritten. Temporary processing data goes to
`data/temp/`, and generated data goes to `data/output/`.

## Repository layout

```text
DataQX/
├── backend/              FastAPI application and backend tests
│   ├── app/api/          API routers
│   ├── app/core/         Configuration and logging
│   ├── app/services/     Quality, cleaning, validation, and reporting engines
│   └── app/utils/        Filesystem and shared utilities
├── frontend/             React + Vite application and browser tests
├── data/
│   ├── input/            Original uploads; never modified
│   ├── output/           Cleaned and generated datasets
│   ├── temp/             Ephemeral processing files
│   └── samples/          Sample datasets for development and testing
├── reports/              Per-run artifacts and drift history
├── logs/                 Audit, cleaning, error, and performance logs
├── project/              Project requirements and business rules
├── config/               Non-secret runtime configuration
├── render.yaml           Render backend deployment definition
└── DATAQX.txt            Product and architecture specification
```

## Quick start

### Prerequisites

- Python 3.12 or later
- Node.js and npm

### Start the backend

From the repository root:

```powershell
cd backend
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python -m uvicorn main:app --reload
```

The API is available at `http://localhost:8000`. The health endpoints are:

- `GET http://localhost:8000/health`
- `GET http://localhost:8000/api/health`

### Start the frontend

In a second terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`, upload a CSV, Excel, JSON, or Parquet dataset, and start an
analysis. The frontend uses the backend URL from `VITE_API_BASE_URL`.

## Configuration

Copy the example environment files before deploying or customizing an environment:

```powershell
Copy-Item backend\.env.example backend\.env
Copy-Item frontend\.env.example frontend\.env
```

### Backend

| Variable | Purpose | Default |
| --- | --- | --- |
| `DATAQX_CORS_ORIGINS` | Comma-separated allowed frontend origins | `http://localhost:5173,http://127.0.0.1:5173` |
| `DATAQX_ENV` | Runtime environment label | `development` |
| `DATAQX_MAX_UPLOAD_MB` | Maximum accepted upload size | `200` |

### Frontend

| Variable | Purpose | Default |
| --- | --- | --- |
| `VITE_API_BASE_URL` | Backend API base URL, without a trailing slash | `http://localhost:8000` |

## API surface

All application routes below are prefixed with `/api`.

| Area | Endpoints |
| --- | --- |
| Health and ingestion | `GET /health`, `POST /upload` |
| Analysis | `POST /analyze`, `GET /profile/{run_id}`, `GET /issues/{run_id}` |
| Cleaning and validation | `POST /clean`, `POST /validate` |
| Governance | `GET /audit/{run_id}`, `GET /lineage/{run_id}`, `GET /drift/{run_id}` |
| Analytics | `GET /quality/{run_id}`, `GET /dictionary/{run_id}`, `GET /before-after/{run_id}`, `GET /analytics-readiness/{run_id}` |
| Reporting | `GET /report/{run_id}`, `GET /download/{run_id}/{filename}`, `GET /performance/{run_id}` |

FastAPI's interactive API documentation is available at `/docs` while the backend is
running.

## Project requirements

For business-sensitive processing, complete `project/project_plan.md` before analysis, or
provide the equivalent requirements through the frontend. A project plan can define:

- Business questions, KPIs, and expected calculations
- Required and protected columns
- Expected date ranges and target variables
- Business rules and referential requirements
- Expected dashboards, visualizations, filters, and output formats

These requirements guide the cleaning and validation stages so the result is fit for its
intended analytical use.

## Testing

Run the backend unit and integration suite:

```powershell
cd backend
.venv\Scripts\python -m pytest
```

Run frontend tests and the browser journey:

```powershell
cd frontend
npm run test
npm run test:e2e
```

The end-to-end journey exercises the real frontend and backend together, including upload,
analysis, dashboard views, and file download.

## Deployment

DataQX deploys as two independent services:

### Backend on Render

The root `render.yaml` defines the web service. It installs `backend/requirements.txt`,
starts Uvicorn, and checks `/health`. Set `DATAQX_CORS_ORIGINS` to the production Vercel
origin or origins.

### Frontend on Vercel

Create a Vercel project with `frontend` as the root directory. Use the Vite preset, run
`npm run build`, and set `VITE_API_BASE_URL` to the deployed Render backend URL.

Deploy the backend first so its URL is available to the frontend configuration.

### Filesystem persistence

The application is designed for stateless runs. Deployment environments with ephemeral
filesystems may remove generated artifacts after a restart or redeploy; download or export
run outputs when they need to be retained externally.

## Security and operational behavior

- Unsafe filenames, path traversal, extension spoofing, and malformed files are rejected or
  handled with user-facing errors.
- Raw exception traces are not returned to clients.
- Basic response hardening headers are applied by the backend.
- Upload size is bounded by `DATAQX_MAX_UPLOAD_MB`.
- No application data is stored in a database.

## Project status

The core platform workflow is implemented and covered by backend, frontend, integration,
stress, security, and browser end-to-end tests. The repository is suitable for local
development and the documented Render/Vercel deployment model.

## License

No open-source license is currently specified for this repository. Contact the project
maintainers before redistributing or using DataQX outside its intended environment.
