from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState
from langgraph.runtime import Runtime

from app.repositories.mysql.dw import dw_mysql_repository
from app.core.log import logger


async def validate_sql(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    writer = runtime.stream_writer
    writer("校验sql")

    sql = state['sql']
    dw_mysql_repository = runtime.context['dw_mysql_repository']

    try:
        await dw_mysql_repository.validate(sql)
        logger.info(f"SQL语法正确")
        return {"error": None}
    except Exception as e:
        logger.info(f"SQL语法错误：{str(e)}")
        return {"error": str(e)}


