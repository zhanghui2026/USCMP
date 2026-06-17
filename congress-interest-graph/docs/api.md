# API 契约文档: 美国国会利益关联图谱系统

## 基础信息

- **Base URL**: `http://localhost:8000/api`
- **Content-Type**: `application/json`
- **OpenAPI Docs**: `http://localhost:8000/docs`
- **所有时间字段**: ISO 8601 格式 (`YYYY-MM-DDTHH:MM:SSZ`)
- **所有日期字段**: ISO 8601 格式 (`YYYY-MM-DD`)

## 统一错误响应格式

```json
{
  "error_code": "ERROR_CODE",
  "message": "Human-readable error message",
  "details": {},
  "request_id": "req_xxx"
}
```

### 错误码列表

| error_code | HTTP Status | 说明 |
|------------|-------------|------|
| VALIDATION_ERROR | 422 | 请求参数校验失败 |
| NOT_FOUND | 404 | 资源不存在 |
| GRAPH_QUERY_TOO_LARGE | 400 | 图谱查询结果过大 |
| GRAPH_DEPTH_EXCEEDED | 400 | 查询深度超限 |
| SEARCH_QUERY_TOO_SHORT | 400 | 搜索关键词过短 |
| COMPARE_TOO_FEW_MEMBERS | 400 | 对比人数不足 |
| PREDICTION_INSUFFICIENT_DATA | 200 | 预测证据不足(返回 unknown) |
| INTERNAL_ERROR | 500 | 服务器内部错误 |
| SERVICE_UNAVAILABLE | 503 | 后端服务不可用 |

## API 端点

### 1. Health Check

```
GET /api/health
```

**Response (200)**:
```json
{
  "status": "ok",
  "postgres": "ok",
  "neo4j": "ok",
  "data_mode": "mock",
  "version": "0.1.0",
  "timestamp": "2025-06-16T12:00:00Z"
}
```

**Response (503)**:
```json
{
  "status": "degraded",
  "postgres": "error",
  "neo4j": "ok",
  "data_mode": "unknown",
  "version": "0.1.0",
  "timestamp": "2025-06-16T12:00:00Z"
}
```

### 2. 议员列表

```
GET /api/members
```

**Query Parameters**:
| 参数 | 类型 | 必需 | 默认值 | 说明 |
|------|------|------|--------|------|
| chamber | string | No | - | senate, house |
| party | string | No | - | Democratic, Republican, Independent |
| state | string | No | - | 2-letter state code |
| committee | string | No | - | Committee name (fuzzy match) |
| congress | integer | No | - | 117, 118, 119 |
| search | string | No | - | Name search |
| skip | integer | No | 0 | Pagination offset |
| limit | integer | No | 50 (max 200) | Pagination limit |

**Response (200)**:
```json
{
  "members": [
    {
      "id": "person_001",
      "canonical_name": "John Smith",
      "display_name": "Sen. John Smith",
      "party": "Democratic",
      "chamber": "senate",
      "state": "CA",
      "district": null,
      "official_photo_url": null,
      "committee_tags": ["Foreign Relations", "Armed Services"],
      "congress": 119
    }
  ],
  "total": 50,
  "skip": 0,
  "limit": 50
}
```

### 3. 议员详情

```
GET /api/members/{member_id}
```

**Path Parameters**:
| 参数 | 类型 | 说明 |
|------|------|------|
| member_id | string | 议员唯一ID |

**Response (200)**: `MemberDetail` object (详见 Schema 文档)

**Response (404)**:
```json
{
  "error_code": "NOT_FOUND",
  "message": "Member not found",
  "details": {"member_id": "person_999"},
  "request_id": "req_xxx"
}
```

### 4. 议员图谱

```
GET /api/members/{member_id}/graph
```

**Query Parameters**:
| 参数 | 类型 | 必需 | 默认值 | 说明 |
|------|------|------|--------|------|
| depth | integer | No | 2 (max 2) | 查询深度 |
| start_date | date | No | - | 过滤 start_date >= 此日期的关系 |
| end_date | date | No | - | 过滤 end_date <= 此日期的关系 |
| min_confidence | float | No | 0.0 (0.0-1.0) | 最低置信度 |
| limit | integer | No | 200 (max 500) | 节点数量限制 |

