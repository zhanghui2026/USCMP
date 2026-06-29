# 合规检查清单: 美国国会利益关联图谱系统

## 检查清单使用说明

在以下模块完成后必须暂停并逐项自查:
1. 争议与调查记录模块
2. 预测评分模块
3. 真实 ETL Adapter 模块

检查人自填 `[ ]` 未检查 / `[x]` 已通过 / `[!]` 需整改。

---

## A. 诽谤风险 (Defamation Risk)

| # | 检查项 | 状态 | 备注 |
|---|--------|------|------|
| A1 | 争议记录是否区分 allegation / investigation / lawsuit / conviction / correction | [ ] | |
| A2 | 未有法院/监管机构/官方报告确认的事实是否标记为 allegation | [ ] | |
| A3 | 是否避免使用"腐败""被收买""黑料"等主观定性词 | [ ] | |
| A4 | 所有指控是否标注"该记录尚需人工复核" | [ ] | |
| A5 | 是否避免了基于家庭关系的恶意推断 | [ ] | |
| A6 | 系统是否拒绝自动输出未经证据支持的腐败判断 | [ ] | |

## B. 隐私风险 (Privacy Risk)

| # | 检查项 | 状态 | 备注 |
|---|--------|------|------|
| B1 | 是否仅采集公开可获取的 OSINT 数据 | [ ] | |
| B2 | 是否避免了非公开个人信息采集 | [ ] | |
| B3 | Mock 数据是否使用虚构姓名和实体 | [ ] | |
| B4 | 真实数据采集是否遵守 robots.txt | [ ] | |
| B5 | 是否避免了绕过登录/验证码/付费墙 | [ ] | |

## C. 数据授权风险 (Data Authorization Risk)

| # | 检查项 | 状态 | 备注 |
|---|--------|------|------|
| C1 | 每个 ETL Adapter 是否声明 source_name / source_url / license_note | [ ] | |
| C2 | 真实数据是否优先使用官方 API / bulk data / CSV / JSON | [ ] | |
| C3 | 是否避免了高频请求和攻击式代理轮换 | [ ] | |
| C4 | 所有 SourceDocument 是否包含 license_note | [ ] | |
| C5 | 是否避免了未经授权的内容抓取 | [ ] | |

## D. 伪相关风险 (Spurious Correlation Risk)

| # | 检查项 | 状态 | 备注 |
|---|--------|------|------|
| D1 | 低置信度关系（<0.8）是否明确标记 | [ ] | |
| D2 | 低置信度边是否以虚线/低透明度展示 | [ ] | |
| D3 | 关系是否包含置信度分数说明 | [ ] | |
| D4 | 统计相关性是否附带了样本量和数据来源说明 | [ ] | |
| D5 | 是否避免了因果推断（correlation =/= causation） | [ ] | |

## E. 模型偏见风险 (Model Bias Risk)

| # | 检查项 | 状态 | 备注 |
|---|--------|------|------|
| E1 | 预测评分模型是否透明可解释（规则模型） | [ ] | |
| E2 | 是否避免了黑箱模型 | [ ] | |
| E3 | 评分权重是否集中配置在 scoring_weights.yaml | [ ] | |
| E4 | 是否主动寻找反事实证据 | [ ] | |
| E5 | 预测结果是否标注免责声明 | [ ] | |
| E6 | 证据不足时是否返回 unknown 而非强行预测 | [ ] | |
| E7 | 是否避免了基于党派/种族/性别等受保护特征的歧视性评分 | [ ] | |

## F. 证据缺失风险 (Evidence Gap Risk)

| # | 检查项 | 状态 | 备注 |
|---|--------|------|------|
| F1 | 证据不足的关系是否标记 needs_review | [ ] | |
| F2 | 是否明确区分"有证据支持"和"模型推断" | [ ] | |
| F3 | Claim 是否包含原始片段和来源 URL | [ ] | |
| F4 | SourceDocument 是否包含抓取时间和 last_seen_at | [ ] | |
| F5 | 证据链是否完整可追溯（Claim -> SourceDocument） | [ ] | |
| F6 | 每条争议记录是否包含来源和状态 | [ ] | |

## G. 人工复核建议 (Human Review Recommendations)

| # | 检查项 | 状态 | 备注 |
|---|--------|------|------|
| G1 | 是否提供了 needs_review 过滤接口 | [ ] | |
| G2 | 争议记录是否包含"需人工复核"标记 | [ ] | |
| G3 | 实体对齐阈值以下是否标记 needs_review | [ ] | |
| G4 | 是否提供证据审核界面（EvidenceDrawer） | [ ] | |
| G5 | 简报是否包含"该报告需人工审核"提醒 | [ ] | |

