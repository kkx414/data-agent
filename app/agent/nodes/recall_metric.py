import keyword

from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from app.core.log import logger
from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState
from langgraph.runtime import Runtime
from app.agent.llm import llm
from app.entities.metric_info import MetricInfo
from app.prompt.prompt_loader import load_prompt


async def recall_metric(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    """
    召回指标节点：基于关键词在 Qdrant 向量库中检索候选指标。

    流程：
        1. 借助 LLM 扩展关键词（面向指标场景，补充指标相关的同义表述）；
        2. 将扩展后的关键词与原关键词合并去重；
        3. 对每个关键词做向量化（aembed_query）；
        4. 在 Qdrant 中检索相似指标；
        5. 以 metric.id 去重合并，写入 retrieved_metric_infos。

    与 recall_column 的区别：
        - 检索目标是指标（销售额、订单量等可计算指标）而非字段；
        - 未显式传入 score_threshold，使用向量库默认相似度阈值。

    state 读/写：
        - 读：query、keywords
        - 写：retrieved_metric_infos: list[MetricInfo]

    返回：
        仅包含 retrieved_metric_infos 的 state 增量字典。
    """
    writer = runtime.stream_writer
    writer("召回指标信息")

    query = state["query"]
    keywords = state["keywords"]
    embedding_client = runtime.context["embedding_client"]
    metric_qdrant_repository = runtime.context["metric_qdrant_repository"]

    # 扩展关键词：让 LLM 基于 query 产出指标检索词（如"销售额"→"成交金额、营收"）
    prompt = PromptTemplate(template=load_prompt("extend_keywords_for_metric_recall"), input_variables=['query'])
    output_parser = JsonOutputParser()
    chain = prompt | llm | output_parser
    result = await chain.ainvoke({"query": query})
    keywords = set(keywords + result)

    metric_info_map: dict[str, MetricInfo] = {}
    for keyword in keywords:
        # 对 keyword 进行向量化并在 qdrant 中进行检索
        embedding = await embedding_client.aembed_query(keyword)
        current_metric_infos: list[MetricInfo] = await metric_qdrant_repository.search(embedding)
        # 按 id 去重合并当前关键词的检索结果
        for metric_info in current_metric_infos:
            if metric_info.id not in metric_info_map:
                metric_info_map[metric_info.id] = metric_info

        # TODO(bug): 与 recall_column 相同，return 位于 for 循环体内，
        #            只处理了第一个关键词即返回，应将下方三行移出循环。
        retrieved_metric_infos: list[MetricInfo] = list(metric_info_map.values())

        logger.info(f"检索到的字段信息: {list(metric_info_map.keys())}")
        return {"retrieved_metric_infos": retrieved_metric_infos}
