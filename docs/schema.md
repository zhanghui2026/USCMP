# Schema 文档: 美国国会利益关联图谱系统

## 1. Neo4j Graph Schema

### 1.1 节点类型

#### Person
```
Label: Person
Fields:
  - id: String (unique, required)
  - canonical_name: String (unique, indexed, required)
  - display_name: String (required)
  - aliases: List[String] (default [])
  - person_type: String (required)  # senator, representative, staffer, family, political_figure
  - party: String  # Democratic, Republican, Independent
  - chamber: String  # senate, house
  - state: String  # 2-letter code
  - district: String?
  - official_photo_url: String?
  - bioguide_id: String?
  - govtrack_id: String?
  - fec_candidate_id: String?
  - opensecrets_id: String?
  - created_at: DateTime (required)
  - updated_at: DateTime (required)
```

#### Organization
```
Label: Organization
Fields:
  - id: String (unique, required)
  - canonical_name: String (unique, indexed, required)
  - display_name: String (required)
  - aliases: List[String] (default [])
  - entity_type: String (required)  # corporation, pac, super_pac, think_tank, lobbying_firm, shell_company, trade_association, nonprofit
  - industry: String
  - ticker: String?
  - country: String (default "US")
  - created_at: DateTime (required)
  - updated_at: DateTime (required)
```

#### PoliticalEntity
```
Label: PoliticalEntity
Fields:
  - id: String (unique, required)
  - name: String (unique, indexed, required)
  - entity_type: String (required)  # senate, house, committee, subcommittee, state, district, caucus
  - chamber: String?  # senate, house
  - state: String?  # 2-letter code
  - congress: Integer?  # 117, 118, 119
  - created_at: DateTime (required)
  - updated_at: DateTime (required)
```

#### Event
```
Label: Event
Fields:
  - id: String (unique, required)
  - event_type: String (required)  # bill, vote, hearing, stock_trade, donation, lobbying_disclosure, controversy, news
  - title: String (required)
  - description: String?
  - event_date: Date (indexed, required)
  - congress: Integer?  # 117, 118, 119
  - source_reliability: String (default "mock")  # mock, official, verified_media, unverified
  - created_at: DateTime (required)
  - updated_at: DateTime (required)
```

#### Claim
```
Label: Claim
Fields:
  - claim_id: String (unique, indexed, required)
  - claim_type: String (required)  # financial, social, political, event_participation
  - subject_id: String (required)  # reference to source node id
  - object_id: String (required)  # reference to target node id
  - relation_type: String (required)  # e.g. HOLDS_STOCK, RECEIVED_CONTRIBUTION
  - claim_text: String (required)
  - original_snippet: String
  - confidence_score: Float (indexed, required, range: 0.0-1.0)
  - extraction_method: String (default "mock")  # mock, rule_based, llm
  - source_reliability: String (default "mock")  # mock, official, verified_media, unverified
  - review_status: String (default "unreviewed")  # unreviewed, needs_review, reviewed_approved, reviewed_rejected
  - created_at: DateTime (required)
  - updated_at: DateTime (required)
```

#### SourceDocument
```
Label: SourceDocument
Fields:
  - id: String (unique, required)
  - source_name: String (required)
  - source_url: String
  - title: String
  - publisher: String
  - published_at: DateTime
  - collected_at: DateTime
  - last_seen_at: DateTime
  - document_type: String  # financial_disclosure, campaign_finance, news_article, lobbyist_disclosure, gov_record
  - raw_text_hash: String
  - snippet: String
  - source_reliability: String (default "mock")  # mock, official, verified_media, unverified
  - license_note: String
  - created_at: DateTime (required)
  - updated_at: DateTime (required)
```

### 1.2 关系类型

