from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate

from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState
from langgraph.runtime import Runtime
from app.agent.llm import llm
from app.entities.column_info import ColumnInfo
from app.prompt.prompt_loader import load_prompt
from app.repositories.qdrant import column_qdrant_repository
from app.core.log import logger


async def recall_column(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    """
    召回字段节点：基于关键词在 Qdrant 向量库中检索候选字段。

    流程：
        1. 借助 LLM 扩展关键词（补充同义词、业务别称等，弥补用户表述与
           元数据命名之间的差异）；
        2. 将扩展后的关键词与原关键词合并去重；
        3. 对每个关键词做向量化（aembed_query）；
        4. 在 Qdrant 中按相似度检索字段（阈值 0.6，Top 10）；
        5. 以 column.id 去重合并，写入 retrieved_column_infos。

    图中位置：
        上游 extract_keywords（keywords 检索输入）；下游 merge_retrieved_info
        （三路并行召回之一，仅召回字段信息）。

    state 读/写：
        - 读：query、keywords
        - 写：retrieved_column_infos: list[ColumnInfo]

    返回：
        仅包含 retrieved_column_infos 的 state 增量字典。
    """
    writer = runtime.stream_writer
    writer({"type": "progress", "step": "召回字段", "status": "running"})

    keywords = state["keywords"]
    query = state["query"]
    column_qdrant_repository = runtime.context["column_qdrant_repository"]
    embedding_client = runtime.context["embedding_client"]

    try:
        # 先借助大模型来扩展关键词
        # chain = prompt | llm | output_parsers
        prompt = PromptTemplate(template=load_prompt("extend_keywords_for_column_recall"), input_variables=['query'])
        output_parser = JsonOutputParser()
        chain = prompt | llm | output_parser
        result = await chain.ainvoke({"query": query})
        # result 为 LLM 输出的关键词列表（JsonOutputParser 解析），与原关键词合并去重
        keywords = set(keywords + result)

        # 从 qdrant 中检索字段信息
        column_info_map: dict[str, ColumnInfo] = {}
        for keyword in keywords:
            # 对 keyword 进行向量化并在 qdrant 中进行检索
            embedding = await embedding_client.aembed_query(keyword)
            current_column_infos: list[ColumnInfo] = await column_qdrant_repository.search(embedding, score_threshold=0.6, limit=10)
            # 按 id 去重合并当前关键词的检索结果，避免同一字段被多次召回
            for column_info in current_column_infos:
                if column_info.id not in column_info_map:
                    column_info_map[column_info.id] = column_info

        retrieved_column_infos: list[ColumnInfo] = list(column_info_map.values())

        logger.info(f"检索到的字段信息: {list(column_info_map.keys())}")

        writer({"type": "progress", "step": "召回字段", "status": "success"})
        logger.info("召回字段成功")
        return {"retrieved_column_infos": retrieved_column_infos}

    except Exception as e:
        logger.info(f"召回字段失败：{e}")
        writer({"type": "progress", "step": "召回字段", "status": "error"})
        raise
