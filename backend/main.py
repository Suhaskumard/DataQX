"""DataQX FastAPI entrypoint.

Stateless, file-based backend. No database, no ORM, no persistent server-side session
state. Run `uvicorn main:app --reload` from the backend/ directory to start it locally.
"""

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.analytics_readiness import router as analytics_readiness_router
from app.api.analyze import router as analyze_router
from app.api.audit import router as audit_router
from app.api.before_after import router as before_after_router
from app.api.clean import router as clean_router
from app.api.dictionary import router as dictionary_router
from app.api.download import router as download_router
from app.api.drift import router as drift_router
from app.api.health import router as health_router
from app.api.issues import router as issues_router
from app.api.lineage import router as lineage_router
from app.api.performance import router as performance_router
from app.api.quality import router as quality_router
from app.api.report import router as report_router
from app.api.upload import router as upload_router
from app.api.validate import router as validate_router
from app.core.config import get_settings
from app.core.logging import setup_logging
from app.utils.filesystem import ensure_directories

settings = get_settings()
logger = logging.getLogger(__name__)

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


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """Basic hardening headers on every response (DATAQX.pdf S55)."""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    return response


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Last-resort safety net: never let a raw stack trace reach the client.

    Individual routers already catch and translate expected failures; this exists
    only to guarantee the same friendly-response guarantee for anything they miss.
    """
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "An unexpected error occurred."})

app.include_router(health_router, prefix="/api")
app.include_router(upload_router, prefix="/api")
app.include_router(analyze_router, prefix="/api")
app.include_router(issues_router, prefix="/api")
app.include_router(clean_router, prefix="/api")
app.include_router(audit_router, prefix="/api")
app.include_router(drift_router, prefix="/api")
app.include_router(lineage_router, prefix="/api")
app.include_router(analytics_readiness_router, prefix="/api")
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