**时间过滤说明**: 缺少 `start_date` 的关系不受起始日期过滤影响；缺少 `end_date` (进行中的关系) 不受结束日期过滤影响。

**Response (200)**: `GraphResponse` object

**Response (400)**:
```json
{
  "error_code": "GRAPH_DEPTH_EXCEEDED",
  "message": "Graph query depth exceeds maximum allowed depth of 2",
  "details": {"requested_depth": 5, "max_depth": 2},
  "request_id": "req_xxx"
}
```

### 5. 图谱展开（懒加载）

```
POST /api/graph/expand
```

**Request Body**:
```json
{
  "node_id": "person_001",
  "depth": 1,
  "start_date": "2024-01-01",
  "end_date": "2025-01-01",
  "min_confidence": 0.5,
  "limit": 200
}
```

**约束**: `depth` 固定为 1，不可超过；`limit` 最大 500。时间过滤行为与议员图谱端点一致。

**Response (200)**: `GraphResponse` object (仅返回新增的节点和边)

### 6. 证据查询

```
GET /api/evidence/{claim_id}
```

**Path Parameters**:
| 参数 | 类型 | 说明 |
|------|------|------|
| claim_id | string | Claim 唯一ID |

**Response (200)**: `EvidenceResponse` object

### 7. 全局搜索

```
GET /api/search
```

**Query Parameters**:
| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| query | string | Yes (min 2 chars) | 搜索关键词 |
| limit | integer | No (default 50, max 100) | 结果数量 |

**说明**: 当前搜索为 PostgreSQL ILIKE 关键词匹配，覆盖 members 的 canonical_name/display_name/state、organizations 的 canonical_name/industry、events 的 title。更多搜索能力（Neo4j 图搜索、按组织/行业分类搜索、日期过滤）在后续版本实现。

**Response (200)**: `SearchResult` object
```json
{
  "members": [...],
  "organizations": [...],
  "events": [...],
  "total_count": 15,
  "source": "postgresql"
}
```

**Response (400)**:
```json
{
  "error_code": "SEARCH_QUERY_TOO_SHORT",
  "message": "Search query must be at least 2 characters",
  "details": {"query": "a", "min_length": 2},
  "request_id": "req_xxx"
}
```

### 8. 多人对比

```
POST /api/compare
```

**Request Body**:
```json
{
  "member_ids": ["person_001", "person_002", "person_003"],
  "start_date": "2024-01-01",
  "end_date": "2025-01-01"
}
```

**约束**: `member_ids` 至少 2 个，最多 10 个。

**Response (200)**: `CompareResponse` object

**Response (400)**:
```json
{
  "error_code": "COMPARE_TOO_FEW_MEMBERS",
  "message": "At least 2 members required for comparison",
  "details": {"member_count": 1, "min_required": 2},
  "request_id": "req_xxx"
}
```

### 9. Markdown 简报导出

```
POST /api/reports/markdown
```

**Request Body**:
```json
{
  "member_id": "person_001",
  "format": "markdown",
  "include_graph": true,
  "include_predictions": true
}
```

**Response (200)**: `ReportResponse` object

### 10. 预测投票

```
POST /api/predictions/vote
```

**Request Body**:
```json
{
  "member_id": "person_001",
  "event_id": "event_001",
  "event_type": "bill"
}
```

**Response (200)**:
- 证据充足时返回预测结果 (predicted_position: "support" 或 "oppose")
- 证据不足时返回:
```json
{
  "predicted_position": "unknown",
  "probability": 0.0,
  "confidence_interval": [0.0, 0.0],
  "top_factors": [],
  "counter_evidence": [],
  "evidence_count": 0,
  "data_quality_score": 0.0,
  "disclaimer": "仅供研究参考，不构成事实认定、法律判断或投资建议。当前证据不足以进行可靠预测。"
}
```

## 通用响应头

| Header | 值 | 说明 |
|--------|-----|------|
| X-Request-ID | req_xxx | 请求唯一跟踪 ID |
| X-Response-Time | 45ms | 服务端响应时间 |
| Content-Type | application/json | 响应内容类型 |
