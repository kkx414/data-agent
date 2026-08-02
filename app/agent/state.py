from typing import TypedDict

from app.entities.column_info import ColumnInfo


class DataAgentState(TypedDict):
    query: str
    error: str
    keywords: list[str]
    retrieved_column_infos: list[ColumnInfo]    # 检索到的字段信息