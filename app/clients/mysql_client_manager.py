"""
MySQL 客户端管理器
==================

封装基于 SQLAlchemy async engine 的 MySQL 连接生命周期。
项目中共创建两个全局实例：

    meta_mysql_client_manager → 连接 meta 库（元数据表结构）
    dw_mysql_client_manager   → 连接 dw 库（实际业务数据）
"""

import asyncio

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine, AsyncSession, async_sessionmaker

from app.conf.app_config import DBConfig, app_config


class MySQLClientManager:
    """
    MySQL 客户端管理器：封装单个数据库的连接池和会话工厂。

    Attributes:
        engine: 异步引擎，内部为 QueuePool 连接池。init() 后创建。
        session_factory: 异步会话工厂，每次调用从池中借出一条连接。
        config: 数据库连接配置（来自 app_config.yaml）。
    """

    def __init__(self, config: DBConfig):
        self.engine: AsyncEngine | None = None
        self.session_factory = None
        self.config = config

    def _get_url(self):
        """
        拼接 SQLAlchemy 异步连接 URL。

        URL 格式: mysql+asyncmy://user:password@host:port/database?charset=utf8mb4

        _get_url 以 _ 开头：仅类内部调用，外部不应直接使用。
        """
        return (
            f"mysql+asyncmy://"
            f"{self.config.user}:{self.config.password}@"
            f"{self.config.host}:{self.config.port}/"
            f"{self.config.database}"
            f"?charset=utf8mb4"
        )

    def init(self):
        """
        创建异步引擎和会话工厂。

        pool_size=10：预建 10 个空闲连接，覆盖项目中两个并发 session 的场景。
        pool_pre_ping=True：每次从池中取连接前先发 SELECT 1 验证连接有效性，
            避免拿到已被 MySQL 服务端超时断开的"死连接"。
        """
        self.engine = create_async_engine(
            self._get_url(),
            pool_size=10,
            pool_pre_ping=True)

        # autoflush=True：session 提交前自动将内存变更同步到数据库
        # expire_on_commit=False：提交后不使 ORM 对象过期，避免后续访问触发额外查询
        self.session_factory = async_sessionmaker(
            self.engine,
            autoflush=True,
            expire_on_commit=False)

    async def close(self):
        """
        释放连接池中所有 TCP 连接。

        调用时机：脚本退出前。异步方法，需 await 等待所有连接关闭。
        """
        await self.engine.dispose()


meta_mysql_client_manager = MySQLClientManager(app_config.db_meta)
dw_mysql_client_manager = MySQLClientManager(app_config.db_dw)

if __name__ == '__main__':
    dw_mysql_client_manager.init()

    async def test():
        # async with 从连接池借连接，with 块结束自动归还
        async with dw_mysql_client_manager.session_factory() as session:
            sql = "select * from fact_order limit 10"
            result = await session.execute(text(sql))

            # mappings() 让每行可通过列名取值（如 row['order_id']）
            rows = result.mappings().fetchall()

            print(type(rows))
            print(type(rows[0]))
            print(rows[0]['order_id'])

    asyncio.run(test())
