"""
元数据知识库构建 — CLI 入口
==========================

读取 meta_config.yaml，连接 MySQL meta 和 dw 两个库，
调用 MetaKnowledgeService 执行元数据同步。

用法：
    python app/scripts/build_meta_knowledge.py -c conf/meta_config.yaml

该脚本按顺序：
    1. 初始化两个 MySQL 连接池（meta + dw）
    2. 创建 Repository → 注入 Service
    3. 执行 Service.build()（核心构建逻辑）
    4. 关闭连接池释放资源
"""

import argparse
import asyncio
from pathlib import Path

from app.clients.embedding_client_manager import embedding_client_manager
from app.clients.es_client_manager import es_client_manager
from app.clients.mysql_client_manager import meta_mysql_client_manager, dw_mysql_client_manager
from app.clients.qdrant_client_manager import qdrant_client_manager
from app.repositories.es.value_es_repository import ValueESRepository
from app.repositories.mysql.dw.dw_mysql_repository import DWMySQLRepository
from app.repositories.mysql.meta.meta_mysql_repository import MetaMySQLRepository
from app.repositories.qdrant.column_qdrant_repository import ColumnQdrantRepository
from app.repositories.qdrant.metric_qdrant_repository import MetricQdrantRepository
from app.services.meta_knowledge_service import MetaKnowledgeService


async def build(config_path: Path):
    """
    初始化连接 → 装配依赖 → 执行构建 → 释放资源。

    两个 async with 用逗号合并为一个上下文管理器：
        meta_session 用于读写 meta 库，dw_session 用于只读 dw 库。
        两者独立，互不干扰——meta 的写操作不会阻塞 dw 的读操作。
    """
    meta_mysql_client_manager.init()
    dw_mysql_client_manager.init()
    qdrant_client_manager.init()
    embedding_client_manager.init()
    es_client_manager.init()

    # 两个 session 并行进入，任一退出时一并释放
    async with (meta_mysql_client_manager.session_factory() as meta_session,
                dw_mysql_client_manager.session_factory() as dw_session):
        meta_mysql_repository = MetaMySQLRepository(meta_session)
        dw_mysql_repository = DWMySQLRepository(dw_session)

        column_qdrant_repository = ColumnQdrantRepository(qdrant_client_manager.client)
        metric_qdrant_repository = MetricQdrantRepository(qdrant_client_manager.client)
        value_es_repository = ValueESRepository(es_client_manager.client)
        meta_knowledge_service = MetaKnowledgeService(meta_mysql_repository=meta_mysql_repository,
                                                      dw_mysql_repository=dw_mysql_repository,
                                                      column_qdrant_repository=column_qdrant_repository,
                                                      embedding_client=embedding_client_manager.client,
                                                      value_es_repository=value_es_repository,
                                                      metric_qdrant_repository=metric_qdrant_repository)

        await meta_knowledge_service.build(config_path)

    await meta_mysql_client_manager.close()
    await dw_mysql_client_manager.close()
    await qdrant_client_manager.close()
    await es_client_manager.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description="构建元数据知识库：从 DW 提取字段信息 → 写入 MySQL/Qdrant/ES")
    parser.add_argument('-c', '--conf',
                        required=True,
                        help="meta_config.yaml 的路径")
    args = parser.parse_args()
    config_path = args.conf

    asyncio.run(build(Path(config_path)))