#### 资金流 (Financial Flow)
```
RECEIVED_CONTRIBUTION (Person -> Organization)
  Properties: claim_id, start_date, end_date, confidence_score, source_type, amount_min, amount_max, congress, created_at, updated_at

HOLDS_STOCK (Person -> Organization)
  Properties: claim_id, start_date, end_date, confidence_score, source_type, amount_min, amount_max, ticker, created_at, updated_at

RECEIVED_LOBBYING_SUPPORT (Person -> Organization)
  Properties: claim_id, start_date, end_date, confidence_score, source_type, amount_min, amount_max, congress, created_at, updated_at
```

#### 社会流 (Social Flow)
```
ALUMNI_OF (Person -> Organization)
  Properties: claim_id, start_date, end_date, confidence_score, source_type, position, created_at, updated_at

RELATED_TO (Person -> Person)
  Properties: claim_id, start_date, end_date, confidence_score, source_type, relation_type, created_at, updated_at

FORMER_EMPLOYER (Person -> Organization)
  Properties: claim_id, start_date, end_date, confidence_score, source_type, position, created_at, updated_at

FUTURE_EMPLOYER (Person -> Organization)
  Properties: claim_id, start_date, end_date, confidence_score, source_type, expected_position, created_at, updated_at
```

#### 政治流 (Political Flow)
```
SPONSORED_BILL (Person -> Event)
  Properties: claim_id, start_date, end_date, confidence_score, source_type, bill_number, created_at, updated_at

COSPONSORED_BILL (Person -> Event)
  Properties: claim_id, start_date, end_date, confidence_score, source_type, bill_number, created_at, updated_at

VOTED_FOR (Person -> Event)
  Properties: claim_id, start_date, end_date, confidence_score, source_type, bill_number, created_at, updated_at

VOTED_AGAINST (Person -> Event)
  Properties: claim_id, start_date, end_date, confidence_score, source_type, bill_number, created_at, updated_at

SERVED_ON_COMMITTEE (Person -> PoliticalEntity)
  Properties: claim_id, start_date, end_date, confidence_score, source_type, role, congress, created_at, updated_at

MADE_STATEMENT (Person -> Event)
  Properties: claim_id, start_date, end_date, confidence_score, source_type, statement_url, created_at, updated_at
```

#### 事件流 (Event Flow)
```
PARTICIPATED_IN (Person -> Event)
  Properties: claim_id, start_date, end_date, confidence_score, source_type, role, created_at, updated_at

ASSOCIATED_WITH_EVENT (Person -> Event)
  Properties: claim_id, start_date, end_date, confidence_score, source_type, association_type, created_at, updated_at
```

#### 证据流 (Evidence Flow)
```
HAS_CLAIM (Node -> Claim)
  Properties: created_at, updated_at

EVIDENCED_BY (Claim -> SourceDocument)
  Properties: created_at, updated_at
```

### 1.3 Neo4j 约束与索引

```cypher
// 唯一约束
CREATE CONSTRAINT person_id_unique IF NOT EXISTS FOR (n:Person) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT person_canonical_name_unique IF NOT EXISTS FOR (n:Person) REQUIRE n.canonical_name IS UNIQUE;
CREATE CONSTRAINT org_id_unique IF NOT EXISTS FOR (n:Organization) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT org_canonical_name_unique IF NOT EXISTS FOR (n:Organization) REQUIRE n.canonical_name IS UNIQUE;
CREATE CONSTRAINT pol_entity_id_unique IF NOT EXISTS FOR (n:PoliticalEntity) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT pol_entity_name_unique IF NOT EXISTS FOR (n:PoliticalEntity) REQUIRE n.name IS UNIQUE;
CREATE CONSTRAINT event_id_unique IF NOT EXISTS FOR (n:Event) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT claim_id_unique IF NOT EXISTS FOR (n:Claim) REQUIRE n.claim_id IS UNIQUE;
CREATE CONSTRAINT source_doc_id_unique IF NOT EXISTS FOR (n:SourceDocument) REQUIRE n.id IS UNIQUE;

// 索引
CREATE INDEX person_name_idx IF NOT EXISTS FOR (n:Person) ON (n.canonical_name);
CREATE INDEX org_name_idx IF NOT EXISTS FOR (n:Organization) ON (n.canonical_name);
CREATE INDEX pol_entity_name_idx IF NOT EXISTS FOR (n:PoliticalEntity) ON (n.name);
CREATE INDEX event_date_idx IF NOT EXISTS FOR (n:Event) ON (n.event_date);
CREATE INDEX claim_id_idx IF NOT EXISTS FOR (n:Claim) ON (n.claim_id);
CREATE INDEX confidence_score_idx IF NOT EXISTS FOR (n:Claim) ON (n.confidence_score);
```

