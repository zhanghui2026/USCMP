"""Report/Markdown export endpoint."""

from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.postgres import get_db
from app.models.sqlalchemy.models import Member
from app.models.pydantic.models import ReportRequest, ReportResponse
from app.core.errors import NotFoundError
from app.services.report_service import build_markdown
from app.api.routes.member_visibility import visible_member_filter

router = APIRouter(tags=["reports"])


@router.post("/reports/markdown", response_model=ReportResponse)
def generate_markdown_report(request: ReportRequest, db: Session = Depends(get_db)):
    member = db.query(Member).filter(Member.id == request.member_id, visible_member_filter()).first()
    if not member:
        raise NotFoundError("Member not found", {"member_id": request.member_id})

    content = build_markdown(member, request.include_graph, request.include_predictions)

    if member.source != "mock":
        disclaimer = "仅供研究参考，不构成事实认定、法律判断或投资建议。数据来源: unitedstates/congress-legislators (CC0-1.0)。"
    else:
        disclaimer = "仅供研究参考，不构成事实认定、法律判断或投资建议。所有数据为 Mock 生成。"

    return ReportResponse(
        format="markdown",
        content=content,
        generated_at=datetime.now(timezone.utc),
        disclaimer=disclaimer,
    )
