"""
数据仓库（DW）MySQL Repository
==============================

封装对 MySQL dw 库的只读查询，为 MetaKnowledgeService 提供
字段类型和取值示例。

注意：本 Repository 只读不写。写入 meta 库的操作由
MetaMySQLRepository 负责。
"""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class DWMySQLRepository:
    """
    dw 库数据访问层。

    每个方法接收一个 AsyncSession（从连接池借出的连接），
    执行原生 SQL 后返回结构化结果。
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_column_type(self, table_name) -> dict[str, str]:
        """
        查询指定表中所有字段的数据类型。

        使用 SHOW COLUMNS 而非 information_schema.COLUMNS：
            SHOW COLUMNS 直接返回当前库的表结构，无需指定 schema，
            且性能更好（不跨库查询）。

        Returns:
            {'province': 'varchar(50)', 'order_amount': 'decimal(10,2)', ...}
        """
        sql = f"show columns from {table_name}"
        result = await self.session.execute(text(sql))
        result_dict = result.mappings().fetchall()
        # SHOW COLUMNS 返回列：Field, Type, Null, Key, Default, Extra
        # 只取 Field→Type 映射，其余列丢弃
        return {row['Field']: row['Type'] for row in result_dict}

    async def get_column_value(self, table_name, column_name, limit=10):
        """
        查询某个字段的 distinct 取值示例。

        distinct 去重：同一取值（如 '华北'）只返回一次。
        limit=10：只取 10 条示例，避免大表全量 distinct 导致慢查询。

        Returns:
            ['华北', '华东', '华南', ...]
            —— 直接返回值列表，用于写入 ES 或展示为 examples。
        """
        sql = f"select distinct {column_name} from {table_name} limit {limit}"
        result = await self.session.execute(text(sql))

        # 查询只有一列，直接取 row[0] 而非 row['column_name']
        # 原因：表名和列名由外部参数拼接，可能含特殊字符，
        # 用索引取值避免转义问题
        return [row[0] for row in result.fetchall()]

    async def get_db_info(self):
        sql = "select version()"

        result = await self.session.execute(text(sql))

        version = result.scalar()
        dialect = self.session.bind.dialect.name
        return {
            'version': version,
            'dialect': dialect,
        }

    async def validate(self, sql):
        sql = f"explain {sql}"
        await self.session.execute(text(sql))

    async def run(self, sql) -> list[dict]:
        result = await self.session.execute(text(sql))
        return [dict(row) for row in result.mappings().fetchall()]