### 1.4 边颜色映射

| 关系类型 | 颜色 | CSS Color |
|----------|------|-----------|
| RECEIVED_CONTRIBUTION | 绿色 | #52c41a |
| HOLDS_STOCK | 绿色 | #73d13d |
| RECEIVED_LOBBYING_SUPPORT | 绿色 | #95de64 |
| ALUMNI_OF | 蓝色 | #1890ff |
| RELATED_TO | 蓝色 | #40a9ff |
| FORMER_EMPLOYER | 蓝色 | #69c0ff |
| FUTURE_EMPLOYER | 蓝色 | #91d5ff |
| SPONSORED_BILL | 红色 | #f5222d |
| COSPONSORED_BILL | 红色 | #ff4d4f |
| VOTED_FOR | 红色 | #ff7875 |
| VOTED_AGAINST | 红色 | #ffa39e |
| SERVED_ON_COMMITTEE | 红色 | #ff4d4f |
| MADE_STATEMENT | 红色 | #ff7875 |
| PARTICIPATED_IN | 黄色 | #faad14 |
| ASSOCIATED_WITH_EVENT | 黄色 | #ffc53d |
| HAS_CLAIM | 灰色 | #d9d9d9 |
| EVIDENCED_BY | 灰色 | #d9d9d9 |

### 1.5 节点样式映射

| Label | 形状 | 颜色 |
|-------|------|------|
| Person | circle (头像) | #1890ff |
| Organization | rect (圆角矩形) | #722ed1 |
| PoliticalEntity | diamond (菱形) | #eb2f96 |
| Event | hexagon (六边形) | #fa8c16 |
| Claim | dot (小圆点) | #8c8c8c |
| SourceDocument | document icon | #595959 |

## 2. PostgreSQL Schema

### 2.1 表定义

#### members
```sql
CREATE TABLE members (
    id VARCHAR PRIMARY KEY,
    canonical_name VARCHAR NOT NULL,
    display_name VARCHAR NOT NULL,
    aliases JSONB DEFAULT '[]',
    person_type VARCHAR NOT NULL,
    party VARCHAR,
    chamber VARCHAR,
    state VARCHAR(2),
    district VARCHAR,
    official_photo_url VARCHAR,
    bioguide_id VARCHAR,
    govtrack_id VARCHAR,
    fec_candidate_id VARCHAR,
    opensecrets_id VARCHAR,
    top_contributors JSONB DEFAULT '[]',
    top_holdings JSONB DEFAULT '[]',
    committee_memberships JSONB DEFAULT '[]',
    career_summary JSONB DEFAULT '[]',
    china_stance_summary TEXT,
    controversies JSONB DEFAULT '[]',
    source_reliability VARCHAR DEFAULT 'mock',
    extraction_method VARCHAR DEFAULT 'mock',
    congress INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_members_canonical_name ON members(canonical_name);
CREATE INDEX idx_members_party ON members(party);
CREATE INDEX idx_members_chamber ON members(chamber);
CREATE INDEX idx_members_state ON members(state);
CREATE INDEX idx_members_congress ON members(congress);
```

#### organizations
```sql
CREATE TABLE organizations (
    id VARCHAR PRIMARY KEY,
    canonical_name VARCHAR NOT NULL,
    display_name VARCHAR NOT NULL,
    aliases JSONB DEFAULT '[]',
    entity_type VARCHAR NOT NULL,
    industry VARCHAR,
    ticker VARCHAR,
    country VARCHAR DEFAULT 'US',
    source_reliability VARCHAR DEFAULT 'mock',
    extraction_method VARCHAR DEFAULT 'mock',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_orgs_canonical_name ON organizations(canonical_name);
CREATE INDEX idx_orgs_entity_type ON organizations(entity_type);
CREATE INDEX idx_orgs_industry ON organizations(industry);
```

