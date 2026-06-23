# USCMP - 美国国会利益关联图谱系统

USCMP 是一个面向美国国会政治研究的开源情报分析工具，用于展示现任议员的身份背景、委员会任职、政治献金、公开持股披露和关系图谱。

> 主项目位于 [`congress-interest-graph/`](congress-interest-graph/)。

## v1.0 重点

- 新增数据覆盖 API：`/api/data-coverage`，展示基础资料、画像、FEC 献金、持股披露的数据覆盖状态。
- 优化 FEC 导入：仅保留现任议员，限制 2022/2024 周期，降低磁盘压力。
- 修复 FEC candidate ID 匹配：补正多位参议员 Senate ID，提升现任议员委员会覆盖率。
- 新增政治献金与持股前端页：`ContributionsTab`、`HoldingsTab`。
- 新增持股披露 ETL：支持 CSV/JSON 格式的公开财务披露数据导入。
- 优化 API 稳定性：统一议员可见性过滤，避免部分接口失败阻塞整体页面加载。

## 快速启动

```bash
cd congress-interest-graph

# 启动后端
cd backend
POSTGRES_HOST=localhost NEO4J_URI=bolt://localhost:7687 python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# 启动前端
cd ../frontend
npx vite --port 3000 --host 0.0.0.0
```

访问地址：

- 前端：http://localhost:3000
- API 文档：http://localhost:8000/docs

## 数据策略

当前仓库默认面向轻量预览环境，避免提交或依赖大型原始数据文件。

- FEC 原始 `indiv*.zip` 文件体积较大，不纳入 Git。
- 当前建议仅导入 2022/2024 两个周期的现任议员数据。
- 未来 v2.0 计划引入 summary-first 的轻量数据内核。

## 技术栈

- 后端：FastAPI、SQLAlchemy、PostgreSQL、Neo4j
- 前端：React、TypeScript、Vite、Ant Design、AntV G6
- 数据源：unitedstates/congress-legislators、FEC bulk data、公开财务披露数据

## 详细文档

- 项目 README：[`congress-interest-graph/README.md`](congress-interest-graph/README.md)
- 部署说明：[`congress-interest-graph/DEPLOYMENT.md`](congress-interest-graph/DEPLOYMENT.md)
- 演示指南：[`congress-interest-graph/DEMO.md`](congress-interest-graph/DEMO.md)
