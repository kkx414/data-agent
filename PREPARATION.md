# 掌柜问数 — 前期准备规划

> 版本：V1.0 | 基于《尚硅谷大模型技术之掌柜问数》项目说明

---

## 一、准备工作总览

| 序号 | 类别 | 内容 | 预计耗时 |
|------|------|------|----------|
| 1 | 硬件与环境 | 确认 GPU / Docker / Python / Node 环境 | 30 min |
| 2 | 项目脚手架 | uv 创建项目、安装 Python 依赖 | 15 min |
| 3 | 基础设施 | Docker Compose 部署 5 项基础服务 | 20 min |
| 4 | 元数据初始化 | MySQL 建表 + 数据写入 + 向量/全文索引构建 | 40 min |
| 5 | 代码初始化 | 客户端管理器 + Repository 层 + 配置系统 | 60 min |
| 6 | Agent 开发 | LangGraph 12 个节点 + 工作流编排 | 120 min |
| 7 | API 服务 | FastAPI 接口 + 中间件 + 日志 | 45 min |
| 8 | 前端环境 | Node.js + 前端项目启动 | 15 min |
| 9 | 端到端联调 | 全链路测试 + Apifox 调试 | 30 min |

---

## 二、硬件与环境准备

### 2.1 硬件最低要求

| 资源 | 最低要求 | 推荐配置 |
|------|----------|----------|
| CPU | 4 核 | 8 核+ |
| 内存 | 16 GB | 32 GB+ |
| 磁盘 | 50 GB 可用 | 100 GB SSD |
| GPU | 无（可 CPU 跑 TEI） | NVIDIA 8GB+ VRAM（Embedding 推理加速） |

> ⚠️ Elasticsearch 和 Qdrant 是内存大户，Docker 默认内存分配建议设为 8 GB 以上。

### 2.2 软件清单

