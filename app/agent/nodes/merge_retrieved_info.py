from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState, TableInfoState, ColumnInfoState, MetricInfoState
from langgraph.runtime import Runtime

from app.entities.column_info import ColumnInfo
from app.entities.metric_info import MetricInfo
from app.entities.table_info import TableInfo
from app.entities.value_info import ValueInfo
from app.repositories.mysql.meta import meta_mysql_repository
from app.core.log import logger


async def merge_retrieved_info(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    """
    合并召回信息节点：将三类召回结果交叉关联并整理成面向 SQL 生成的结构。

    背景：
        召回阶段的三个节点（recall_column / recall_metric / recall_value）
        各自独立检索，产出相互割裂的字段、指标、取值。本节点是它们的
        fan-in 汇合点，需要完成以下拼接与补全：
            1. 字段索引：以 column.id 为 key 建立全部候选字段的索引；
            2. 指标补字段：指标 relevant_columns 引用的字段若未被召回，从
               MySQL 元数据库补查；
            3. 取值挂字段：把召回的值去重挂到所属字段的 examples 上，作为
               LLM 生成 WHERE 条件的枚举约束；
            4. 按表分组：以 table_id 将字段归组，产出表结构视角；
            5. 补主外键：为每张表强制补充 primary / foreign_key 字段，
               保证 LLM 能看到表间 JOIN 的关联字段；
            6. 转目标格式：转换为 TableInfoState / MetricInfoState。

    state 读/写：
        - 读：retrieved_column_infos / retrieved_metric_infos / retrieved_value_infos
        - 写：table_infos / metric_infos
        - context：meta_mysql_repository（元数据 MySQL，用于补查缺失信息）

    返回：
        仅包含 table_infos、metric_infos 的 state 增量字典。
    """
    writer = runtime.stream_writer
    writer("合并召回信息")

    retrieved_column_infos: list[ColumnInfo] = state["retrieved_column_infos"]
    retrieved_metric_infos: list[MetricInfo] = state["retrieved_metric_infos"]
    retrieved_value_infos: list[ValueInfo] = state["retrieved_value_infos"]

    meta_mysql_repository = runtime.context["meta_mysql_repository"]

    # ============================================================
    # 处理表信息
    # ============================================================
    # 以 id 为 key 建立字段索引，方便后续按 id 快速查找/去重
    retrieved_column_infos_map: dict[str, ColumnInfo] = {
        retrieved_column_info.id: retrieved_column_info
        for retrieved_column_info in retrieved_column_infos
    }

    # 将指标信息的相关字段信息补充到字段信息中
    # 指标通过 relevant_columns 引用其依赖字段，若该字段未被召回，
    # 则从 MySQL 补查，保证指标引用的字段一定存在于索引中
    for retrieved_metric_info in retrieved_metric_infos:
        for relevant_column in retrieved_metric_info.relevant_columns:
            if relevant_column not in retrieved_column_infos_map:
                column_info: ColumnInfo = await meta_mysql_repository.get_column_info_by_id(relevant_column)
                retrieved_column_infos_map[relevant_column] = column_info

    # 将字段取值加入到其所属字段的 examples
    # 目的是把"华北地区"这类真实取值作为枚举示例提供给 LLM，
    # 帮助其生成合法的 WHERE 条件
    for retrieved_value_info in retrieved_value_infos:
        value = retrieved_value_info.value
        column_id = retrieved_value_info.column_id
        # 取值所属字段若不在索引中，先补查 MySQL
        if column_id not in retrieved_column_infos_map:
            column_info: ColumnInfo = await meta_mysql_repository.get_column_info_by_id(column_id)
            retrieved_column_infos_map[column_id] = column_info
        # 去重追加到所属字段的 examples，避免同一取值重复
        if value not in retrieved_column_infos_map[column_id].examples:
            retrieved_column_infos_map[column_id].examples.append(value)

    # 按照表对字段信息进行分组
    # 以 table_id 为 key 将字段归组，便于后续按表维度补主外键、组装表结构
    table_to_columns_map: dict[str, list[ColumnInfo]] = {}
    for column_info in retrieved_column_infos_map.values():
        table_id = column_info.table_id
        if table_id not in table_to_columns_map:
            table_to_columns_map[table_id] = []
        table_to_columns_map[table_id].append(column_info)

    # TODO(bug): 应为 table_to_columns_map.keys()。dict 没有 key() 方法，
    #            当前写法运行到此处会直接抛 AttributeError，导致整条链路崩溃。
    # TODO(dead code): 下面 43-48 行已经完成过一次分组，此处 62-67 行重复执行，
    #                  前一段分组结果会被此处完全覆盖（前段为无效代码）。
    # 强制为表添加主外键信息
    # 保证每张表都包含 primary / foreign_key 字段，LLM 才能据此推导表间 JOIN
    for table_id in table_to_columns_map.keys():
        # 从 MySQL 查询该表的全部主键/外键字段
        key_columns: list[ColumnInfo] = await meta_mysql_repository.get_key_columns_info_by_table_id(table_id)
        column_ids = [column_info.id for column_info in table_to_columns_map[table_id]]
        # 仅追加尚未在表字段列表中的主外键，避免重复
        for key_column in key_columns:
            if key_column.id not in column_ids:
                table_to_columns_map[table_id].append(key_column)

    # 按照表对字段信息进行分组，整理成目标格式
    # TODO(dead code): 与上文 43-48 行重复，第一段分组逻辑可删除
    table_to_columns_map: dict[str, list[ColumnInfo]] = {}
    for column_info in retrieved_column_infos_map.values():
        table_id = column_info.table_id
        if table_id not in table_to_columns_map:
            table_to_columns_map[table_id] = []
        table_to_columns_map[table_id].append(column_info)

    # 逐表转换为 TableInfoState：补查表名/角色/描述，并将字段转换为 ColumnInfoState
    table_infos: list[TableInfoState] = []
    for table_id, column_infos in table_to_columns_map.items():
        table_info: TableInfo = await meta_mysql_repository.get_table_info_by_id(table_id)
        columns = [ColumnInfoState(
            name=column_info.name,
            type=column_info.type,
            role=column_info.role,
            examples=column_info.examples,
            description=column_info.description,
            alias=column_info.alias,
        ) for column_info in column_infos]

        table_info_state = TableInfoState(
            name=table_info.name,
            role=table_info.role,
            description=table_info.description,
            columns=columns
        )
        table_infos.append(table_info_state)

    # ============================================================
    # 处理指标信息：将指标实体转换为面向 LLM 的 MetricInfoState
    # ============================================================
    metric_infos: list[MetricInfoState] = [MetricInfoState(
        name=retrieved_metric_info.name,
        description=retrieved_metric_info.description,
        relevant_columns=retrieved_metric_info.relevant_columns,
        alias=retrieved_metric_info.alias,
    ) for retrieved_metric_info in retrieved_metric_infos]

    return {
        "table_infos": table_infos,
        "metric_infos": metric_infos,
    }
