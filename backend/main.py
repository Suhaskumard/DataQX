"""DataQX FastAPI entrypoint.

Stateless, file-based backend. No database, no ORM, no persistent server-side session
state. Run `uvicorn main:app --reload` from the backend/ directory to start it locally.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.analyze import router as analyze_router
from app.api.before_after import router as before_after_router
from app.api.clean import router as clean_router
from app.api.dictionary import router as dictionary_router
from app.api.download import router as download_router
from app.api.drift import router as drift_router
from app.api.health import router as health_router
from app.api.issues import router as issues_router
from app.api.lineage import router as lineage_router
from app.api.performance import router as performance_router
from app.api.powerbi import router as powerbi_router
from app.api.quality import router as quality_router
from app.api.report import router as report_router
from app.api.upload import router as upload_router
from app.api.validate import router as validate_router
from app.core.config import get_settings
from app.core.logging import setup_logging
from app.utils.filesystem import ensure_directories

settings = get_settings()

setup_logging()
ensure_directories()

app = FastAPI(title=settings.app_name, version=settings.app_version)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router, prefix="/api")
app.include_router(upload_router, prefix="/api")
app.include_router(analyze_router, prefix="/api")
app.include_router(issues_router, prefix="/api")
app.include_router(clean_router, prefix="/api")
app.include_router(drift_router, prefix="/api")
app.include_router(lineage_router, prefix="/api")
app.include_router(powerbi_router, prefix="/api")
app.include_router(report_router, prefix="/api")
app.include_router(quality_router, prefix="/api")
app.include_router(before_after_router, prefix="/api")
app.include_router(dictionary_router, prefix="/api")
app.include_router(download_router, prefix="/api")
app.include_router(validate_router, prefix="/api")
app.include_router(performance_router, prefix="/api")


@app.get("/health")
def root_health() -> dict:
    """Convenience alias for platform health checks (Render etc.) at the bare path."""
    from app.api.health import health_check

    return health_check()
