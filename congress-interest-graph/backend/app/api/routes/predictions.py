"""Prediction API endpoint.

Phase 1: Rule-based scoring only. No LLM, no black-box models.
Returns unknown when evidence is insufficient.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.postgres import get_db
from app.models.sqlalchemy.models import Member, Event as EventModelDB
from app.models.sandbox_models import SandboxClaim
from app.models.pydantic.models import PredictionRequest, PredictionResponse
from app.core.errors import NotFoundError
from app.services.prediction_service import compute_prediction

router = APIRouter(tags=["predictions"])


@router.post("/predictions/vote", response_model=PredictionResponse)
def predict_vote(request: PredictionRequest, db: Session = Depends(get_db)):
    member = db.query(Member).filter(Member.id == request.member_id).first()
    if not member:
        raise NotFoundError("Member not found", {"member_id": request.member_id})

    event = None
    if request.event_id:
        event = db.query(EventModelDB).filter(EventModelDB.id == request.event_id).first()
        if not event:
            raise NotFoundError("Event not found", {"event_id": request.event_id})

    # Identity-only / committee-only evidence guard: if sandbox data exists
    # but lacks term_claim (substantive behavioral data like served-in-term),
    # return unknown. Identity and committee membership alone are insufficient.
    if member.bioguide_id:
        sandbox_person_id = f"uscl_person_{member.bioguide_id}"
        sandbox_claims = db.query(SandboxClaim).filter(
            SandboxClaim.subject_id == sandbox_person_id
        ).all()
        if sandbox_claims:
            claim_types = set(c.claim_type for c in sandbox_claims)
            non_identity = [c for c in sandbox_claims if c.claim_type != "identity_claim"]
            has_term = "term_claim" in claim_types
            if not non_identity or not has_term:
                return PredictionResponse(
                    predicted_position="unknown",
                    probability=0.0,
                    confidence_interval=[0.0, 0.0],
                    top_factors=[],
                    counter_evidence=[],
                    evidence_count=0,
                    data_quality_score=0.0,
                    confidence_level="low",
                    margin_from_baseline=0.0,
                    interpretation="仅有身份或委员会任职声明，无任期记录等实质性行为数据，无法进行有效预测。",
                    disclaimer="仅供研究参考，不构成事实认定、法律判断或投资建议。身份/委员会数据不足以支撑投票行为预测。",
                )

    return compute_prediction(member, event)
