# 评分方法论: 美国国会利益关联图谱系统

> **当前实现状态 (v0.3.x)**: 以下公式和权重体系为设计规格。当前代码实现使用 Mock 演示数据，所有评分为固定基线值（详见代码注释 `source_reliability="mock"`）。真实数据接入后，将按此方法论启用完整评分计算。权重配置文件位于 `backend/app/core/scoring_weights.yaml`。

## 1. 评分模型原则

第一阶段不得训练黑箱模型，不得使用 LLM 直接对真实议员作出确定性政治预测。必须实现可解释规则评分模型。证据不足时返回 `unknown`。

## 2. 核心评分指标

### 2.1 China Hawkishness Index (涉华立场指数, 0-100)

衡量议员对华政策立场的倾向性。100 表示最鹰派（强硬立场），0 表示最鸽派（温和/合作立场）。

**数据来源**:
- 涉华相关投票记录 (VOTED_FOR / VOTED_AGAINST 涉华法案)
- 涉华相关声明 (MADE_STATEMENT 涉华主题)
- 涉华相关委员会任职 (SERVED_ON_COMMITTEE 涉华委员会)
- 涉华相关事件参与 (PARTICIPATED_IN 涉华事件)

**计算公式**:
```
hawkishness_score = (
    hawkish_vote_ratio * 0.35 +
    hawkish_statement_ratio * 0.25 +
    china_committee_score * 0.20 +
    china_event_participation_score * 0.10 +
    donor_china_exposure * 0.10
) * 100
```

### 2.2 Party Alignment Score (党派一致性, 0-100)

衡量议员与所属党派主流立场的吻合程度。100 表示完全一致，0 表示完全背离。

**计算公式**:
```
party_alignment = (
    party_line_vote_ratio * 0.50 +
    party_leadership_support_ratio * 0.20 +
    party_caucus_membership_score * 0.15 +
    party_donor_alignment * 0.15
) * 100
```

### 2.3 Donor Overlap Score (金主重合度, 0-100)

衡量多位议员之间的金主重合程度。

**计算公式**:
```
donor_overlap = (
    jaccard_similarity(contributors_set_a, contributors_set_b) * 0.40 +
    top_donor_overlap_ratio * 0.30 +
    industry_sector_overlap * 0.20 +
    pac_support_overlap * 0.10
) * 100
```

### 2.4 Conflict Risk Score (利益冲突风险, 0-100)

衡量议员个人经济利益与其公共职责之间的潜在冲突程度。

**计算公式**:
```
conflict_risk = (
    stock_committee_overlap * 0.25 +
    lobbying_contribution_ratio * 0.20 +
    revolving_door_indicator * 0.20 +
    family_business_connection * 0.15 +
    undisclosed_relationship_flag * 0.10 +
    vote_against_disclosed_interest * 0.10
) * 100
```

### 2.5 Committee Relevance Score (委员会相关度, 0-100)

衡量议员在委员会中的影响力、资历与某一议题的相关度。

**计算公式**:
```
committee_relevance = (
    committee_jurisdiction_match * 0.30 +
    committee_seniority_score * 0.25 +
    subcommittee_leadership * 0.20 +
    bill_sponsorship_relevance * 0.15 +
    hearing_participation * 0.10
) * 100
```

## 3. 投票预测公式

```
vote_probability = (
    calibrated_party_baseline * W_party +
    issue_alignment_weight * W_issue +
    donor_exposure_weight * W_donor +
    committee_relevance_weight * W_committee +
    historical_behavior_weight * W_history -
    counter_evidence_penalty * W_counter
)
```

其中所有权重集中配置在 `backend/app/core/scoring_weights.yaml`。

### 3.1 各因子说明

