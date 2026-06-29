"""Member comparison scoring service.

Phase 1: Mock baseline metrics. Real scoring model not yet implemented.
"""

from app.models.sqlalchemy.models import Member
from app.models.pydantic.models import RadarMetric


def compute_radar_metrics(member: Member) -> list[RadarMetric]:
    metrics = []

    # Party alignment: mock baseline
    party_alignment = 50.0
    metrics.append(RadarMetric(
        metric_name="party_alignment", member_id=member.id,
        value=party_alignment,
        source_reliability="mock",
    ))

    # China hawkishness: based on stance summary
    china_score = 50.0
    if member.china_stance_summary:
        china_score += 15.0 if "强硬" in member.china_stance_summary else -10.0
    metrics.append(RadarMetric(
        metric_name="china_hawkishness", member_id=member.id,
        value=max(0.0, min(100.0, china_score)),
    ))

    # Donor exposure: based on top contributors
    donor_score = min(100.0, len(member.top_contributors or []) * 15.0)
    metrics.append(RadarMetric(
        metric_name="donor_exposure", member_id=member.id,
        value=donor_score,
    ))

    # Conflict risk: mock baseline
    conflict = 30.0
    metrics.append(RadarMetric(
        metric_name="conflict_risk", member_id=member.id,
        value=conflict,
        source_reliability="mock",
    ))

    # Committee relevance
    committee_score = min(100.0, len(member.committee_memberships or []) * 20.0)
    metrics.append(RadarMetric(
        metric_name="committee_relevance", member_id=member.id,
        value=committee_score,
    ))

    return metrics
