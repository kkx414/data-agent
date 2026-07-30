# 掌柜问数 — 项目架构与技术路线

> 版本：V1.0 | 基于《尚硅谷大模型技术之掌柜问数》项目说明

---

## 一、项目概述

掌柜问数是一个基于大语言模型（LLM）与自然语言处理（NLP）的智能数据服务系统，面向上层业务用户，将自然语言查询自动转化为数据仓库的结构化查询语言（SQL），并返回查询结果。

核心价值：**"问即所得"——用户无需掌握 SQL 或数据仓库结构，用自然语言即可获取数据洞察。**

---

## 二、系统架构总览

```
┌─────────────────────────────────────────────────────────┐
│                      用户交互层                           │
│         前端 SPA（独立项目）↔ FastAPI REST/SSE             │
└──────────────────────┬──────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────┐
│                     API 服务层                           │
│     FastAPI + StreamingResponse（SSE流式响应）            │
│     中间件：request_id 注入 + 全局日志追踪                   │
└──────────────────────┬──────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────┐
│                   问数智能体（Agent）                      │
│                    LangGraph 工作流                      │
│                                                         │
│   extract_keywords → recall(column/value/metric) →      │
│   merge → filter(table/metric) → add_context →          │
│   generate_sql → validate → execute/correct             │
└──────┬──────────┬──────────┬──────────┬─────────────────┘
       │          │          │          │
┌──────▼──┐ ┌─────▼───┐ ┌───▼────┐ ┌──▼──────────┐
│  MySQL  │ │ Qdrant  │ │   ES   │ │  Embedding  │
│ 元数据DB │ │ 向量索引 │ │ 全文索引│ │  推理服务    │
│ + 业务DW │ │ (语义)  │ │(关键词)│ │  (TEI)      │
└─────────┘ └─────────┘ └────────┘ └─────────────┘
```

---

## 三、分层架构设计

### 3.1 目录结构

```
data-agent/
├── main.py                       # FastAPI 入口
├── app/
│   ├── agent/                    # 智能体核心
│   │   ├── graph.py              # LangGraph 工作流定义
│   │   ├── state.py              # Agent 状态定义
│   │   ├── context.py            # Agent 上下文
│   │   ├── llm.py                # LLM 客户端
│   │   └── nodes/                # 各节点逻辑
│   │       ├── extract_keywords.py
│   │       ├── recall_column.py
│   │       ├── recall_value.py
│   │       ├── recall_metric.py
│   │       ├── merge_retrieved_info.py
│   │       ├── filter_table.py
│   │       ├── filter_metric.py
│   │       ├── add_extra_context.py
│   │       ├── generate_sql.py
│   │       ├── validate_sql.py
│   │       ├── correct_sql.py
│   │       └── execute_sql.py
│   ├── api/                      # API 接口层
│   │   ├── routers/
│   │   │   └── query_router.py
│   │   ├── schemas/
│   │   │   └── query_schema.py
│   │   └── dependencies.py
│   ├── services/                 # 业务逻辑层
│   │   └── query_service.py
│   ├── repositories/             # 数据访问层（Repo 模式）
│   │   ├── mysql/
│   │   │   ├── meta/
│   │   │   │   └── meta_mysql_repository.py
│   │   │   └── dw/
│   │   │       └── dw_mysql_repository.py
│   │   ├── qdrant/
│   │   │   ├── column_qdrant_repository.py
│   │   │   └── metric_qdrant_repository.py
│   │   └── es/
│   │       └── value_es_repository.py
│   ├── clients/                  # 外部服务客户端管理
│   │   ├── mysql_client_manager.py
│   │   ├── qdrant_client_manager.py
│   │   ├── es_client_manager.py
│   │   └── embedding_client_manager.py
│   ├── models/                   # ORM 实体
│   ├── entities/                 # 业务实体（Domain Entity）
│   ├── conf/                     # 配置管理
│   │   └── app_config.py
│   ├── core/                     # 基础设施
│   │   ├── lifespan.py
│   │   ├── context.py
│   │   └── log.py
│   ├── prompt/                   # Prompt 工具
│   │   └── prompt_loader.py
│   └── scripts/                  # 初始化/工具脚本
├── conf/                         # YAML 配置文件
│   └── app_config.yaml
├── prompts/                      # Prompt 模板（静态文本）
├── docker/                       # Docker 编排
│   ├── elasticsearch/
│   ├── embedding/
│   └── mysql/
└── logs/                         # 运行日志
```

### 3.2 模块职责

