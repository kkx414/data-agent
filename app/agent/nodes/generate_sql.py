import yaml
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate

from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState
from langgraph.runtime import Runtime

from app.prompt.prompt_loader import load_prompt
from app.core.log import logger


async def generate_sql(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    """
    生成 SQL 节点：将用户自然语言问题转换为可执行 SQL，是链路的核心生成点。

    职责：
        基于已过滤的表结构（table_infos）与指标口径（metric_infos），以及
        add_extract_context 注入的时间（date_info）与数据库环境（db_info），
        借助 generate_sql 提示词让 LLM 生成语法严格符合目标数据库的 SQL。
        生成结果未做任何后处理，直接以字符串写入 state["sql"]。

    state 读/写：
        - 读：table_infos / metric_infos / date_info / db_info / query
        - 写：sql（生成的 SQL）

    图中位置：
        上游 add_extract_context（提供时间与数据库环境，对应提示词
        {date_info}、{db_info} 占位符）；下游 validate_sql（语法校验）。

    返回：
        仅包含 sql 的 state 增量字典。
    """
    writer = runtime.stream_writer
    writer({"type": "progress", "step": "生成SQL", "status": "running"})

    try:
        table_infos = state["table_infos"]
        metric_infos = state["metric_infos"]
        date_info = state["date_info"]
        db_info = state["db_info"]
        query = state["query"]

        # 构造生成链路：prompt | LLM | 纯文本解析
        # 将表/指标结构序列化为 YAML 喂给 LLM（allow_unicode 保证中文正常展示，
        # sort_keys=False 保持原有顺序），输出为纯 SQL 文本
        prompt = PromptTemplate(template=load_prompt("generate_sql"), input_variables=['table_infos', 'metric_infos', 'date_info', 'db_info', 'query'])
        output_parser = StrOutputParser()
        from app.agent.llm import llm
        chain = prompt | llm | output_parser

        result = await chain.ainvoke({
            'table_infos': yaml.dump(table_infos, allow_unicode=True, sort_keys=False),
            'metric_infos': yaml.dump(metric_infos, allow_unicode=True, sort_keys=False),
            'date_info': yaml.dump(date_info, allow_unicode=True, sort_keys=False),
            'db_info': yaml.dump(db_info, allow_unicode=True, sort_keys=False),
            'query': query
        })

        logger.info(f"生成的SQL：{result}")

        writer({"type": "progress", "step": "生成SQL", "status": "success"})
        logger.info("生成SQL成功")
        return {'sql': result}

    except Exception as e:
        logger.info(f"生成SQL失败：{e}")
        writer({"type": "progress", "step": "生成SQL", "status": "error"})
        raise
