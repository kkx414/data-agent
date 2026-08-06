from typing import TypedDict

from app.entities.column_info import ColumnInfo
from app.entities.metric_info import MetricInfo
from app.entities.value_info import ValueInfo


class MetricInfoState(TypedDict):
    name: str
    description: str
    relevant_columns: list[str]
    alias: list[str]





class ColumnInfoState(TypedDict):
    name: str
    type: str
    role: str
    examples: list
    description: str
    alias: list[str]



class TableInfoState(TypedDict):
    name: str
    role: str
    description: str
    columns: list[ColumnInfoState]

class DateInfoState(TypedDict):
    date:str
    weekday:str
    quarter:str

class DBInfoState(TypedDict):
    dialect: str
    version: str


class DataAgentState(TypedDict):
    query: str
    error: str
    keywords: list[str]
    retrieved_column_infos: list[ColumnInfo]    # 检索到的字段信息
    retrieved_metric_infos: list[MetricInfo]  # 检索到的指标信息
    retrieved_value_infos: list[ValueInfo]

    table_infos: list[TableInfoState]   # 表信息
    metric_infos: list[MetricInfoState]    # 指标信息

    date_info:DateInfoState
    db_info:DBInfoState

    sql: str