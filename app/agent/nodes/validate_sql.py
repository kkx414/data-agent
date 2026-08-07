from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState
from langgraph.runtime import Runtime

from app.repositories.mysql.dw import dw_mysql_repository
from app.core.log import logger


async def validate_sql(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    """
    校验 SQL 节点：对生成的 SQL 做语法级校验，并据此决定链路走向。

    职责：
        使用 EXPLAIN 语句（仅做语法分析、不真正执行查询）验证 SQL 是否合法：
        - 语法正确：state["error"] 置为 None；
        - 语法错误：捕获异常，将错误信息写入 state["error"]。
        graph.py 中的条件边依据 error 是否为 None 决定分支走向：
        None -> run_sql；非空 -> correct_sql（进入纠错循环）。

    state 读/写：
        - 读：sql（待校验的 SQL）
        - 写：error（None 表示语法正确，否则为错误信息字符串）

    图中位置：
        上游 generate_sql；下游 run_sql（正确）或 correct_sql（错误）。

    返回：
        仅包含 error 的 state 增量字典。
    """
    writer = runtime.stream_writer
    writer({"type": "progress", "step": "校验SQL", "status": "running"})

    sql = state['sql']
    dw_mysql_repository = runtime.context['dw_mysql_repository']

    # 注意：此处 try/except 是本节点的业务逻辑（语法错误走 correct_sql 纠错分支），
    # 并非意外异常，因此捕获后不回抛，而是将错误信息写入 state["error"] 驱动条件边。
    try:
        await dw_mysql_repository.validate(sql)
        logger.info("SQL语法正确")
        writer({"type": "progress", "step": "校验SQL", "status": "success"})
        return {"error": None}
    except Exception as e:
        logger.info(f"SQL语法错误：{str(e)}")
        writer({"type": "progress", "step": "校验SQL", "status": "error"})
        return {"error": str(e)}