#### source_documents
```sql
CREATE TABLE source_documents (
    id VARCHAR PRIMARY KEY,
    source_name VARCHAR NOT NULL,
    source_url VARCHAR,
    title VARCHAR,
    publisher VARCHAR,
    published_at TIMESTAMP WITH TIME ZONE,
    collected_at TIMESTAMP WITH TIME ZONE,
    last_seen_at TIMESTAMP WITH TIME ZONE,
    document_type VARCHAR,
    raw_text_hash VARCHAR,
    snippet TEXT,
    source_reliability VARCHAR DEFAULT 'mock',
    license_note VARCHAR,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_sdocs_source_name ON source_documents(source_name);
CREATE INDEX idx_sdocs_document_type ON source_documents(document_type);
```

#### events
```sql
CREATE TABLE events (
    id VARCHAR PRIMARY KEY,
    event_type VARCHAR NOT NULL,
    title VARCHAR NOT NULL,
    description TEXT,
    event_date DATE NOT NULL,
    congress INTEGER,
    source_reliability VARCHAR DEFAULT 'mock',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_events_event_date ON events(event_date);
CREATE INDEX idx_events_congress ON events(congress);
CREATE INDEX idx_events_event_type ON events(event_type);
```

#### claims
```sql
CREATE TABLE claims (
    claim_id VARCHAR PRIMARY KEY,
    claim_type VARCHAR NOT NULL,
    subject_id VARCHAR NOT NULL,
    object_id VARCHAR NOT NULL,
    relation_type VARCHAR NOT NULL,
    claim_text TEXT NOT NULL,
    original_snippet TEXT,
    confidence_score FLOAT NOT NULL DEFAULT 0.5,
    extraction_method VARCHAR DEFAULT 'mock',
    source_reliability VARCHAR DEFAULT 'mock',
    review_status VARCHAR DEFAULT 'unreviewed',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_claims_subject_id ON claims(subject_id);
CREATE INDEX idx_claims_object_id ON claims(object_id);
CREATE INDEX idx_claims_relation_type ON claims(relation_type);
CREATE INDEX idx_claims_confidence ON claims(confidence_score);
```

