# Project Constitution: 美国国会利益关联图谱系统

## 1. 项目身份

- **项目名称**: 美国国会利益关联图谱系统 (Congress Interest Graph System)
- **项目类型**: 智库级美国政治研究工具
- **核心方法**: OSINT 开源情报分析
- **最高优先级**: 一次性本地可运行闭环

## 2. 核心原则 (五大 First)

### 2.1 Mock-First
- 第一阶段必须使用 Mock 数据完成全链路
- 真实数据采集只能作为可插拔 Adapter，不得阻塞主流程
- 所有 Mock 数据必须明确标记 `source_reliability = "mock"`, `extraction_method = "mock"`

### 2.2 Schema-First
- 所有数据模型必须先定义 Schema 再写代码
- Neo4j Label 使用 PascalCase，关系 Type 使用大写蛇形，属性使用小写蛇形
- PostgreSQL 表字段使用 snake_case
- Pydantic Models 使用 PascalCase

### 2.3 Contract-First
- 所有 API 必须先定义契约再实现
- 前后端类型必须对齐
- API 返回结构必须稳定，使用 Pydantic Strict Mode

### 2.4 Evidence-First
- 所有事实关系必须包含 `claim_id`、`start_date`、`end_date`、`confidence_score`
- Neo4j 关系通过 Claim 节点 + SourceDocument 节点实现证据溯源
- 证据不足时不得展示为事实关系，应标记 `needs_review`
- 所有非结构化抽取关系必须有 Claim、SourceDocument、原文片段、URL、抓取时间、抽取方式、置信度

### 2.5 Compliance-First
- 所有预测结果必须标注"仅供参考，不构成事实认定"
- 所有敏感、争议、调查、指控类信息必须附带原始来源和证据节点
- 系统不得自动生成未经官方、司法、权威媒体或可验证公开文件背书的事实性指控

## 3. 命名规范

| 层级 | 规范 | 示例 |
|------|------|------|
| Neo4j Label | PascalCase | `Person`, `Organization`, `PoliticalEntity` |
| Neo4j 关系 Type | UPPER_SNAKE_CASE | `RECEIVED_CONTRIBUTION`, `SERVED_ON_COMMITTEE` |
| Neo4j 属性 | snake_case | `canonical_name`, `confidence_score` |
| PostgreSQL 表 | snake_case | `members`, `organizations`, `source_documents` |
| PostgreSQL 列 | snake_case | `bioguide_id`, `created_at` |
| Pydantic Models | PascalCase | `MemberSummary`, `GraphResponse` |
| API 端点 | kebab-case | `/api/members/{member_id}/graph` |
| Python 模块 | snake_case | `graph_service.py`, `neo4j.py` |
| React 组件 | PascalCase | `GraphCanvas`, `MemberCard` |
| API 路由前缀 | /api/ | `/api/members` |

## 4. 图查询安全红线

1. Neo4j 多跳查询最大深度为 2
2. expand 懒加载查询最大深度为 1
3. 所有 Cypher 查询必须包含 LIMIT
4. 禁止无限制查询：`MATCH (m)-[*]->(n)`
5. 禁止在 API route 中拼接 Cypher
6. 所有 Cypher 必须集中在 `backend/app/services/graph_service.py`
7. 所有用户输入必须参数化
8. 图查询必须支持 `start_date`、`end_date`、`min_confidence`

## 5. 时间切片红线

1. 所有事实关系必须包含 `start_date`、`end_date`、`confidence_score`、`claim_id`
2. 所有事件和关系必须支持按届次和自定义时间区间过滤
3. 防止 117、118、119 届数据混淆
4. 时间滑块变化必须重新请求图谱 API

## 6. 证据节点红线

1. Neo4j 关系不能直接连接节点，必须采用 `claim_id + Claim + SourceDocument` 模式
2. 所有事实关系必须包含 `claim_id`
3. 模式: `(Person)-[:HOLDS_STOCK { claim_id, ... }]->(Organization)` + `(Claim)-[:EVIDENCED_BY]->(SourceDocument)`
4. 所有非结构化抽取关系必须有 Claim、SourceDocument、原文片段、URL、抓取时间、抽取方式、置信度

## 7. 前端渲染红线

1. 必须使用 AntV G6 WebGL 渲染
2. 节点超过 200 自动 clustering
3. 节点超过 500 拒绝渲染并提示缩小范围
4. 双击节点只能懒加载下一层（depth=1）
5. 低置信度边必须虚线或低透明度
6. 点击边必须能查看证据
7. 时间滑块变化必须重新请求图谱 API

## 8. 合规红线

### 8.1 用词规范
- 不得使用"污点""劣迹""黑料"等主观词
- 统一使用"争议与调查记录 / Controversies & Investigations"
- 争议记录类型必须区分: `allegation`, `investigation`, `lawsuit`, `conviction`, `correction`
- 未经法院、监管机构、官方报告或权威媒体确认，不得标记为事实结论

### 8.2 预测规范
- 预测必须标注: "仅供研究参考，不构成事实认定、法律判断或投资建议"
- 证据不足时返回 `unknown`，不得强行预测

### 8.3 表述规范
- 必须使用: "公开资料显示……"、"根据来源 X 的报道……"、"该记录尚需人工复核……"、"该关系为模型抽取，置信度为……"
- 禁止使用: "此人腐败"、"此人被收买"、"此人一定受金主控制"、"此人有黑料"

### 8.4 争议记录规范
每条必须包含: 类型、来源、URL、发布时间、原文片段、状态、是否官方确认、是否司法确认、是否需要人工复核

## 9. 降级策略

| 故障场景 | 降级行为 |
|----------|---------|
| Neo4j 不可用 | health check 显示 `neo4j: error` |
| PostgreSQL 不可用 | health check 显示 `postgres: error` |
| 真实 ETL Adapter 失败 | 不影响 Mock 链路 |
| LLM API Key 不存在 | 切换 mock / rule-based extractor |
| PDF 生成失败 | 降级为 Markdown |
| 图谱节点 > 200 | 自动 clustering |
| 图谱节点 > 500 | 拒绝渲染 |
| 搜索无结果 | 展示空状态 |
| 证据缺失 | 标记 needs_review，不展示为事实 |
| 预测证据不足 | 返回 unknown |

## 10. 技术架构原则

1. 不得把业务逻辑写在 route 里
2. 不得硬编码数据库密码或 API Key
3. 所有用户输入必须校验
4. 所有返回结构必须稳定
5. 前后端类型必须对齐
6. 代码清晰、模块化
7. 必须提供日志和错误处理
8. docker compose 一键启动
