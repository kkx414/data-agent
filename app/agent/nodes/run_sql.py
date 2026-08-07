from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState
from langgraph.runtime import Runtime

from app.repositories.mysql.dw import dw_mysql_repository
from app.core.log import logger


async def run_sql(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    """
    执行 SQL 节点：在数据仓库（DW）库中执行最终 SQL，是链路的终点。

    职责：
        在 SQL 通过语法校验（validate_sql）或已被修正（correct_sql）后，
        真正在 DW 库执行查询，记录执行结果日志。当前实现仅打印结果，
        尚未将结果集写回 state（如需向用户返回查询结果，可在此扩展
        写入新的 state key）。

    state 读/写：
        - 读：sql（待执行的 SQL）
        - 写：无（仅日志输出，不产生 state 增量）

    图中位置：
        上游 validate_sql（语法正确分支）或 correct_sql（修正后）；
        下游 END（整个链路在此终止）。

    返回：
        无返回值（节点不产出 state 增量字典）。
    """
    writer = runtime.stream_writer
    writer({"type": "progress", "step": "执行SQL", "status": "running"})

    try:
        sql = state["sql"]
        dw_mysql_repository = runtime.context["dw_mysql_repository"]

        result = await dw_mysql_repository.run(sql)
        logger.info(f"SQL执行结果：{result}")

        writer({"type": "progress", "step": "执行SQL", "status": "success"})
        logger.info("执行SQL成功")

    except Exception as e:
        logger.info(f"执行SQL失败：{e}")
        writer({"type": "progress", "step": "执行SQL", "status": "error"})
        raise
