import jieba.analyse

from app.core.log import logger
from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState
from langgraph.runtime import Runtime


async def extract_keywords(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    """
    提取关键词节点：从用户原始问题中抽取检索关键词。

    职责：
        使用 jieba 分词（TF-IDF + 词性白名单过滤）从 query 中抽取关键词，
        并将原始 query 整体追加进关键词集合，保证"华北地区"这类整体表述
        不被分词拆散。输出的 keywords 将作为后续三个召回节点
        （字段 / 指标 / 取值）的检索输入。

    state 读/写：
        - 读：query        用户原始问题
        - 写：keywords     检索关键词列表（含原始 query）

    返回：
        仅包含 keywords 的 state 增量字典（LangGraph 会自动合并进全局 state）。
    """
    writer = runtime.stream_writer
    writer("提取关键词")

    query = state["query"]

    # 词性白名单：只保留对检索有意义的实词，过滤掉虚词/标点/语气词等噪音
    allow_pos = (
        "n",  # 名词: 数据、服务器、表格
        "nr", # 人名: 张三、李四
        "ns", # 地名: 北京、上海
        "nt", # 机构团体名: 政府、学校、某公司
        "nz", # 其他专有名词: Unicode、哈希算法、诺贝尔奖
        "v",  # 动词: 运行、开发
        "vn", # 名动词: 工作、研究
        "a",  # 形容词: 美丽、快速
        "an", # 名形词: 难度、合法性、复杂度
        "eng",# 英文
        "i",  # 成语
        "l",  # 常用固定短语
    )

    # jieba 基于 TF-IDF 提取 Top 关键词（词性受 allowPOS 约束）
    keywords = jieba.analyse.extract_tags(query, allowPOS=allow_pos)

    # TODO(bug): keywords 是 list，query 是 str，`keywords + query` 会抛
    #            TypeError（list 只能与 list 拼接），应为 `keywords + [query]`
    #            或直接 `keywords.append(query)`。
    keywords = list(set(keywords + query))
    logger.info(f"抽取关键词：{keywords}")
    return {"keywords": keywords}
