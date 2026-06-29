"""ETL and Sandbox Data API endpoints.

Read-only endpoints for browsing dry run results and sandbox import status.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, text
from app.db.postgres import get_db
from app.models.sandbox_models import (
    SandboxImportRun, SandboxClaim, SandboxPerson,
    SandboxPoliticalEntity, SandboxEntityResolutionReview,
)
from app.models.pydantic.models import ETLRunResponse, ETLSandboxStatsResponse

router = APIRouter(prefix="/etl", tags=["etl"])


def _run_to_response(run: SandboxImportRun) -> ETLRunResponse:
    return ETLRunResponse(
        run_id=run.run_id,
        status=run.status,
        adapter=run.adapter,
        commit_sha=run.commit_sha,
        eligible_for_import=run.eligible_for_import,
        records_total=run.records_total,
        started_at=run.started_at.isoformat() if run.started_at else None,
        completed_at=run.completed_at.isoformat() if run.completed_at else None,
    )


@router.get("/runs")
def list_etl_runs(
    db: Session = Depends(get_db),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """List all sandbox import runs (most recent first)."""
    runs = (
        db.query(SandboxImportRun)
        .order_by(SandboxImportRun.started_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    total = db.query(func.count(SandboxImportRun.id)).scalar()
    return {
        "total": total,
        "items": [_run_to_response(r) for r in runs],
    }


@router.get("/runs/{run_id}")
def get_etl_run(run_id: str, db: Session = Depends(get_db)):
    """Get details of a specific sandbox import run."""
    run = db.query(SandboxImportRun).filter(SandboxImportRun.run_id == run_id).first()
    if not run:
        return {"error": "Run not found", "run_id": run_id}
    return _run_to_response(run)


@router.get("/sandbox/stats")
def get_sandbox_stats(db: Session = Depends(get_db)):
    """Get summary statistics of sandbox data."""
    stats = {
        "total_persons": db.query(func.count(SandboxPerson.id)).scalar(),
        "total_committees": db.query(func.count(SandboxPoliticalEntity.id)).scalar(),
        "total_claims": db.query(func.count(SandboxClaim.id)).scalar(),
        "import_runs": db.query(func.count(SandboxImportRun.id)).scalar(),
        "entity_resolution": {
            "safe_match": db.query(func.count(SandboxEntityResolutionReview.id))
                .filter(SandboxEntityResolutionReview.safe_match == True).scalar(),
            "needs_review": db.query(func.count(SandboxEntityResolutionReview.id))
                .filter(SandboxEntityResolutionReview.needs_review == True).scalar(),
        },
        "claim_types": {},
        "data_namespace": "sandbox",
        "data_source": "unitedstates/congress-legislators",
    }

    # Claim type breakdown
    rows = db.execute(text("""
        SELECT claim_type, COUNT(*) as cnt
        FROM sandbox_claims
        GROUP BY claim_type
        ORDER BY cnt DESC
    """)).fetchall()
    stats["claim_types"] = {row[0]: row[1] for row in rows}

    return stats