| 软件 | 版本要求 | 用途 | 安装方式 |
|------|----------|------|----------|
| Python | 3.10+ | 后端开发语言 | 官网 / Anaconda |
| uv | latest | Python 依赖管理 | `pip install uv` 或官网 |
| Docker Desktop | latest | 容器化部署基础服务 | [docker.com](https://docker.com) |
| Docker Compose | v2+ | 多容器编排（Docker Desktop 已内置） | 随 Docker 附带 |
| Node.js | 18+ | 前端项目运行 | [nodejs.org](https://nodejs.org) |
| Git | latest | 版本控制 | [git-scm.com](https://git-scm.com) |

### 2.3 环境检查命令

```bash
# Python
python --version          # 期望 ≥ 3.10

# uv
uv --version              # 期望已安装

# Docker
docker --version          # 期望 ≥ 24
docker compose version    # 期望 v2+

# Node.js
node --version            # 期望 ≥ 18
npm --version             # 附带检查

# Git
git --version
```

---

## 三、项目脚手架搭建

### 3.1 创建项目

```bash
# 初始化为 uv 管理项目
uv init data-agent
cd data-agent
```

### 3.2 安装 Python 依赖

```bash
uv add fastapi[standard] sqlalchemy asyncmy qdrant-client \
      "elasticsearch[async]>=8,<9" langchain langchain-huggingface \
      langgraph jieba omegaconf pyyaml loguru cryptography
```

### 3.3 依赖说明

| 包名 | 作用 |
|------|------|
| `fastapi[standard]` | 高性能异步 Web 框架，含 uvicorn 等标准组件 |
| `sqlalchemy` | 异步 ORM，统一管理数据库读写与事务 |
| `asyncmy` | MySQL 高性能 asyncio 驱动 |
| `qdrant-client` | Qdrant 向量数据库客户端 |
| `elasticsearch[async]>=8,<9` | 异步 ES 客户端，用于全文检索 |
| `langchain` | LLM 应用编排框架 |
| `langchain-huggingface` | HuggingFace Embedding/LLM 桥接 |
| `langgraph` | 图结构 Agent 工作流构建 |
| `jieba` | 中文分词 |
| `omegaconf` | 分层配置系统 |
| `pyyaml` | YAML 解析 |
| `loguru` | 优雅日志库 |
| `cryptography` | 加密基础库（网络/数据库依赖） |

---

## 四、基础设施服务部署

### 4.1 服务清单

| 服务 | 端口 | 用途 |
|------|------|------|
| MySQL | 3306 | 元数据库 `meta` + 业务数据仓库 `dw` |
| Qdrant | 6333 | 向量存储与语义检索 |
| Elasticsearch | 9200 | 全文索引与检索 |
| Kibana | 5601 | ES 可视化管理与调试 |
| Text Embedding Inference | 8081 | Embedding 模型推理（BAAI/bge-large-zh-v1.5） |

### 4.2 Docker Compose 部署

项目资料中已包含 `docker-compose.yaml` 及 `docker/` 目录下的各服务配置文件。

```bash
# 进入 docker-compose.yaml 所在目录
cd docker/

# 一键启动全部服务（后台运行）
docker compose up -d

# 验证服务状态
docker compose ps
# 期望：5 个服务均为 Up / healthy
```

### 4.3 各服务启动后验证

```bash
# MySQL 连接验证
mysql -h localhost -P 3306 -u atguigu -pAtguigu.123 -e "SELECT 1"

# Qdrant 健康检查
curl http://localhost:6333/health

# Elasticsearch 健康检查
curl http://localhost:9200/_cluster/health

# Kibana 可访问性
curl http://localhost:5601

# Embedding 服务验证
curl http://localhost:8081/health
```

> ⚠️ 首次启动时，TEI 需要下载 `BAAI/bge-large-zh-v1.5` 模型（约 1.3 GB），耗时取决于网络。可通过 `docker compose logs -f embedding` 观察进度。

---

## 五、元数据知识库初始化

### 5.1 MySQL 建表

在 `meta` 库中创建四张元数据表：

```sql
-- 1. table_info：数据仓库表信息
CREATE TABLE meta.table_info (
    id          INT PRIMARY KEY AUTO_INCREMENT,
    table_name  VARCHAR(255) NOT NULL COMMENT '表名',
    table_cn    VARCHAR(255) COMMENT '表中文名',
    layer       VARCHAR(50)  COMMENT '数据层级（ODS/DWD/DWS/ADS）',
    description TEXT         COMMENT '表描述'
);

-- 2. column_info：字段信息
CREATE TABLE meta.column_info (
    id              INT PRIMARY KEY AUTO_INCREMENT,
    table_id        INT NOT NULL COMMENT '所属表ID',
    column_name     VARCHAR(255) NOT NULL COMMENT '字段名',
    column_cn       VARCHAR(255) COMMENT '字段中文名',
    column_type     VARCHAR(50)  COMMENT '字段类型',
    is_dimension    TINYINT(1) DEFAULT 0 COMMENT '是否为维度字段',
    description     TEXT COMMENT '字段描述',
    FOREIGN KEY (table_id) REFERENCES table_info(id)
);

-- 3. column_value：字段取值示例
CREATE TABLE meta.column_value (
    id            INT PRIMARY KEY AUTO_INCREMENT,
    column_id     INT NOT NULL COMMENT '字段ID',
    value         VARCHAR(500) NOT NULL COMMENT '取值',
    value_desc    VARCHAR(500) COMMENT '取值描述',
    FOREIGN KEY (column_id) REFERENCES column_info(id)
);

-- 4. metric_info：指标定义
CREATE TABLE meta.metric_info (
    id              INT PRIMARY KEY AUTO_INCREMENT,
    table_id        INT NOT NULL COMMENT '所属表ID',
    metric_name     VARCHAR(255) NOT NULL COMMENT '指标名',
    metric_cn       VARCHAR(255) COMMENT '指标中文名',
    expression      TEXT COMMENT '计算表达式/SQL片段',
    description     TEXT COMMENT '指标描述',
    FOREIGN KEY (table_id) REFERENCES table_info(id)
);
```

### 5.2 数据注入

根据项目提供的业务数据（模拟电商零售场景），向四张表写入示例数据。建议通过课程资料中的 SQL 脚本批量导入，或编写 Python 脚本通过 SQLAlchemy 写入。

关键数据示例：

| 表 | 示例内容 |
|----|---------|
| `table_info` | `ods_order` (订单表), `dwd_order_detail` (订单明细), `dim_region` (地区维度), `dim_product` (商品维度) |
| `column_info` | `order_amount` (订单金额), `region_id` (地区ID), `order_date` (下单日期) |
| `column_value` | `region_name = '华北'`, `category = '数码'`, `brand = '华为'` |
| `metric_info` | `total_sales = SUM(order_amount)`, `order_count = COUNT(*)` |

### 5.3 向量索引构建

编写脚本遍历 `column_info` 和 `metric_info`，将需索引字段拼接后调用 Embedding 服务生成向量，写入 Qdrant：

```
Column 索引内容: "{column_cn} {description}"
Metric 索引内容: "{metric_cn} {description}"
```

Qdrant 集合配置：
- 集合名：`column` / `metric`
- 向量维度：1024（与 bge-large-zh-v1.5 一致）
- 距离度量：Cosine

### 5.4 全文索引构建

编写脚本遍历 `column_value`，将各维度取值批量写入 ES 索引 `data_agent`：

```json
{
  "column_id": 1,
  "column_name": "region_name",
  "value": "华北",
  "value_desc": "华北地区"
}
```

---

## 六、配置文件准备

创建 `conf/app_config.yaml`，填入实际环境参数：

```yaml
logging:
  file:
    enable: true
    level: INFO
    path: logs
    rotation: "10 MB"
    retention: "7 days"
  console:
    enable: true
    level: INFO

db_meta:
  host: localhost
  port: 3306
  user: atguigu
  password: Atguigu.123
  database: meta

db_dw:
  host: localhost
  port: 3306
  user: atguigu
  password: Atguigu.123
  database: dw

qdrant:
  host: localhost
  port: 6333
  embedding_size: 1024

embedding:
  host: localhost
  port: 8081
  model: BAAI/bge-large-zh-v1.5

es:
  host: localhost
  port: 9200
  index_name: data_agent

llm:
  model_name: gpt-5.2-codex
  api_key: <your_api_key>
  base_url: https://api.openai-proxy.org/v1
```

> ⚠️ `llm.api_key` 和 `llm.base_url` 需根据实际使用的模型服务填写。

---

## 七、代码初始化开发顺序

按照依赖关系，建议按以下顺序开发：

```
phase 1: app/conf/app_config.py          ← 配置加载（最先，所有模块依赖它）
phase 2: app/core/log.py                 ← 日志系统
phase 3: app/clients/*                   ← 4个客户端管理器
phase 4: app/models/*                    ← ORM 实体定义
phase 5: app/repositories/*              ← 7个 Repository
phase 6: app/core/lifespan.py            ← 生命周期事件
phase 7: app/agent/state.py + context.py ← Agent 数据结构
phase 8: app/agent/llm.py               ← LLM 客户端
phase 9: app/prompt/prompt_loader.py     ← Prompt 加载器
phase 10: app/agent/nodes/*             ← 12个 Agent 节点
phase 11: app/agent/graph.py            ← LangGraph 工作流编排
phase 12: app/services/query_service.py ← 业务层
phase 13: app/api/*                     ← API 接口
phase 14: main.py                        ← FastAPI 入口
```

---

## 八、前端环境准备

```bash
# 1. 确认 Node.js ≥ 18
node --version

# 2. 进入前端项目目录（课程资料提供）
cd frontend/

# 3. 安装依赖
npm install

# 4. 启动开发服务器
npm run dev

# 5. 浏览器访问命令行输出的地址（通常 http://localhost:5173）
```

> 前端为独立项目，通过 HTTP 调用后端 `/api/query` 接口进行 SSE 流式通信。

---

## 九、开发工具推荐

| 类别 | 工具 | 用途 |
|------|------|------|
| IDE | VS Code / PyCharm | 代码编写 |
| API 测试 | Apifox / Postman | 接口调试，SSE 流式响应测试 |
| 数据库管理 | DBeaver / Navicat | MySQL 可视化操作 |
| ES 调试 | Kibana Dev Tools | ES 查询语句调试与索引管理 |
| Docker 管理 | Docker Desktop | 容器状态监控 |
| 版本控制 | Git + GitHub/Gitee | 代码版本管理 |

---

## 十、检查清单（Checklist）

完成一项勾一项：

### 环境
- [ ] Python 3.10+ 已安装
- [ ] uv 已安装
- [ ] Docker Desktop 已安装并正常运行
- [ ] Node.js 18+ 已安装

### 项目
- [ ] `uv init` 完成项目初始化
- [ ] `uv add` 安装全部 Python 依赖成功
- [ ] 项目目录结构按架构文档创建完毕

### 服务
- [ ] `docker compose up -d` 启动成功（5 个服务全部 healthy）
- [ ] MySQL 连接验证通过
- [ ] Qdrant 健康检查通过
- [ ] Elasticsearch 健康检查通过
- [ ] Kibana 页面可访问
- [ ] Embedding 服务模型下载完成并可访问

### 数据
- [ ] MySQL `meta` 数据库 4 张表创建完成
- [ ] 示例数据写入完成
- [ ] Qdrant `column` 集合向量索引构建完成
- [ ] Qdrant `metric` 集合向量索引构建完成
- [ ] ES `data_agent` 索引创建完成并写入维度取值

### 配置
- [ ] `conf/app_config.yaml` 填写完成
- [ ] LLM API Key 已配置
- [ ] 各服务连接参数验证无误

### 代码
- [ ] 配置加载模块通过测试
- [ ] 日志系统正常输出
- [ ] 4 个客户端管理器初始化成功
- [ ] Repository 层 CRUD 测试通过
- [ ] Agent 各节点单元测试通过
- [ ] LangGraph 工作流集成测试通过
- [ ] FastAPI 服务启动并正常响应
- [ ] `/api/query` SSE 流式接口可正常返回

### 联调
- [ ] 前端项目启动成功
- [ ] 前端 → 后端接口调通
- [ ] 完整问数流程：输入问题 → 返回结果，端到端走通
- [ ] Apifox 接口测试通过

---

## 十一、常见问题预案

| 问题 | 原因 | 解决 |
|------|------|------|
| Docker 服务启动失败 | 端口冲突 | `netstat -ano` 检查 3306/6333/9200/5601/8081 端口占用 |
| ES 启动后立即退出 | 内存不足 | 修改 `docker-compose.yaml` 中 ES 的 `-Xmx` 参数 |
| TEI 模型下载慢 | 网络问题 | 配置 Docker Hub 国内镜像，或提前下载模型挂载 |
| `uv add` 失败 | PyPI 源不可达 | 配置 `UV_INDEX_URL` 为国内镜像源 |
| LLM API 调用超时 | 网络/代理问题 | 检查 `base_url` 和 `api_key`，确认网络可达 |
| `asyncmy` 连接失败 | 密码特殊字符转义 | URL 中使用 `urllib.parse.quote_plus` 处理密码 |
