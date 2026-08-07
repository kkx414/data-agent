import yaml
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate

from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState
from langgraph.runtime import Runtime

from app.prompt.prompt_loader import load_prompt
from app.core.log import logger


async def correct_sql(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    """
    校正 SQL 节点：根据数据库执行错误信息，让 LLM 最小化修正生成的 SQL。

    职责：
        generate_sql 或上一轮 correct_sql 产出的 SQL 被 validate_sql 判定为
        有误（state["error"] 非空）时进入本节点。借助 correct_sql 提示词，
        结合表结构 / 指标口径 / 时间 / 数据库环境，仅修复导致 SQL 无法执行的
        问题，严格保持原业务语义不变。

    state 读/写：
        - 读：table_infos / metric_infos / date_info / db_info（修正依据）
        - 读：query（原始问题）、sql（待修正 SQL）、error（执行错误信息）
        - 写：sql（修正后的 SQL，覆盖原值）

    图中位置：
        上游 validate_sql（条件边，error 非空时进入）；
        下游 run_sql（修正后直接执行）。若执行仍失败会再次进入 validate_sql，
        形成"校验 → 修正 → 再执行"的纠错循环。

    返回：
        仅包含 sql 的 state 增量字典。
    """
    writer = runtime.stream_writer
    writer({"type": "progress", "step": "校正SQL", "status": "running"})

    try:
        table_infos = state["table_infos"]
        metric_infos = state["metric_infos"]
        date_info = state["date_info"]
        db_info = state["db_info"]
        query = state["query"]
        sql = state["sql"]
        error = state["error"]

        # 构造修正链路：prompt | LLM | 纯文本解析
        # 将上下文（表/指标/时间/环境）与错误信息序列化为 YAML 喂给 LLM，
        # 输出为修正后的纯 SQL 文本
        prompt = PromptTemplate(template=load_prompt("correct_sql"),
                                input_variables=['table_infos', 'metric_infos', 'date_info', 'db_info', 'query', 'sql', 'error'])
        output_parser = StrOutputParser()
        from app.agent.llm import llm
        chain = prompt | llm | output_parser

        result = await chain.ainvoke({
            'table_infos': yaml.dump(table_infos, allow_unicode=True, sort_keys=False),
            'metric_infos': yaml.dump(metric_infos, allow_unicode=True, sort_keys=False),
            'date_info': yaml.dump(date_info, allow_unicode=True, sort_keys=False),
            'db_info': yaml.dump(db_info, allow_unicode=True, sort_keys=False),
            'query': query,
            'sql': sql,
            'error': error
        })

        logger.info(f"校正后的SQL：{result}")

        writer({"type": "progress", "step": "校正SQL", "status": "success"})
        logger.info("校正SQL成功")
        return {'sql': result}

    except Exception as e:
        logger.info(f"校正SQL失败：{e}")
        writer({"type": "progress", "step": "校正SQL", "status": "error"})
        raise
