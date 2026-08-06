import yaml
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from app.core.log import logger
from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState
from langgraph.runtime import Runtime

from app.prompt.prompt_loader import load_prompt


async def filter_metric(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    """
    过滤指标信息节点：从 merge_retrieved_info 产出的候选指标中，裁剪出回答
    用户问题所必需的指标。

    职责：
        merge_retrieved_info 的指标列表是"召回优先、宁多勿缺"，可能包含冗余、
        口径相近或与问题无关的指标。本节点借助 LLM（filter_metric_info 提示词）
        筛选出本次查询真正用于度量/统计的指标：
            1. 提示词要求输出指标名称的 JSON 数组（如 ["转正人数", "转正率"]），
               并允许输出空数组 [] 表示"问题不涉及任何指标"；
            2. 以指标名为 key 过滤 metric_infos，仅保留被选中的指标。
        裁剪结果写回 metric_infos，作为后续 generate_sql 严格遵循的指标口径依据。

    state 读/写：
        - 读：query        用户原始问题
        - 读：metric_infos merge_retrieved_info 产出的候选指标集合
        - 写：metric_infos 裁剪后的必需指标集合

    与 filter_table 的关系：
        两者在 merge_retrieved_info 之后并行执行，分别写 metric_infos 与
        table_infos 两个不同的 key，LangGraph 自动合并，无写冲突。

    返回：
        仅包含 metric_infos 的 state 增量字典。
    """
    writer = runtime.stream_writer
    writer("过滤指标信息")
    query = state["query"]
    metric_infos = state["metric_infos"]

    # 构造 LLM 筛选链路：prompt | LLM | JSON 解析
    # 注意：filter_metric_info 提示词输出的是【指标名称数组】，
    #       而不是 filter_table 的 {"表名": ["字段1", ...]} 对象格式。
    prompt = PromptTemplate(template=load_prompt("filter_metric_info"), input_variables=['query', 'metric_infos'])
    output_parser = JsonOutputParser()
    from app.agent.llm import llm
    chain = prompt | llm | output_parser

    # 将候选指标信息序列化为 YAML 文本喂给 LLM
    # - allow_unicode=True: 保证中文指标名正常展示
    # - sort_keys=False:    保持指标原有顺序，方便与结果对齐
    result = await chain.ainvoke({"query": query,
                                  "metric_infos": yaml.dump(metric_infos, allow_unicode=True, sort_keys=False)})

    # 指标级裁剪：仅保留 LLM 选中的指标（以指标名为 key 匹配）
    filtered_metric_info = [metric_info for metric_info in metric_infos if metric_info['name'] in result]

    # TODO(风险): 提示词允许输出 [] 表示"问题不涉及指标"，此时 filtered_metric_info
    #             为空是【合法结果】；但若 LLM 解析失败返回了非数组，则可能是异常，
    #             建议补充防御：result 非数组时告警并回退保留原指标集合。
    logger.info(f"过滤后的指标信息：{[filtered_metric_info['name'] for filtered_metric_info in filtered_metric_info]}")

    return {"metric_infos": filtered_metric_info}
