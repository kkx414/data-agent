"""
元数据知识库构建服务
====================

核心服务层，负责将数据仓库（DW）的表结构和指标定义同步到下游知识库存储中。
它是整个 ETL 管道的编排者：从 YAML 配置出发，查询 DW 获取真实元数据，
然后分别写入 MySQL（结构化存储）、Qdrant（向量索引）和 Elasticsearch（全文索引）。

工作流分三个阶段，按顺序执行：

    Step 1  加载配置
            ─────────
            读取 meta_config.yaml → OmegaConf 校验 → MetaConfig 对象。
            若 YAML 中存在 MetaConfig 未定义的字段，OmegaConf 会报错阻断。

    Step 2  同步表信息（tables）
            ───────────────────
            2.1  写入 MySQL meta 库
                 - 遍历配置中的每张表 → 从 DW 查字段类型（SHOW COLUMNS）
                 - 从 DW 查每个字段的 distinct 取值示例
                 - 拼装 TableInfo / ColumnInfo ORM 对象 → 写入 meta 库

            2.2  建立 Qdrant 向量索引
                 - 对每个字段的 name、description、alias 分别生成 embedding
                 - 写入 Qdrant column_info_collection 集合
                 - 用途：支持"这个字段是干什么的？"等语义搜索

            2.3  建立 ES 全文索引
                 - 对 sync=true 的维度字段，将其所有 distinct 取值写入 ES
                 - 写入 ES value_index 索引（使用 ik_max_word 中文分词）
                 - 用途：支持"华北地区的订单"等维度值精确匹配

    Step 3  同步指标信息（metrics）
            ──────────────────────
            3.1  写入 MySQL meta 库
                 - MetricInfo + ColumnMetric（指标-字段关联表）

            3.2  建立 Qdrant 向量索引
                 - 对每个指标的 name、description、alias 生成 embedding
                 - 写入 Qdrant metric_info_collection 集合

依赖关系：
    ┌──────────────────────────────────────────────────┐
    │              MetaKnowledgeService                 │
    │              (本文件 - 编排层)                      │
    └──────┬──────────┬──────────┬──────────┬──────────┘
           │          │          │          │
           ▼          ▼          ▼          ▼
    MetaMySQLRepo  DWMySQLRepo  Qdrant     ES
    (meta 库读写)  (dw 库只读)  (向量索引)  (全文索引)

当前状态：
    ✅ Step 2.1  表信息 → MySQL  （已实现）
    ✅ Step 2.2  字段向量 → Qdrant（已实现）
    ✅ Step 2.3  维度值 → ES    （已实现）
    ✅ Step 3.1  指标信息 → MySQL（已实现）
    ✅ Step 3.2  指标向量 → Qdrant（已实现）

注意事项：
    - DW 查询使用原生 SQL 拼接（非 ORM），因为 SHOW COLUMNS 和动态表名/列名
      无法通过 SQLAlchemy ORM 表达。
    - 向量化采用批量模式（batch_size=20），避免一次性传入大量文本导致
      embedding 服务 OOM。
    - ES 的 ik_max_word 分词器需要在 ES 中预先安装 ik 插件。
"""
import uuid
from dataclasses import asdict
from pathlib import Path

from langchain_huggingface import HuggingFaceEndpointEmbeddings
from omegaconf import OmegaConf
from loguru import logger

from app.clients.embedding_client_manager import embedding_client_manager  # noqa: F401  # 预初始化 embedding 客户端
from app.conf.meta_config import MetaConfig
from app.entities.column_info import ColumnInfo
from app.entities.column_metric_info import ColumnMetric
from app.entities.metric_info import MetricInfo
from app.entities.table_info import TableInfo
from app.entities.value_info import ValueInfo
from app.repositories.es import value_es_repository  # ⚠️ 见下方错误 #2：此导入冗余，模块对象未被使用
from app.repositories.mysql.dw.dw_mysql_repository import DWMySQLRepository
from app.repositories.mysql.meta.meta_mysql_repository import MetaMySQLRepository
from app.repositories.qdrant.column_qdrant_repository import ColumnQdrantRepository
from app.repositories.es.value_es_repository import ValueESRepository
from app.repositories.qdrant.metric_qdrant_repository import MetricQdrantRepository


class MetaKnowledgeService:
    """
    元数据知识库构建服务。

    职责：
        编排"DW → 知识库"的完整同步流程。不直接操作数据库连接 —
        所有 I/O 通过 Repository 层完成，Service 层只做编排和转换。

    依赖的 Repository：

        meta_mysql_repository  (MetaMySQLRepository)
            读写 MySQL meta 库。负责 TableInfo / ColumnInfo / MetricInfo
            的持久化。写入操作在事务中完成。

        dw_mysql_repository  (DWMySQLRepository)
            只读 MySQL dw 库。提供两类查询：
            - get_column_type():    SHOW COLUMNS → 字段类型映射
            - get_column_value():   SELECT DISTINCT → 字段取值示例

        column_qdrant_repository  (ColumnQdrantRepository)
            写入 Qdrant column_info_collection 集合。
            存储字段名/描述/别名的向量，支持语义检索。

        metric_qdrant_repository  (MetricQdrantRepository)
            写入 Qdrant metric_info_collection 集合。
            存储指标名/描述/别名的向量，支持语义检索。

        value_es_repository  (ValueESRepository)
            写入 ES value_index 索引。
            存储维度字段的 distinct 取值，支持 ik_max_word 中文分词全文检索。

        embedding_client  (HuggingFaceEndpointEmbeddings)
            HuggingFace 推理端点提供的 embedding 服务。
            将文本转为浮点向量，用于 Qdrant 向量索引。
    """

    def __init__(self,
                 meta_mysql_repository: MetaMySQLRepository,
                 dw_mysql_repository: DWMySQLRepository,
                 column_qdrant_repository: ColumnQdrantRepository,
                 embedding_client: HuggingFaceEndpointEmbeddings,
                 value_es_repository: ValueESRepository,
                 metric_qdrant_repository: MetricQdrantRepository
                 ):
        """
        初始化服务实例。

        所有依赖通过构造函数注入（依赖注入模式），便于单元测试时 mock 各 Repository。

        Args:
            meta_mysql_repository:  meta 库读写仓库
            dw_mysql_repository:    dw 库只读仓库
            column_qdrant_repository: 字段向量索引仓库
            embedding_client:       HuggingFace embedding 推理客户端
            value_es_repository:    维度值 ES 全文索引仓库
            metric_qdrant_repository: 指标向量索引仓库
        """
        self.meta_mysql_repository: MetaMySQLRepository = meta_mysql_repository
        self.dw_mysql_repository: DWMySQLRepository = dw_mysql_repository
        self.column_qdrant_repository: ColumnQdrantRepository = column_qdrant_repository
        self.embedding_client: HuggingFaceEndpointEmbeddings = embedding_client
        self.value_es_repository: ValueESRepository = value_es_repository
        self.metric_qdrant_repository: MetricQdrantRepository = metric_qdrant_repository

    # ═══════════════════════════════════════════════════════════════
    # Step 2.1: 表信息 → MySQL meta 库
    # ═══════════════════════════════════════════════════════════════

    async def _save_tables_to_meta_db(self, meta_config: MetaConfig) -> list[ColumnInfo]:
        """
        将配置中的表结构和字段信息写入 MySQL meta 库。

        执行流程（按表遍历）：
            1. 对每张表创建 TableInfo 对象（id = 表名）
            2. 调用 DW MySQL Repository → SHOW COLUMNS 获取字段类型
               （注意：字段类型从 DW 实时查询，不从 YAML 读取 —
               YAML 只声明元数据，DW 才持有真实数据类型）
            3. 对每个字段调用 DW MySQL Repository → SELECT DISTINCT 获取取值示例
            4. 以 "表名.字段名" 格式生成 ColumnInfo.id，确保跨表不冲突
            5. 在同一个事务中写入 TableInfo + ColumnInfo

        Args:
            meta_config: 从 meta_config.yaml 解析得到的配置对象。

        Returns:
            column_infos: 所有字段的 ColumnInfo 列表，供后续 Step 2.2
                          （Qdrant 向量索引）复用，避免重复查询 DW。

        Raises:
            KeyError: 若 YAML 中配置的字段在 DW 中不存在，
                      column_types[column.name] 会抛出 KeyError。
                      建议在生产环境添加 try-except 并记录日志。
        """
        table_infos: list[TableInfo] = []
        column_infos: list[ColumnInfo] = []

        for table in meta_config.tables:
            # ── 构建表信息 ──────────────────────────────────────
            # id 直接使用表名：在 meta_config.yaml 中表名是唯一的
            table_info = TableInfo(id=table.name,
                                   name=table.name,
                                   role=table.role,
                                   description=table.description)
            table_infos.append(table_info)

            # ── 从 DW 查询字段类型 ──────────────────────────────
            # SHOW COLUMNS 返回 {'Field': 'Type', ...} 字典
            # 为什么要查 DW 而不是读 YAML：
            #   YAML 只声明了元数据（描述、别名、角色），字段的实际
            #   数据类型（如 varchar(50)、decimal(10,2)）只在 DW 的
            #   表结构中存在，必须实时查询。
            column_types = await self.dw_mysql_repository.get_column_type(table.name)

            for column in table.columns:
                # ── 从 DW 查询字段的 distinct 取值 ──────────────
                # 这些取值用作 ES 全文索引的示例值，也在前端展示为
                # "该字段可能的值有哪些？"
                column_values = await self.dw_mysql_repository.get_column_value(
                    table.name, column.name)

                # ── 构建字段信息 ────────────────────────────────
                # id 格式："表名.字段名"
                # 设计原因：不同表之间可能存在同名字段（如多个表都有
                # "create_time"），用 "表名.字段名" 作为全局唯一标识。
                column_info = ColumnInfo(id=f"{table.name}.{column.name}",
                                         name=column.name,
                                         type=column_types[column.name],
                                         role=column.role,
                                         examples=column_values,
                                         description=column.description,
                                         alias=column.alias,
                                         table_id=table.name)
                column_infos.append(column_info)
        # ── 事务写入 ───────────────────────────────────────────
        # 使用 async with session.begin() 确保 TableInfo 和 ColumnInfo
        # 的写入在同一个事务中：要么全部成功，要么全部回滚。
        async with self.meta_mysql_repository.session.begin():
            self.meta_mysql_repository.save_table_infos(table_infos)
            self.meta_mysql_repository.save_column_infos(column_infos)

        return column_infos

    # ═══════════════════════════════════════════════════════════════
    # Step 2.2: 字段信息 → Qdrant 向量索引
    # ═══════════════════════════════════════════════════════════════

    async def _save_columns_to_qdrant(self, column_infos: list[ColumnInfo]) -> None:
        """
        对字段信息建立 Qdrant 向量索引。

        索引策略 —— 多文本向量化：
            对每个字段生成多条向量记录，每条记录对应一个可搜索的文本维度：
            - column_info.name        → 按字段名搜索（如 "order_amount"）
            - column_info.description → 按字段描述搜索（如 "订单金额"）
            - column_info.alias[i]    → 按别名搜索（如 "销售额", "营收"）

            所有记录携带相同的 payload（完整的 ColumnInfo），确保无论
            命中哪条向量，都能返回完整的字段元数据。

        向量化流程：
            1. 确保 Qdrant 集合存在（不存在则创建，1024 维 COSINE 距离）
            2. 构建 points 列表（每个字段 → 1 + 1 + len(alias) 条记录）
            3. 批量调用 embedding 服务（每批 20 条）
            4. 批量 upsert 到 Qdrant（每批 10 条）

        Args:
            column_infos: 来自 Step 2.1 的字段信息列表（已入 MySQL）。
        """
        # ── 确保集合存在 ───────────────────────────────────────
        # 若集合不存在则创建，向量维度、距离度量等参数在 Repository 层定义
        await self.column_qdrant_repository.ensure_collection()

        # ── 构建待向量化的 points ──────────────────────────────
        # 每个字段拆分为多条 point：name、description、每个 alias 各一条
        # 这样用户按任意文本维度搜索都能命中
        points: list[dict] = []
        for column_info in column_infos:
            # 按字段名搜索的入口
            points.append({
                'id': uuid.uuid4(),
                'embedding_text': column_info.name,
                'payload': asdict(column_info),
            })

            # 按字段描述搜索的入口
            points.append({
                'id': uuid.uuid4(),
                'embedding_text': column_info.description,
                'payload': asdict(column_info),
            })

            # 按每个别名搜索的入口
            for alia in column_info.alias:
                points.append({
                    'id': uuid.uuid4(),
                    'embedding_text': alia,
                    'payload': asdict(column_info),
                })

        # ── 批量向量化 ─────────────────────────────────────────
        # 提取所有待向量化的文本 → 分批调用 embedding 服务
        # 分批原因：embedding 服务有单次请求的 token 上限，
        # 一次性传入几百条文本可能超限或超时
        embeddings: list[list[float]] = []
        embedding_texts = [point['embedding_text'] for point in points]
        embedding_batch_size = 20
        for i in range(0, len(embedding_texts), embedding_batch_size):
            batch_embedding_texts = embedding_texts[i:i + embedding_batch_size]
            batch_embeddings = await self.embedding_client.aembed_documents(batch_embedding_texts)
            embeddings.extend(batch_embeddings)

        # ── 拆分 ID 和 payload 列表 ────────────────────────────
        ids = [point['id'] for point in points]

        payloads = [point['payload'] for point in points]

        # ── 批量写入 Qdrant ────────────────────────────────────
        # Repository 层内部按 batch_size=10 分批 upsert
        await self.column_qdrant_repository.upset(ids, embeddings, payloads)

    # ═══════════════════════════════════════════════════════════════
    # Step 2.3: 维度字段取值 → ES 全文索引
    # ═══════════════════════════════════════════════════════════════

    async def _save_values_to_es(self, meta_config: MetaConfig) -> None:
        """
        对维度字段的取值建立 Elasticsearch 全文索引。

        同步策略：
            只对 column.sync=True 的字段建立索引。
            sync 标志在 meta_config.yaml 中配置，通常维度字段
            （如 province、category）设为 true，度量字段
            （如 amount、count）设为 false。

        索引内容：
            - 每个 distinct 取值生成一条 ValueInfo 记录
            - id 格式："表名.字段名.取值"（全局唯一）
            - 使用 ik_max_word 分词器支持中文分词搜索

        使用场景：
            用户输入 "华北" → ES 全文检索 value 字段 → 返回匹配的维度值
            → 据此构建 WHERE province = '华北' 的 SQL 查询。

        Args:
            meta_config: 从 meta_config.yaml 解析得到的配置对象。
        """
        # ── 确保索引存在 ───────────────────────────────────────
        # 若索引不存在则创建，mappings（字段类型、分词器）在 ValueESRepository 中定义
        await self.value_es_repository.ensure_index()

        # ── 遍历所有 sync=true 的字段，查询 distinct 取值 ──────
        value_infos: list[ValueInfo] = []
        for table in meta_config.tables:
            for column in table.columns:
                if column.sync:
                    # 从 DW 查询该字段的所有 distinct 取值
                    # limit=100000 是硬编码的上限：
                    #   - 对于高基数字段（如 user_id），100000 可能仍不足
                    #   - 未来可考虑从配置中读取 limit 值
                    current_column_values = await self.dw_mysql_repository.get_column_value(table.name, column.name,
                                                                                            100000)
                    # ── 构建 ValueInfo 列表 ──────────────────────
                    # 每条取值的 id 格式："表名.字段名.取值"
                    # 确保同一取值在不同字段下不冲突
                    current_values_infos = [ValueInfo(id=f"{table.name}.{column.name}.{current_column_value}",
                                                      value=current_column_value,
                                                      column_id=f"{table.name}.{column.name}") for
                                            current_column_value in current_column_values]

                    value_infos.extend(current_values_infos)

        # ── 批量写入 ES ────────────────────────────────────────
        # Repository 层内部按 batch_size=20 分批 index
        await self.value_es_repository.index(value_infos)

    # ═══════════════════════════════════════════════════════════════
    # Step 3.1: 指标信息 → MySQL meta 库
    # ═══════════════════════════════════════════════════════════════

    async def _save_metric_to_meta_db(self, meta_config: MetaConfig) -> list[MetricInfo]:
        """
        将配置中的指标定义写入 MySQL meta 库。

        写入内容：
            1. MetricInfo —— 指标本身（名称、描述、别名、关联字段列表）
            2. ColumnMetric —— 指标与字段的多对多关联关系
               （一个指标可能关联多个字段，一个字段可能被多个指标引用）

        数据关系示例：
            指标 "GMV" 关联字段 ["order_amount", "refund_amount"]
            → 写入 1 条 MetricInfo + 2 条 ColumnMetric

        Args:
            meta_config: 从 meta_config.yaml 解析得到的配置对象。

        Returns:
            metric_infos: 所有指标的 MetricInfo 列表，供后续 Step 3.2
                          （Qdrant 向量索引）复用。
        """
        metric_infos: list[MetricInfo] = []
        column_metrics: list[ColumnMetric] = []

        for metric in meta_config.metrics:
            # ── 构建指标信息 ──────────────────────────────────
            # metric->MetricInfo: 将 YAML 配置中的指标定义转为 ORM 实体
            metric_info = MetricInfo(
                id=metric.name,
                name=metric.name,
                description=metric.description,
                relevant_columns=metric.relevant_columns,
                alias=metric.alias
            )
            metric_infos.append(metric_info)

            # ── 构建指标-字段关联 ──────────────────────────────
            # 每个关联字段生成一条 ColumnMetric 记录，
            # 用于在 MySQL 中建立指标与字段的多对多关系
            for column in metric.relevant_columns:
                column_metric = ColumnMetric(
                    column_id=column,
                    metric_id=metric.name,
                )
                column_metrics.append(column_metric)

        # ── 事务写入 ───────────────────────────────────────────
        # MetricInfo 和 ColumnMetric 在同一事务中写入，保证一致性
        async with self.meta_mysql_repository.session.begin():
            self.meta_mysql_repository.save_metric_infos(metric_infos)
            self.meta_mysql_repository.save_column_metrics(column_metrics)

        return metric_infos

    # ═══════════════════════════════════════════════════════════════
    # Step 3.2: 指标信息 → Qdrant 向量索引
    # ═══════════════════════════════════════════════════════════════

    async def _save_metrics_to_qdrant(self, metric_infos: list[MetricInfo]) -> None:
        """
        对指标信息建立 Qdrant 向量索引。

        索引策略 —— 多文本向量化（与字段索引策略一致）：
            对每个指标生成多条向量记录：
            - metric_info.name        → 按指标名搜索（如 "GMV"）
            - metric_info.description → 按指标描述搜索（如 "总成交金额"）
            - metric_info.alias[i]    → 按别名搜索（如 "销售额", "营收"）

            所有记录携带相同的 payload（完整的 MetricInfo），确保
            无论命中哪条向量，都能返回完整的指标元数据。

        Args:
            metric_infos: 来自 Step 3.1 的指标信息列表（已入 MySQL）。
        """
        # ── 确保集合存在 ───────────────────────────────────────
        # 若集合不存在则创建，向量维度、距离度量等参数在 Repository 层定义
        await self.metric_qdrant_repository.ensure_collection()

        # ── 构建待向量化的 points ──────────────────────────────
        # 每个指标拆分为多条 point：name、description、每个 alias 各一条
        points: list[dict] = []
        for metric_info in metric_infos:
            # 按指标名搜索的入口
            points.append({
                'id': uuid.uuid4(),
                'embedding_text': metric_info.name,
                'payload': asdict(metric_info),
            })

            # 按指标描述搜索的入口
            points.append({
                'id': uuid.uuid4(),
                'embedding_text': metric_info.description,
                'payload': asdict(metric_info),
            })

            # 按每个别名搜索的入口
            for alia in metric_info.alias:
                points.append({
                    'id': uuid.uuid4(),
                    'embedding_text': alia,
                    'payload': asdict(metric_info),
                })

        # ── 批量向量化 ─────────────────────────────────────────
        # 与 _save_columns_to_qdrant 采用相同的分批策略：
        # 提取文本 → 每批 20 条调用 embedding 服务 → 汇总向量
        embeddings: list[list[float]] = []
        embedding_texts = [point['embedding_text'] for point in points]
        embedding_batch_size = 20
        for i in range(0, len(embedding_texts), embedding_batch_size):
            batch_embedding_texts = embedding_texts[i:i + embedding_batch_size]
            batch_embeddings = await self.embedding_client.aembed_documents(batch_embedding_texts)
            embeddings.extend(batch_embeddings)

        # ── 拆分 ID 和 payload 列表 ────────────────────────────
        ids = [point['id'] for point in points]

        payloads = [point['payload'] for point in points]

        # ── 批量写入 Qdrant ────────────────────────────────────
        # Repository 层内部按 batch_size=10 分批 upsert
        await self.metric_qdrant_repository.upset(ids, embeddings, payloads)


    async def build(self, config_path: Path):
            """
            执行元数据知识库构建全流程（对外唯一入口）。

            该方法按顺序驱动三个阶段，每个阶段依赖前一阶段的输出：

                Step 1 ─── 加载配置
                │   OmegaConf.load() → 结构化校验 → MetaConfig 对象
                │
                ├── Step 2 ─── 同步表信息（条件：meta_config.tables 非空）
                │   ├── 2.1  _save_tables_to_meta_db()    → MySQL
                │   ├── 2.2  _save_columns_to_qdrant()    → Qdrant
                │   └── 2.3  _save_values_to_es()         → Elasticsearch
                │
                └── Step 3 ─── 同步指标信息（条件：meta_config.metrics 非空）
                    ├── 3.1  _save_metric_to_meta_db()    → MySQL
                    └── 3.2  _save_metrics_to_qdrant()    → Qdrant

            错误处理：
                当前未实现细粒度的错误恢复。任一步骤失败会抛出异常并中断
                后续步骤。建议在生产环境中添加：
                - 每步的 try-except 包裹
                - 失败步骤的日志记录
                - 可重试的幂等性保证

            Args:
                config_path: meta_config.yaml 的绝对路径，由命令行 -c 参数传入。
                             示例: Path("/app/conf/meta_config.yaml")
            """
            # ── Step 1: 加载配置 ───────────────────────────────────
            # OmegaConf.merge(schema, context)：
            #   schema = OmegaConf.structured(MetaConfig)  → 生成 dataclass 的结构化模板
            #   context = OmegaConf.load(config_path)      → 从 YAML 文件读取实际数据
            #   merge 将 context 填入 schema，多余字段报错（严格模式），
            #   缺失字段使用 dataclass 默认值。
            #   OmegaConf.to_object() 将结构化配置转为 MetaConfig 实例。
            context = OmegaConf.load(config_path)
            schema = OmegaConf.structured(MetaConfig)
            meta_config: MetaConfig = OmegaConf.to_object(OmegaConf.merge(schema, context))
            logger.info("保存表信息成功")

            # ── Step 2: 同步表信息 ─────────────────────────────────
            if meta_config.tables:
                # 2.1 表结构 + 字段信息 → MySQL
                column_infos = await self._save_tables_to_meta_db(meta_config)
                logger.info("保存表信息和字段信息到数据库成功")
                # 2.2 字段向量索引 → Qdrant
                # 对 name、description、alias 分别生成 embedding，
                # 存入 Qdrant column_info_collection 集合
                await self._save_columns_to_qdrant(column_infos)
                logger.info("为字段信息建立向量索引成功")




                # 2.3 维度值全文索引 → Elasticsearch
                # 对 sync=true 的维度字段，将其 distinct 取值写入 ES，
                # 使用 ik_max_word 分词器支持中文搜索
                await self._save_values_to_es(meta_config)
                logger.info("为指定的维度字段建立全文索引成功")


            # ── Step 3: 同步指标信息 ───────────────────────────────
            if meta_config.metrics:
                # 3.1 指标定义 + 指标-字段关联 → MySQL
                metric_infos = await self._save_metric_to_meta_db(meta_config)
                logger.info("保存指标信息到数据库成功")
                # 3.2 指标向量索引 → Qdrant
                # 对 name、description、alias 分别生成 embedding，
                # 存入 Qdrant metric_info_collection 集合
                await self._save_metrics_to_qdrant(metric_infos)
                logger.info("为指标信息建立向量索引成功")
