"""
元数据知识库构建服务
====================

负责读取 meta_config.yaml，从 DW 数据仓库提取表结构信息，
组装为 ORM 对象，最终写入 MySQL meta 库 / Qdrant / ES。

工作流分三个阶段：
    Step 1: 加载配置 → MetaConfig 对象
    Step 2: 遍历 tables → 从 DW 查字段类型和取值示例 → 拼装 ORM 对象
            → 2.1 写入 MySQL meta 库
            → 2.2 对字段信息建立 Qdrant 向量索引
            → 2.3 对维度取值建立 ES 全文索引
    Step 3: 遍历 metrics → 同步指标信息 + 向量索引

当前状态：Step 2.1 已实现，2.2/2.3/3 待实现。
"""
import uuid
from dataclasses import asdict
from pathlib import Path

from langchain_huggingface import HuggingFaceEndpointEmbeddings
from omegaconf import OmegaConf

from app.clients.embedding_client_manager import embedding_client_manager
from app.conf.meta_config import MetaConfig
from app.entities.column_info import ColumnInfo
from app.entities.table_info import TableInfo
from app.repositories.mysql.dw.dw_mysql_repository import DWMySQLRepository
from app.repositories.mysql.meta.meta_mysql_repository import MetaMySQLRepository
from app.repositories.qdrant.column_qdrant_repository import ColumnQdrantRepository


class MetaKnowledgeService:
    """
    元数据知识库构建服务。

    依赖两个 Repository：
        meta_mysql_repository → 读写 MySQL meta 库
        dw_mysql_repository   → 只读 MySQL dw 库（查字段类型和取值示例）
    """

    def __init__(self,
                 meta_mysql_repository: MetaMySQLRepository,
                 dw_mysql_repository: DWMySQLRepository,
                 column_qdrant_repository: ColumnQdrantRepository,
                 embedding_client: HuggingFaceEndpointEmbeddings,
                 ):
        self.meta_mysql_repository: MetaMySQLRepository = meta_mysql_repository
        self.dw_mysql_repository: DWMySQLRepository = dw_mysql_repository
        self.column_qdrant_repository: ColumnQdrantRepository = column_qdrant_repository
        self.embedding_client: HuggingFaceEndpointEmbeddings = embedding_client

    async def build(self, config_path: Path):
        """
        执行元数据知识库构建全流程。

        该方法按顺序完成：
            1. 加载 meta_config.yaml → 类型安全的 MetaConfig 对象
            2. 遍历配置中的表 → 查 DW 获取字段类型和取值示例 → 拼装 ORM 对象
            3. 遍历配置中的指标 → 同步指标信息

        Args:
            config_path: meta_config.yaml 的绝对路径，由命令行 -c 参数传入
        """
        # Step 1: OmegaConf 加载 → 类型校验 → MetaConfig 实例
        # merge(schema, context)：YAML 中的数据填入 dataclass 模板，多余字段报错阻断
        context = OmegaConf.load(config_path)
        schema = OmegaConf.structured(MetaConfig)
        meta_config: MetaConfig = OmegaConf.to_object(OmegaConf.merge(schema, context))

        # Step 2: 同步表信息
        if meta_config.tables:
            table_infos: list[TableInfo] = []
            column_infos: list[ColumnInfo] = []

            for table in meta_config.tables:
                table_info = TableInfo(id=table.name,
                                       name=table.name,
                                       role=table.role,
                                       description=table.description)
                table_infos.append(table_info)

                # 从 DW 查询字段类型（SHOW COLUMNS），而非从 YAML 读取
                # 原因：YAML 只声明了元数据，字段的实际数据类型只在 DW 的表结构中存在
                column_types = await self.dw_mysql_repository.get_column_type(table.name)

                for column in table.columns:
                    # 从 DW 查询该字段的 distinct 取值，用作 ES 全文索引的示例值
                    column_values = await self.dw_mysql_repository.get_column_value(
                        table.name, column.name)
                    # id 用 "表名.字段名" 格式，确保不同表之间的字段 ID 不冲突
                    column_info = ColumnInfo(id=f"{table.name}.{column.name}",
                                                  name=column.name,
                                                  type=column_types[column.name],
                                                  role=column.role,
                                                  examples=column_values,
                                                  description=column.description,
                                                  alias=column.alias,
                                                  table_id=table.name)
                    column_infos.append(column_info)
            async with self.meta_mysql_repository.session.begin():
                self.meta_mysql_repository.save_table_infos(table_infos)
                self.meta_mysql_repository.save_column_infos(column_infos)
            # TODO: 2.2 对字段信息建立向量索引
            #   - 对 sync=true 的列：拼 column.name + alias + description →
            #     调 Embedding → 写入 Qdrant column 集合
            await self.column_qdrant_repository.ensure_collection()
            points: list[dict] = []
            for column_info in column_infos:
                points.append({
                    'id':uuid.uuid4(),
                    'embedding_text': column_info.name,
                    'payload': asdict(column_info),
                               })

                points.append({
                    'id': uuid.uuid4(),
                    'embedding_text': column_info.description,
                    'payload': asdict(column_info),
                })

                for alia in column_info.alias:
                    points.append({
                        'id': uuid.uuid4(),
                        'embedding_text': alia,
                        'payload': asdict(column_info),
                    })

            #向量化
            embeddings: list[list[float]] = []
            embedding_texts = [point['embedding_text'] for point in points]
            embedding_batch_size = 20
            for i in range(0, len(embedding_texts), embedding_batch_size):
                batch_embedding_texts = embedding_texts[i:i + embedding_batch_size]
                batch_embeddings = await self.embedding_client.aembed_documents(batch_embedding_texts)
                embeddings.extend(batch_embeddings)

            ids = [point['id'] for point in points]

            payloads = [point['payload'] for point in points]

            await self.column_qdrant_repository.upset()



            # TODO: 2.3 对维度字段取值建立全文索引
            #   - 对 sync=true 的维度列：遍历 examples →
            #     写入 ES data_agent 索引

        # Step 3: 同步指标信息
        if meta_config.metrics:
            pass
            # TODO: 3.1 将指标信息写入 MySQL meta 库
            # TODO: 3.2 对指标信息建立 Qdrant 向量索引