| 层级 | 目录 | 职责 |
|------|------|------|
| **入口** | `main.py` | FastAPI 应用启动、路由注册、中间件注册 |
| **API** | `app/api/` | HTTP 接口定义、请求/响应 schema、依赖注入 |
| **Service** | `app/services/` | 核心业务编排，连接 API 与 Agent |
| **Agent** | `app/agent/` | LangGraph 工作流定义与节点实现 |
| **Repository** | `app/repositories/` | 各数据源的底层 CRUD 封装 |
| **Client** | `app/clients/` | 外部连接生命周期管理 |
| **Model/Entity** | `app/models/`, `app/entities/` | ORM 映射与领域对象 |
| **Core** | `app/core/` | 日志、生命周期、上下文变量 |
| **Conf** | `app/conf/`, `conf/` | OmegaConf 配置加载 |
| **Prompt** | `app/prompt/`, `prompts/` | Prompt 模板加载与管理 |

---

## 四、核心技术栈选型

| 分类 | 技术 | 版本 | 选型理由 |
|------|------|------|----------|
| **Web 框架** | FastAPI | latest | 原生异步、自动 OpenAPI、SSE 流式支持 |
| **ORM** | SQLAlchemy | 2.0+ | 异步支持成熟、生态最广 |
| **MySQL 驱动** | asyncmy | latest | 纯 Python 异步 MySQL 驱动，性能优异 |
| **向量数据库** | Qdrant | latest | 高性能、Rust 实现、REST/gRPC 双协议 |
| **搜索引擎** | Elasticsearch | 8.x | 全文检索标准方案、生态成熟 |
| **ES 可视化管理** | Kibana | 8.x | 官方管理界面，调试必备 |
| **Embedding** | Text Embedding Inference (TEI) | latest | HuggingFace 官方推理引擎，GPU 加速 |
| **Embedding 模型** | BAAI/bge-large-zh-v1.5 | — | 中文语义向量 SOTA，1024 维 |
| **LLM 编排** | LangChain + LangGraph | latest | 主流 Agent 框架，图结构可控 |
| **LLM** | GPT-5.2-codex（OpenAI 兼容 API） | — | SQL 生成能力强 |
| **中文分词** | jieba | latest | 轻量高效，中文关键词提取 |
| **配置管理** | OmegaConf | latest | 分层配置、类型安全、YAML 支持 |
| **日志** | Loguru | latest | 比标准 logging 更优雅，自动轮转 |
| **依赖管理** | uv | latest | Rust 实现，比 pip 快 10-100 倍 |
| **基础设施** | Docker Compose | — | 一键部署全部基础服务 |

---

## 五、元数据知识库设计

### 5.1 MySQL 元数据库（`meta`）

四张核心表通过外键关联形成完整的数据仓库元数据描述：

| 表名 | 说明 | 关键字段 |
|------|------|----------|
| `table_info` | 数据仓库表信息 | 表名、表中文名、所属层级、描述 |
| `column_info` | 字段信息 | 字段名、中文名、类型、所属表、是否维度、字段描述 |
| `column_value` | 字段取值示例 | 字段ID、取值、取值描述 |
| `metric_info` | 指标定义 | 指标名、中文名、所属表、计算表达式、指标描述 |

> 关系链：`table_info` ← `column_info` ← `column_value` / `metric_info`

### 5.2 Qdrant 向量索引（语义召回）

| 集合 | 向量化内容 | 维度 | 用途 |
|------|-----------|------|------|
| `column` | `column_info` 的字段中文名 + 描述组合文本 | 1024 | 根据用户问题语义匹配相关字段 |
| `metric` | `metric_info` 的指标中文名 + 描述组合文本 | 1024 | 根据用户问题语义匹配相关指标 |

### 5.3 Elasticsearch 全文索引（关键词召回）

- **索引名**: `data_agent`
- **索引内容**: `column_value` 表中各维度字段的实际取值
- **场景**: 用户提到"华北地区"→ ES 全文匹配 `region = '华北'`，作为 WHERE/GROUP BY 的准确依据

---

## 六、问数智能体工作流

### 6.1 流程图