## H. 合规用语检查

| # | 禁止用语 | 是否出现 | 替代用语 |
|---|----------|----------|----------|
| H1 | 污点 | [ ] | 争议与调查记录 |
| H2 | 劣迹 | [ ] | 争议与调查记录 |
| H3 | 黑料 | [ ] | 争议与调查记录 |
| H4 | 腐败 | [ ] | 公开资料显示……/根据来源X报道…… |
| H5 | 被收买 | [ ] | 该关系为模型抽取，置信度为…… |
| H6 | 受金主控制 | [ ] | 公开资料显示某组织为其主要捐助方 |

## I. v0.3.0 Sandbox 真实数据接入 (Real Legislators Sandbox)

| # | 检查项 | 状态 | 备注 |
|---|--------|------|------|
| I1 | Sandbox 数据使用独立 namespace(data_namespace=sandbox)，不与 Mock 主图谱合并 | [x] | 所有 sandbox 表 data_namespace="sandbox" |
| I2 | 数据源仅限 CC0-1.0 授权的 unitedstates/congress-legislators | [x] | license_note="CC0-1.0" |
| I3 | 禁止接入 FEC/OpenSecrets/财务披露/Capitol Trades/LDA/新闻抓取 | [x] | 未实现任何金融/游说 adapter |
| I4 | 禁止推断政治献金/股票持仓/游说关系/涉华立场/投票倾向 | [x] | 仅解析 YAML 结构化数据 |
| I5 | Vendor 数据使用 Pinned Commit (dfa962)，禁止直接 GitHub HEAD | [x] | source_manifest.json 含 SHA256 校验 |
| I6 | Dry Run First: 必须先通过 dry_run 校验才能 sandbox 导入 | [x] | eligible_for_sandbox_import 控制 |
| I7 | Prediction 护栏: identity-only/committee-only 证据返回 unknown | [x] | predictions.py 含 identity-only guard |
| I8 | 置信度规则: identity=0.95, term=0.90, committee=0.85, social=0.85 | [x] | 适配器硬编码置信度 |
| I9 | Entity Resolution: 仅 bioguide+govtrack 双 ID 匹配才是 safe_match | [x] | entity_resolution_reviews 含 safe_match 标记 |
| I10 | Claim 提取方式标记为 extraction_method="yaml"(非 LLM/NLP) | [x] | 所有 claims extraction_method="yaml" |
| I11 | 所有 sandbox 表含 source_reliability="secondary" 标记 | [x] | 全部 9 张 sandbox 表均标记 |
| I12 | Schema 变更: Neo4j 关系类型 SERVED_IN_TERM/SERVED_ON_COMMITTEE/HAS_SOCIAL_ACCOUNT 仅在 sandbox namespace | [x] | 通过 data_namespace/sandbox 节点标签隔离 |
| I13 | 前端 data_mode 支持 real_sandbox 显示(区分 mock/mixed/real/real_sandbox) | [x] | App.tsx + DataQualityPage.tsx 均支持 |
| I14 | Data Quality API 返回 sandbox_* 统计字段 | [x] | /api/data-quality/summary 含 sandbox 字段 |

## J. 禁止接入的数据源清单 (v0.3.0-)

| 数据源 | 状态 | 理由 |
|--------|------|------|
| FEC 政治献金数据 | 禁止 | 未经处理直接接入可能产生误导性关联 |
| OpenSecrets 组织/行业数据 | 禁止 | 需经人工分析方可安全使用 |
| 个人财务披露 | 禁止 | 隐私风险高，数据格式复杂 |
| Capitol Trades (股票交易) | 禁止 | 低置信度关系风险，可能产生伪相关 |
| LDA 游说注册/报告 | 禁止 | 数据量大，实体对齐困难 |
| 新闻标题抓取 | 禁止 | 诽谤风险极高，无法保证事实准确性 |
| LLM 实体抽取 | 禁止 | 置信度不可控，幻觉风险 |
| 社交媒体情感分析 | 禁止 | 子意图推断不可靠 |

- 检查人签名: _________
- 检查日期: _________
- 整体结论: [ ] 通过 / [ ] 有条件通过 / [ ] 拒绝通过
- 整改项: ___ 项
- 备注:
