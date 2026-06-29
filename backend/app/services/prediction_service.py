"""Explainable rule-based vote prediction service.

Phase 1: Mock baseline scoring. No LLM, no black-box models.
Returns unknown when evidence is insufficient.
"""

from app.models.sqlalchemy.models import Member, Event as EventModelDB
from app.models.pydantic.models import PredictionResponse


def compute_prediction(member: Member, event: EventModelDB | None) -> PredictionResponse:
    evidence_count = 0
    top_factors = []
    counter_evidence = []

    # Factor 1: Party baseline
    party_score = 0.7 if member.party else 0.5
    evidence_count += 1
    party_baseline = 0.50
    top_factors.append({
        "factor_name": "party_baseline",
        "weight": 0.30,
        "score": round(party_score, 2),
        "description": f"党派基线预测值为 {party_score:.0%}",
    })

    # Factor 2: Issue alignment
    issue_score = 0.50
    evidence_count += 1
    top_factors.append({
        "factor_name": "issue_alignment",
        "weight": 0.25,
        "score": round(issue_score, 2),
        "description": "议题立场 (Mock 演示数据，真实分析模型暂未实现)",
    })

    # Factor 3: Donor exposure
    donor_count = len(member.top_contributors or [])
    donor_score = min(0.3, donor_count * 0.05)
    evidence_count += 1
    top_factors.append({
        "factor_name": "donor_exposure",
        "weight": 0.20,
        "score": round(donor_score, 2),
        "description": f"来源自 {donor_count} 个金主的数据 (Mock 演示数据)",
    })

    # Factor 4: Committee relevance
    committee_count = len(member.committee_memberships or [])
    committee_score = min(0.4, committee_count * 0.08)
    evidence_count += 1
    top_factors.append({
        "factor_name": "committee_relevance",
        "weight": 0.15,
        "score": round(committee_score, 2),
        "description": f"与 {committee_count} 个委员会的相关度分析",
    })

    # Factor 5: Historical behavior
    hist_score = 0.50
    evidence_count += 1
    top_factors.append({
        "factor_name": "historical_behavior",
        "weight": 0.15,
        "score": round(hist_score, 2),
        "description": "历史投票模式 (Mock 演示数据，真实分析模型暂未实现)",
    })

    # Counter evidence: check for controversies
    if member.controversies and len(member.controversies) > 0:
        counter_evidence.append({
            "type": "controversy_flag",
            "description": f"存在 {len(member.controversies)} 条争议记录，可能影响投票决策",
            "impact": -0.05,
        })

    # Counter evidence: check for conflicting committee memberships
    if committee_count > 4:
        counter_evidence.append({
            "type": "committee_overlap",
            "description": "委员会任职较多，议题立场可能存在内部冲突",
            "impact": -0.03,
        })

    # Compute final probability
    weights = [0.30, 0.25, 0.20, 0.15, 0.15]
    scores = [party_score, issue_score, donor_score, committee_score, hist_score]
    probability = sum(w * s for w, s in zip(weights, scores))

    for ce in counter_evidence:
        probability += ce["impact"]

    probability = max(0.0, min(1.0, probability))

    data_quality_score = min(1.0, evidence_count / 5.0)
    margin_from_baseline = abs(probability - party_baseline)

    # Threshold: evidence_count < 3 OR data_quality_score < 0.6 -> unknown
    if evidence_count < 3 or data_quality_score < 0.6:
        return PredictionResponse(
            predicted_position="unknown",
            probability=0.0,
            confidence_interval=[0.0, 0.0],
            top_factors=top_factors,
            counter_evidence=counter_evidence,
            evidence_count=evidence_count,
            data_quality_score=data_quality_score,
            confidence_level="insufficient_data",
            margin_from_baseline=round(margin_from_baseline, 4),
            interpretation="证据不足，无法进行可靠预测。需要至少3条证据且数据质量评分达到0.6以上。",
            disclaimer="仅供研究参考，不构成事实认定、法律判断或投资建议。当前证据不足以进行可靠预测。",
        )

    position = "support" if probability > 0.5 else "oppose"
    margin = 0.08
    ci_low = max(0.0, probability - margin)
    ci_high = min(1.0, probability + margin)

    # Determine confidence_level
    if 0.45 <= probability <= 0.55:
        confidence_level = "low"
        position = "uncertain"
    elif probability > 0.80 or probability < 0.20:
        confidence_level = "high"
    elif probability > 0.60 or probability < 0.40:
        confidence_level = "medium"
    else:
        confidence_level = "low"

    # Generate interpretation
    if 0.45 <= probability <= 0.55:
        interpretation = f"预测概率在45%-55%范围内（当前{probability:.1%}），置信度较低。立场接近中立，建议谨慎解读。"
    elif confidence_level == "high":
        direction = "支持" if position == "support" else "反对"
        interpretation = f"预测置信度为高，{direction}概率{probability:.1%}。当前证据较充分，但该预测仅基于Mock数据。"
    else:
        direction = "倾向于支持" if position == "support" else "倾向于反对"
        interpretation = f"预测置信度为中等，{direction}（概率{probability:.1%}）。证据尚可但仍有不确定性。"

    return PredictionResponse(
        predicted_position=position,
        probability=round(probability, 4),
        confidence_interval=[round(ci_low, 4), round(ci_high, 4)],
        top_factors=top_factors,
        counter_evidence=counter_evidence,
        evidence_count=evidence_count,
        data_quality_score=round(data_quality_score, 2),
        confidence_level=confidence_level,
        margin_from_baseline=round(margin_from_baseline, 4),
        interpretation=interpretation,
        disclaimer="仅供研究参考，不构成事实认定、法律判断或投资建议。当前预测基于 Mock 演示数据，不代表真实投票行为分析。",
    )
