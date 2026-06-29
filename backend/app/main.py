"""FastAPI application entry point."""

from datetime import datetime, timezone
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from app.core.logging import logger
from app.core.config import settings
from app.core.errors import AppError, ErrorCode
from app.api.routes import (
    health, members, graph, evidence, search, compare, reports, predictions,
    data_quality, data_coverage, etl_runs, finance, finance_summary, holdings,
)

app = FastAPI(
    title="Congress Interest Graph API",
    version="0.1.0",
    description="美国国会利益关联图谱系统 API",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    start = datetime.now(timezone.utc)
    response = await call_next(request)
    duration = (datetime.now(timezone.utc) - start).total_seconds() * 1000
    logger.info(f"{request.method} {request.url.path} -> {response.status_code} ({duration:.1f}ms)")
    return response


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    logger.warning(f"AppError: {exc.error_code} - {exc.message}")
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.to_dict(),
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    import uuid
    request_id = f"req_{uuid.uuid4().hex[:8]}"
    details = []
    for error in exc.errors():
        details.append({
            "field": ".".join(str(loc) for loc in error["loc"]),
            "message": error["msg"],
        })
    return JSONResponse(
        status_code=422,
        content={
            "error_code": ErrorCode.VALIDATION_ERROR,
            "message": "Request validation failed",
            "details": {"errors": details},
            "request_id": request_id,
        },
    )


@app.exception_handler(Exception)
async def general_error_handler(request: Request, exc: Exception):
    import uuid
    logger.error(f"Unhandled error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error_code": ErrorCode.INTERNAL_ERROR,
            "message": "An internal error occurred",
            "details": {},
            "request_id": f"req_{uuid.uuid4().hex[:8]}",
        },
    )


# Register routers
app.include_router(health.router, prefix="/api")
app.include_router(members.router, prefix="/api")
app.include_router(graph.router, prefix="/api")
app.include_router(evidence.router, prefix="/api")
app.include_router(search.router, prefix="/api")
app.include_router(compare.router, prefix="/api")
app.include_router(reports.router, prefix="/api")
app.include_router(predictions.router, prefix="/api")
app.include_router(data_quality.router, prefix="/api")
app.include_router(data_coverage.router, prefix="/api")
app.include_router(etl_runs.router, prefix="/api")
app.include_router(finance.router, prefix="/api")
app.include_router(finance_summary.router, prefix="/api")
app.include_router(holdings.router, prefix="/api")


@app.on_event("startup")
async def startup():
    logger.info("Starting Congress Interest Graph API v0.1.0")
    logger.info(f"Environment: {settings.app_env}")


@app.on_event("shutdown")
async def shutdown():
    from app.db.neo4j import close_driver
    close_driver()
    logger.info("API shutdown complete.")