| 因子 | 说明 | 数据来源 |
|------|------|----------|
| calibrated_party_baseline | 校准后的党派基线 | 同党派议员历史投票统计 |
| issue_alignment_weight | 议题立场一致性 | 过往相关议题投票 |
| donor_exposure_weight | 金主影响力暴露度 | RECEIVED_CONTRIBUTION 关系 |
| committee_relevance_weight | 委员会相关度 | 委员会任职、专业背景 |
| historical_behavior_weight | 历史行为一致性 | 过往投票模式 |
| counter_evidence_penalty | 反事实证据惩罚 | 特殊行为记录 |

### 3.2 反事实证据搜索

模型必须主动寻找以下反事实证据:
- 持有军工股但投票削减军费
- 接受科技行业捐款但支持监管
- 党派多数支持但个人反对
- 公开表态与投票不一致
- 持有某行业股票但投票支持该行业不利法案
- 接受某组织捐款但投票反对该组织利益

## 4. 默认权重配置 (scoring_weights.yaml)

```yaml
# 投票预测权重
vote_prediction:
  W_party: 0.30
  W_issue: 0.25
  W_donor: 0.20
  W_committee: 0.15
  W_history: 0.15
  W_counter: 0.05

# 涉华立场指数权重
china_hawkishness:
  hawkish_vote_ratio: 0.35
  hawkish_statement_ratio: 0.25
  china_committee_score: 0.20
  china_event_participation_score: 0.10
  donor_china_exposure: 0.10

# 党派一致性权重
party_alignment:
  party_line_vote_ratio: 0.50
  party_leadership_support_ratio: 0.20
  party_caucus_membership_score: 0.15
  party_donor_alignment: 0.15

# 金主重合度权重
donor_overlap:
  jaccard_similarity: 0.40
  top_donor_overlap_ratio: 0.30
  industry_sector_overlap: 0.20
  pac_support_overlap: 0.10

# 利益冲突风险权重
conflict_risk:
  stock_committee_overlap: 0.25
  lobbying_contribution_ratio: 0.20
  revolving_door_indicator: 0.20
  family_business_connection: 0.15
  undisclosed_relationship_flag: 0.10
  vote_against_disclosed_interest: 0.10

# 委员会相关度权重
committee_relevance:
  committee_jurisdiction_match: 0.30
  committee_seniority_score: 0.25
  subcommittee_leadership: 0.20
  bill_sponsorship_relevance: 0.15
  hearing_participation: 0.10

# 阈值配置
thresholds:
  high_confidence: 0.80
  medium_confidence: 0.50
  low_confidence: 0.30
  unknown_threshold: 0.30

# 数据质量阈值
data_quality:
  min_evidence_count_for_prediction: 3
  min_party_baseline_sample: 10
```

## 5. 预测输出规范

每次预测输出必须包含:

```json
{
  "predicted_position": "support" | "oppose" | "unknown",
  "probability": 0.0 - 1.0,
  "confidence_interval": [lower, upper],
  "top_factors": [
    {
      "factor_name": "party_baseline",
      "weight": 0.30,
      "score": 0.85,
      "description": "同党派议员中 85% 投了赞成票"
    }
  ],
  "counter_evidence": [
    {
      "type": "donor_opposition",
      "description": "主要金主 X 公开反对该法案，但该议员历史上 90% 的投票与党派一致",
      "impact": -0.05
    }
  ],
  "evidence_count": 12,
  "data_quality_score": 0.85,
  "disclaimer": "仅供研究参考，不构成事实认定、法律判断或投资建议。该预测基于可解释规则模型，不依赖 LLM 生成。"
}
```

## 6. 证据不足时的处理

当 `evidence_count < data_quality.min_evidence_count_for_prediction` 或 `data_quality_score < thresholds.unknown_threshold` 时:

```json
{
  "predicted_position": "unknown",
  "probability": 0.0,
  "confidence_interval": [0.0, 0.0],
  "top_factors": [],
  "counter_evidence": [],
  "evidence_count": 1,
  "data_quality_score": 0.15,
  "disclaimer": "仅供研究参考，不构成事实认定、法律判断或投资建议。当前证据不足以进行可靠预测。"
}
```
