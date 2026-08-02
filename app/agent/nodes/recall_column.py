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
    writer = runtime.stream_writer
    writer("召回字段")

    keywords = state["keywords"]
    query = state["query"]
    column_qdrant_repository = runtime.context["column_qdrant_repository"]
    embedding_client = runtime.context["embedding_client"]

    # 先借助大模型来扩展关键词
    # chain = prompt | llm |output_parsers
    prompt = PromptTemplate(template=load_prompt("extend_keywords_for_column_recall"), input_variables=[])
    output_parser = JsonOutputParser()
    chain = prompt | llm | output_parser
    result = await chain.ainvoke({"query": query})
    keywords = set(keywords + result)


    # 从qdrant中检索字段信息
    column_info_map: dict[str, ColumnInfo] = {}
    for keyword in keywords:
        # 对keyword进行向量化并在qdrant中进行检索
        embedding = await embedding_client.aembed_query(keyword)
        current_column_infos: list[ColumnInfo] = await column_qdrant_repository.search(embedding, score_threshold=0.6, limit=10)
        for column_info in current_column_infos:
            if column_info.id not in column_info_map:
                column_info_map[column_info.id] = column_info

        retrieved_column_infos: list[ColumnInfo] = list(column_info_map.values())

        logger.info(f"检索到的字段信息: {list(column_info_map.keys())}")
        return {"retrieved_column_infos": retrieved_column_infos}