```
START
  │
  ▼
extract_keywords         ← 提取关键词（jieba 分词 + LLM 辅助）
  │
  ├──→ recall_column     ← Qdrant 语义召回相关字段
  ├──→ recall_value      ← ES 全文召回维度取值
  └──→ recall_metric     ← Qdrant 语义召回相关指标
  │
  ▼
merge_retrieved_info     ← 合并三路召回结果
  │
  ├──→ filter_table      ← 根据召回信息筛选相关表（元数据库查表详情）
  └──→ filter_metric     ← 根据召回信息筛选相关指标（元数据库查指标详情）
  │
  ▼
add_extra_context        ← 注入当前日期、数据库版本等上下文
  │
  ▼
generate_sql             ← LLM 生成 SQL（Prompt 注入：query + table + metric + context）
  │
  ▼
validate_sql             ← EXPLAIN 语法校验
  │
  ├── 通过 → execute_sql  ← 执行并流式返回结果
  └── 失败 → correct_sql  ← LLM 根据报错修正 SQL → 重新 execute
  │
  ▼
END
```

### 6.2 关键设计决策

| 决策点 | 方案 | 理由 |
|--------|------|------|
| 三路召回并行 | extract_keywords → 三个 recall 节点并发 | 语义 + 关键词互补，减少漏召回 |
| SQL 校验闭环 | validate → correct → execute 循环 | 自修复机制提升 SQL 可用率 |
| 流式响应 | SSE（Server-Sent Events） | 实时反馈进度，用户体验好 |
| 依赖注入 | FastAPI Depends | 解耦、可测试、生命周期自动管理 |
| request_id 追踪 | ContextVar + 中间件 | 并发场景下精确日志关联 |

---

## 七、API 接口设计

### 7.1 查询接口

```
POST /api/query
Content-Type: application/json

Request:
{
    "query": "统计去年各地区的销售总额"
}

Response: text/event-stream (SSE)
data: {"type":"progress","step":"提取关键词","status":"running"}
data: {"type":"progress","step":"提取关键词","status":"success"}
data: {"type":"progress","step":"向量召回字段","status":"running"}
...
data: {"type":"result","data":[...]}
```

### 7.2 响应消息类型

| type | 说明 | 示例 |
|------|------|------|
| `progress` | 工作流进度 | `{"step": "生成SQL", "status": "running"}` |
| `result` | 最终查询结果 | `{"data": [{"region":"华北","total":12345},...]}` |
| `error` | 异常信息 | `{"message": "SQL执行失败: ..."}` |

---

## 八、配置管理体系

```
conf/app_config.yaml          ← 集中配置（单文件多段）
  ├── logging                 ← 日志级别、路径、轮转策略
  ├── db_meta                 ← 元数据库连接信息
  ├── db_dw                   ← 数据仓库连接信息
  ├── qdrant                  ← Qdrant 连接 + embedding_size
  ├── embedding               ← TEI 服务地址 + 模型名
  ├── es                      ← ES 连接 + 索引名
  └── llm                     ← LLM 模型名、API Key、Base URL

加载方式：OmegaConf.structured(AppConfig) → 类型安全的 dataclass
```

---

## 九、技术路线与开发阶段

| 阶段 | 内容 | 产出 |
|------|------|------|
| **Phase 1：基础设施** | Docker Compose 部署 MySQL / Qdrant / ES / Kibana / TEI | 全部基础服务就绪 |
| **Phase 2：元数据初始化** | 创建 MySQL 四张元数据表 + 注入示例数据 + 构建 Qdrant 向量索引 + ES 全文索引 | 元数据知识库就绪 |
| **Phase 3：客户端封装** | 实现各 Client Manager 和 Repository 层 | 数据访问层完整 |
| **Phase 4：Agent 节点开发** | 逐个实现 LangGraph 12 个节点 + 工作流编排 | 智能体核心可运行 |
| **Phase 5：API 服务** | FastAPI 接口 + SSE 流式响应 + 依赖注入 + 中间件 | 后端服务可对外访问 |
| **Phase 6：前后端对接** | 接入前端项目 + 端到端联调 | 完整系统可演示 |
| **Phase 7：优化迭代** | Prompt 调优、召回策略优化、SQL 生成质量提升 | 系统稳定可用 |

---

## 十、架构亮点总结

1. **三路召回+融合策略**：向量语义召回（Qdrant）+ 全文关键词召回（ES）+ 结构化元数据查询（MySQL），多维互补确保高召回率
2. **LangGraph 可控工作流**：图结构定义 Agent 流程，节点解耦、条件分支清晰、易于扩展
3. **SQL 自修复闭环**：EXPLAIN 预校验 + 错误回传 LLM 修正，显著提升生成 SQL 可用率
4. **全链路异步**：FastAPI + asyncmy + 异步 ES 客户端，高并发下吞吐量最大化
5. **流式 SSE 响应**：用户可实时感知查询进度，避免长时间等待的焦虑
6. **request_id 全链路追踪**：ContextVar + 中间件 + Loguru 定制格式，并发请求日志不串扰
