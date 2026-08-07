from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate

from app.agent.context import DataAgentContext
from app.agent.llm import llm
from app.agent.state import DataAgentState
from langgraph.runtime import Runtime
from app.core.log import logger
from app.entities.value_info import ValueInfo
from app.prompt.prompt_loader import load_prompt
from app.repositories.es import value_es_repository


async def recall_value(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    """
    召回取值节点：基于关键词在 ES 全文索引中检索字段的实际取值。

    职责：
        召回字段的具体取值（如"华北地区""华东地区"），用于：
        1. 在 merge_retrieved_info 中挂载到所属字段的 examples；
        2. 为 LLM 生成 WHERE 条件时提供合法的枚举值约束。

    流程：
        1. 借助 LLM 扩展关键词（面向取值场景）；
        2. 将扩展后的关键词与原关键词合并去重；
        3. 直接在 ES 中做全文检索（取值无需向量化，走全文索引）；
        4. 以 value_info.id 去重合并，写入 retrieved_value_infos。

    与 recall_column / recall_metric 的区别：
        - 检索目标是字段取值（维度值），走 ES 全文检索而非 Qdrant 向量检索。

    图中位置：
        上游 extract_keywords（keywords 检索输入）；下游 merge_retrieved_info
        （三路并行召回之一，仅召回字段的实际取值）。

    state 读/写：
        - 读：query、keywords
        - 写：retrieved_value_infos: list[ValueInfo]

    返回：
        仅包含 retrieved_value_infos 的 state 增量字典。
    """
    writer = runtime.stream_writer
    writer({"type": "progress", "step": "召回取值", "status": "running"})

    query = state["query"]
    keywords = state["keywords"]
    value_es_repository = runtime.context["value_es_repository"]

    try:
        # 扩展关键词：让 LLM 基于 query 产出取值检索词
        prompt = PromptTemplate(template=load_prompt("extend_keywords_for_value_recall"), input_variables=['query'])
        output_parser = JsonOutputParser()
        chain = prompt | llm | output_parser
        result = await chain.ainvoke({"query": query})
        keywords = set(keywords + result)

        # 根据关键词召回字段取值
        value_infos_map: dict[str, ValueInfo] = {}
        for keyword in keywords:
            # ES 全文检索：按关键词匹配取值的 value / 所属字段等
            current_value_infos: list[ValueInfo] = await value_es_repository.search(keyword)
            # 按 id 去重合并当前关键词的检索结果
            for current_value_info in current_value_infos:
                if current_value_info.id not in value_infos_map:
                    value_infos_map[current_value_info.id] = current_value_info

        # 循环结束后统一返回，保证所有关键词都参与了检索
        retrieved_value_infos: list[ValueInfo] = list(value_infos_map.values())
        logger.info(f"检索到字段取值: {list(value_infos_map.keys())}")

        writer({"type": "progress", "step": "召回取值", "status": "success"})
        logger.info("召回取值成功")
        return {"retrieved_value_infos": retrieved_value_infos}

    except Exception as e:
        logger.info(f"召回取值失败：{e}")
        writer({"type": "progress", "step": "召回取值", "status": "error"})
        raise
