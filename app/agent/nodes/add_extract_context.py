
from datetime import date

from app.core.log import logger

from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState, DateInfoState, DBInfoState
from langgraph.runtime import Runtime


async def add_extract_context(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    """
    补充上下文节点：为 generate_sql 注入数据库环境与当前时间信息。

    职责：
        在 SQL 生成前补齐两类 LLM 需要的"外部事实"：
            1. 时间信息（date_info）：当前日期 / 星期 / 季度，帮助 LLM 解析
               "本月""最近三个月""本季度"等相对时间表述；
            2. 数据库信息（db_info）：数据库方言（dialect）与版本，帮助 LLM
               生成语法严格符合目标数据库的 SQL。
        这两份信息分别对应 generate_sql 提示词中的 {date_info}、{db_info} 占位符。

    state 读/写：
        - 读：无（仅依赖 context 中的 dw_mysql_repository）
        - 写：date_info（当前时间信息）、db_info（数据库环境信息）

    context 依赖：
        - dw_mysql_repository：数据仓库（DW）库只读访问，用于查数据库版本/方言

    返回：
        仅包含 date_info、db_info 的 state 增量字典。
    """
    writer = runtime.stream_writer
    writer("添加额外的上下文")

    dw_mysql_repository = runtime.context['dw_mysql_repository']

    # ---------- 构造当前时间信息 ----------
    # 取系统当前日期，拆成 日期/星期/季度 三份独立信息
    today = date.today()
    date_str = today.strftime("%Y-%m-%d")          # 如 "2026-08-06"
    weekday = today.strftime("%A")                 # 如 "Thursday"（英文星期名）
    quarter = f"Q{(today.month - 1) // 3 + 1}"     # 季度：1月->Q1, 4月->Q2, 7月->Q3, 10月->Q4
    date_info = DateInfoState(date=date_str, weekday=weekday, quarter=quarter)

    # ---------- 查询数据库环境信息 ----------
    # get_db_info 返回 {"version": "...", "dialect": "mysql"}，
    # 用 **db 展开为关键字参数构造 DBInfoState（字段需与返回 dict 完全对齐）
    db = await dw_mysql_repository.get_db_info()
    db_info = DBInfoState(**db)
    logger.info(f"数据库信息: {db_info}")
    logger.info(f"日期信息: {date_info}")

    # TODO(风险): 返回的 key 是 date_info，而 state.py 中声明的字段名是 data_info，
    #             两者不一致（state.py 为笔误）。运行时 LangGraph 会按 date_info
    #             生成未声明字段，建议统一为 date_info（与 generate_sql 提示词占位符一致）。
    return {"date_info": date_info, "db_info": db_info}
