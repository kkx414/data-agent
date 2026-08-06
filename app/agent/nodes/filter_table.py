import yaml
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from app.core.log import logger
from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState, TableInfoState
from langgraph.runtime import Runtime

from app.entities.table_info import TableInfo
from app.prompt.prompt_loader import load_prompt


async def filter_table(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    """
    过滤表信息节点：从 merge_retrieved_info 产出的候选表中，裁剪出回答用户问题
    所必需的表和字段。

    职责：
        merge_retrieved_info 是"召回优先、宁多勿缺"，候选表往往包含噪音表。
        本节点借助 LLM（filter_table 提示词）在候选 schema 范围内做双重裁剪：
            1. 表级裁剪：丢弃与回答该问题无关的表；
            2. 字段级裁剪：对保留的表，仅保留本次查询实际会用到的字段。
        裁剪结果写回 table_infos，作为后续 generate_sql 的 schema 输入，
        直接决定 SQL 生成的准确性与 token 开销。

    state 读/写：
        - 读：query        用户原始问题
        - 读：table_infos  merge_retrieved_info 产出的候选表集合
        - 写：table_infos  裁剪后的"最小必需"表集合

    与 filter_metric 的关系：
        两者在 merge_retrieved_info 之后并行执行，分别写 table_infos 与
        metric_infos 两个不同的 key，LangGraph 自动合并，无写冲突。

    返回：
        仅包含 table_infos 的 state 增量字典。
    """
    writer = runtime.stream_writer
    writer("过滤表信息")

    query = state["query"]
    table_infos = state["table_infos"]

    # 构造 LLM 筛选链路：prompt | LLM | JSON 解析
    # 提示词要求输出 {"表名": ["字段1", "字段2", ...]} 的 JSON 对象
    prompt = PromptTemplate(template=load_prompt("filter_table_info"), input_variables=['query', 'table_infos'])
    output_parser = JsonOutputParser()
    from app.agent.llm import llm
    chain = prompt | llm | output_parser

    # 将候选表信息序列化为 YAML 文本喂给 LLM
    # - allow_unicode=True: 保证中文表名/字段名正常展示
    # - sort_keys=False:    保持表与字段的原有顺序，方便与结果对齐
    result = await chain.ainvoke({"query": query,
                         "table_infos": yaml.dump(table_infos, allow_unicode=True, sort_keys=False)})

    # 按 LLM 筛选结果裁剪表与字段
    filtered_table_infos: list[TableInfoState] = []
    for table_info in table_infos:
        # 表级裁剪：仅保留 LLM 选中的表（以表名为 key 匹配）
        if table_info["name"] in result:
            # 字段级裁剪：仅保留 LLM 选中且当前表中真实存在的字段
            # TODO(风险): 此处直接原地修改了 state 中的 table_info['columns']，
            #            若 LLM 选中了表但字段全部匹配不上，会得到一个
            #            空字段的表被加入结果（与提示词"表必须含被选中字段"矛盾），
            #            建议补充兜底：字段为空时丢弃该表。
            table_info['columns'] = [column_info for
                                     column_info in table_info['columns'] if column_info["name"] in result[table_info["name"]]]
            filtered_table_infos.append(table_info)

    # TODO(风险): 若 LLM 未选中任何表（result 为空或解析失败），filtered_table_infos
    #            会为空，导致下游 generate_sql 拿不到任何 schema。建议空结果时
    #            回退保留原候选表并告警，避免截断链路。

    logger.info(f"过滤后的表信息: {[filtered_table_info['name'] for filtered_table_info in filtered_table_infos]}")
    return {"table_infos": filtered_table_infos}