#### etl_sources
```sql
CREATE TABLE etl_sources (
    id SERIAL PRIMARY KEY,
    source_name VARCHAR NOT NULL,
    source_url VARCHAR,
    license_note VARCHAR,
    robots_policy_note VARCHAR,
    rate_limit VARCHAR,
    supports_incremental BOOLEAN DEFAULT false,
    last_updated_at TIMESTAMP WITH TIME ZONE,
    data_freshness_window VARCHAR,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

#### api_request_logs
```sql
CREATE TABLE api_request_logs (
    id SERIAL PRIMARY KEY,
    request_id VARCHAR NOT NULL,
    endpoint VARCHAR NOT NULL,
    method VARCHAR NOT NULL,
    status_code INTEGER,
    duration_ms FLOAT,
    ip_address VARCHAR,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_api_logs_request_id ON api_request_logs(request_id);
CREATE INDEX idx_api_logs_created_at ON api_request_logs(created_at);
```

#### mock_seed_manifest
```sql
CREATE TABLE mock_seed_manifest (
    id SERIAL PRIMARY KEY,
    seed_version VARCHAR NOT NULL,
    entity_type VARCHAR NOT NULL,
    entity_count INTEGER NOT NULL,
    seed_timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

## 3. Pydantic Models

### 3.1 共享模型

```python
class ApiError(BaseModel):
    error_code: str
    message: str
    details: dict = {}
    request_id: str

class PredictionRequest(BaseModel):
    member_id: str
    event_id: Optional[str] = None
    event_type: Optional[str] = None

class PredictionResponse(BaseModel):
    predicted_position: str  # support, oppose, unknown
    probability: float  # 0.0 - 1.0
    confidence_interval: tuple[float, float]
    top_factors: list[dict]
    counter_evidence: list[dict]
    evidence_count: int
    data_quality_score: float  # 0.0 - 1.0
    disclaimer: str
```

### 3.2 议员模型

```python
class MemberSummary(BaseModel):
    id: str
    canonical_name: str
    display_name: str
    party: Optional[str]
    chamber: Optional[str]
    state: Optional[str]
    district: Optional[str]
    official_photo_url: Optional[str]
    committee_tags: list[str] = []
    congress: Optional[int]

class MemberDetail(BaseModel):
    id: str
    canonical_name: str
    display_name: str
    aliases: list[str] = []
    person_type: str
    party: Optional[str]
    chamber: Optional[str]
    state: Optional[str]
    district: Optional[str]
    official_photo_url: Optional[str]
    bioguide_id: Optional[str]
    govtrack_id: Optional[str]
    fec_candidate_id: Optional[str]
    opensecrets_id: Optional[str]
    top_contributors: list[dict] = []
    top_holdings: list[dict] = []
    committee_memberships: list[dict] = []
    career_summary: list[dict] = []
    china_stance_summary: Optional[str]
    controversies: list[dict] = []
    congress: Optional[int]
```

### 3.3 组织/实体/事件模型

```python
class OrganizationSummary(BaseModel):
    id: str
    canonical_name: str
    display_name: str
    entity_type: str
    industry: Optional[str]
    ticker: Optional[str]
    country: Optional[str]

class PoliticalEntityModel(BaseModel):
    id: str
    name: str
    entity_type: str
    chamber: Optional[str]
    state: Optional[str]
    congress: Optional[int]

class EventModel(BaseModel):
    id: str
    event_type: str
    title: str
    description: Optional[str]
    event_date: date
    congress: Optional[int]
    source_reliability: str = "mock"
```

### 3.4 图谱模型

```python
class GraphNode(BaseModel):
    id: str
    label: str  # Person, Organization, PoliticalEntity, Event, Claim, SourceDocument
    properties: dict

class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    type: str  # relation type
    properties: dict
    claim_id: Optional[str]
    confidence_score: Optional[float]
    start_date: Optional[date]
    end_date: Optional[date]

class GraphResponse(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    total_node_count: int
    truncated: bool = False

class GraphExpandRequest(BaseModel):
    node_id: str
    depth: int = 1
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    min_confidence: float = 0.0
    limit: int = 200
```

class GraphQueryParams(BaseModel):
    member_id: str
    depth: int = 2
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    min_confidence: float = 0.0
    limit: int = 200
```

### 3.5 证据模型

```python
class ClaimModel(BaseModel):
    claim_id: str
    claim_type: str
    subject_id: str
    object_id: str
    relation_type: str
    claim_text: str
    original_snippet: Optional[str]
    confidence_score: float
    extraction_method: str
    source_reliability: str
    review_status: str

class SourceDocumentModel(BaseModel):
    id: str
    source_name: str
    source_url: Optional[str]
    title: Optional[str]
    publisher: Optional[str]
    published_at: Optional[datetime]
    collected_at: Optional[datetime]
    document_type: Optional[str]
    snippet: Optional[str]
    source_reliability: str
    license_note: Optional[str]

class EvidenceResponse(BaseModel):
    claim: ClaimModel
    source_documents: list[SourceDocumentModel]
```

### 3.6 搜索与对比模型

```python
class SearchResult(BaseModel):
    members: list[MemberSummary] = []
    organizations: list[OrganizationSummary] = []
    events: list[EventModel] = []
    total_count: int
    source: str = "postgresql"

class CompareRequest(BaseModel):
    member_ids: list[str]  # min 2
    start_date: Optional[date] = None
    end_date: Optional[date] = None

class RadarMetric(BaseModel):
    metric_name: str
    member_id: str
    value: float  # 0-100

class CompareResponse(BaseModel):
    members: list[MemberDetail]
    radar_metrics: list[RadarMetric]
    common_donors: list[dict] = []
    common_committees: list[dict] = []
    opposing_votes: list[dict] = []
    disclaimer: str
```

### 3.7 报告模型

```python
class ReportRequest(BaseModel):
    member_id: str
    format: str = "markdown"  # markdown, pdf (reserved)
    include_graph: bool = True
    include_predictions: bool = True

class ReportResponse(BaseModel):
    format: str
    content: str  # markdown content
    generated_at: datetime
    disclaimer: str
```

---

## 4. v0.3.0 Sandbox Schema

所有 sandbox 表使用独立的 `data_namespace="sandbox"` 标记，不与 Mock 主图谱合并。

### 4.1 Sandbox Neo4j 节点类型

#### SandboxPerson
```
Label: SandboxPerson
Fields:
  - id: String (unique, required)   # uscl_person_{bioguide_id}
  - canonical_name: String (required)
  - display_name: String
  - party: String
  - chamber: String
  - state: String
  - person_type: String  # legislator
  - bioguide_id: String
  - data_namespace: String  # "sandbox"
  - data_source: String     # "unitedstates/congress-legislators"
  - data_mode: String       # "real"
  - etl_run_id: String
```

#### SandboxPoliticalEntity
```
Label: SandboxPoliticalEntity
Fields:
  - id: String (unique, required)   # uscl_committee_{thomas_id}
  - name: String
  - entity_type: String  # committee
  - chamber: String
  - data_namespace/"sandbox"
  - data_source/"unitedstates/congress-legislators"
  - data_mode/"real"
  - etl_run_id: String
```

#### SandboxClaim
```
Label: SandboxClaim
Fields:
  - id: String (unique, required)
  - claim_type: String
  - relation_type: String
  - claim_text: String
  - confidence_score: Float
  - review_status: String
  - data_namespace/"sandbox"
  - data_source/"unitedstates/congress-legislators"
  - data_mode/"real"
  - etl_run_id: String
```

#### Neo4j 关系类型 (Sandbox Namespace)
```
(:SandboxPerson)-[:SERVED_ON_COMMITTEE]->(:SandboxPoliticalEntity)
(:SandboxClaim)-[:EVIDENCED_BY_SUBJECT]->(:SandboxPerson|SandboxPoliticalEntity)
(:SandboxClaim)-[:EVIDENCED_BY_OBJECT]->(:SandboxPerson|SandboxPoliticalEntity)
```

### 4.2 Sandbox PostgreSQL 表

| 表名 | 主键 | 记录数 | 用途 |
|------|------|--------|------|
| `sandbox_import_runs` | run_id | 1 | ETL 导入运行记录 |
| `sandbox_persons` | person_id | 12,767 | 真实议员数据 |
| `sandbox_person_terms` | term_id | 45,532 | 任期记录 |
| `sandbox_political_entities` | entity_id | 49 | 委员会实体 |
| `sandbox_committee_memberships` | membership_id | 3,879 | 委员会任职 |
| `sandbox_social_accounts` | account_id | 2,354 | 官方社媒账号 |
| `sandbox_claims` | claim_id | 64,532 | 提取的声明 |
| `sandbox_source_documents` | document_id | 5 | 源文档记录 |
| `sandbox_entity_resolution_reviews` | review_id | 12,767 | 实体对齐审查 |

### 4.3 置信度规则

| Claim 类型 | confidence_score | 依据 |
|------------|-----------------|------|
| identity_claim | 0.95 | YAML 结构化数据，bioguide_id 官方赋值 |
| term_claim | 0.90 | YAML 结构化数据，任期日期官方记录 |
| committee_membership_claim | 0.85 (有日期) / 0.80 (无日期) | YAML 结构化数据 |
| official_social_account | 0.85 | YAML 结构化数据，官方社媒账号 |
