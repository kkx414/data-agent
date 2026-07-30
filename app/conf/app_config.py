"""
应用配置加载模块
================

这个文件是整个项目的"配置中心"。它负责从 YAML 配置文件（conf/app_config.yaml）
中读取所有运行参数，并转换成 Python 对象供其他模块使用。

打个比方：这就像一个"总开关面板"，上面有控制数据库连接的旋钮、控制日志输出的按钮、
控制 Qdrant 地址的开关等等。项目里的任何模块想获取配置信息，都从这一个入口拿，
这样当需要修改某个参数时，只需改 app_config.yaml 一个地方就行。

工作流程：
1. 定义一系列 dataclass（数据类），每个类对应 YAML 中的一个配置段
2. 用 OmegaConf 库读取 app_config.yaml 文件
3. OmegaConf 自动把 YAML 内容和 dataclass 定义"合并校验"
4. 最终生成一个全局唯一的 app_config 对象

数据类（dataclass）是什么？
    Python 自带的一种简化类定义方式。用 @dataclass 装饰后，可以省去写 __init__ 方法，
    字段直接声明即可，Python 自动生成构造函数。这里用它来做"配置模板"。
"""

# =============================================================================
# 导入依赖
# =============================================================================

# dataclass：Python 内置的装饰器，用来简化数据类的定义
# 加了 @dataclass 后，类会自动生成 __init__、__repr__ 等方法
from dataclasses import dataclass

# Path：Python 标准库 pathlib 提供的路径处理类，比字符串拼接路径更安全、更跨平台
# 这里用于拼接配置文件的实际存储路径
from pathlib import Path

# OmegaConf：一个强大的配置管理库，支持 YAML 加载、类型校验、配置合并
# 官网文档：https://omegaconf.readthedocs.io/
from omegaconf import OmegaConf


# =============================================================================
# 一、日志相关配置类
# =============================================================================
# 对应 app_config.yaml 中 logging 段下的各个子项

@dataclass
class File:
    """
    文件日志配置

    控制日志写入本地文件时的行为，比如写到哪个目录、每个文件多大时自动分割、
    旧日志保留多少天等。

    Attributes:
        enable (bool):  是否启用文件日志（True = 写入文件，False = 不写）
        level (str):    日志级别，如 "INFO"（记录一般信息）、"DEBUG"（调试详情）、
                        "WARNING"（警告）、"ERROR"（错误）
        path (str):     日志文件保存目录，如 "logs"
        rotation (str): 日志文件滚动策略，如 "10 MB" 表示单个文件超过 10MB 时
                        自动创建新文件
        retention (str):旧日志保留时长，如 "7 days" 表示只保留最近 7 天的日志
    """
    enable: bool       # 是否启用文件日志
    level: str         # 日志级别
    path: str          # 日志文件存放路径
    rotation: str      # 单个文件最大尺寸，超限自动分割
    retention: str     # 旧日志保留天数


@dataclass
class Console:
    """
    控制台日志配置

    控制日志在终端（命令行窗口）中的显示行为。

    Attributes:
        enable (bool): 是否在控制台输出日志（True = 显示，False = 不显示）
        level (str):   控制台输出的日志级别，同 File.level
    """
    enable: bool       # 是否在控制台输出日志
    level: str         # 控制台日志级别


@dataclass
class LoggingConfig:
    """
    日志总配置

    把文件日志和控制台日志的配置组合在一起，对应 YAML 中的 logging 段。

    Attributes:
        file (File):       文件日志配置对象
        console (Console): 控制台日志配置对象
    """
    file: File           # 文件日志子配置
    console: Console     # 控制台日志子配置


# =============================================================================
# 二、数据库相关配置类
# =============================================================================
# 对应 app_config.yaml 中 db_meta 和 db_dw 段

@dataclass
class DBConfig:
    """
    数据库连接配置

    封装了连接一个 MySQL 数据库所需的全部信息。项目中使用了两个数据库，
    所以会有两个 DBConfig 实例：
    - db_meta：元数据库（存储表结构、字段定义、指标定义等元数据）
    - db_dw：   数据仓库（存储实际的业务数据，如订单、用户等）

    Attributes:
        host (str):     数据库服务器的地址，如 "localhost"（本机）或 IP 地址
        port (int):     数据库端口号，MySQL 默认是 3306
        user (str):     登录数据库的用户名
        password (str): 登录数据库的密码
        database (str): 要连接的具体数据库名称，如 "meta" 或 "dw"
    """
    host: str         # 数据库主机地址
    port: int         # 端口号（MySQL 默认 3306）
    user: str         # 用户名
    password: str     # 密码
    database: str     # 数据库名称


# =============================================================================
# 三、Qdrant 向量数据库配置
# =============================================================================
# 对应 app_config.yaml 中 qdrant 段

@dataclass
class QdrantConfig:
    """
    Qdrant 向量数据库配置

    Qdrant 是一个专门存储和检索"向量"的数据库。向量可以理解为一串数字，
    用来表示文本的语义含义。相似的文本，其向量在数学空间中也更接近。

    Attributes:
        host (str):           Qdrant 服务地址，如 "localhost"
        port (int):           Qdrant HTTP 端口，默认 6333
        embedding_size (int): 向量维度，即每个向量由多少个数字组成。
                              这里为 1024，与 BAAI/bge-large-zh-v1.5 模型输出的维度一致
    """
    host: str             # Qdrant 服务地址
    port: int             # HTTP 端口（默认 6333）
    embedding_size: int   # 向量维度（必须与 Embedding 模型输出维度一致）


# =============================================================================
# 四、Embedding（文本向量化）服务配置
# =============================================================================
# 对应 app_config.yaml 中 embedding 段

@dataclass
class EmbeddingConfig:
    """
    Embedding 推理服务配置

    "Embedding" 就是把文字转换成向量（一串有数学意义的数字）的过程。
    比如 "销售额" 这个词，经过 Embedding 后会变成一个 1024 维的向量。
    这个向量可以用于 Qdrant 中的语义搜索。

    本项目的 Embedding 服务由 TEI（Text Embedding Inference）提供，
    它是一个专门做文本向量化的推理引擎。

    Attributes:
        host (str):  Embedding 服务地址，如 "localhost"
        port (int):  Embedding 服务端口，默认 8081
        model (str): 使用的 Embedding 模型名称，
                     如 "BAAI/bge-large-zh-v1.5"（中文语义向量的 SOTA 模型）
    """
    host: str     # Embedding 服务地址
    port: int     # Embedding 服务端口
    model: str    # 使用的模型名称（HuggingFace 格式）


# =============================================================================
# 五、Elasticsearch 搜索引擎配置
# =============================================================================
# 对应 app_config.yaml 中 es 段

@dataclass
class ESConfig:
    """
    Elasticsearch 全文搜索引擎配置

    Elasticsearch（简称 ES）是一个强大的全文搜索引擎。在本项目中，
    它用于对数据仓库中维度字段的"取值"建立倒排索引，实现关键词级别的精确匹配。
    
    比如用户问"华北地区的销售额"，ES 可以在索引中找到 region = "华北" 对应的记录。

    Attributes:
        host (str):       ES 服务地址，如 "localhost"
        port (int):       ES HTTP 端口，默认 9200
        index_name (str): 索引名称。ES 中的"索引"类似于 MySQL 中的"数据库"，
                          本项目使用名为 "data_agent" 的索引存储维度取值
    """
    host: str         # ES 服务地址
    port: int         # ES 端口（默认 9200）
    index_name: str   # 索引名称（类似数据库名）


# =============================================================================
# 六、大语言模型（LLM）配置
# =============================================================================
# 对应 app_config.yaml 中 llm 段

@dataclass
class LLMConfig:
    """
    大语言模型配置

    这是整个系统"大脑"的配置。LLM（Large Language Model）负责：
    1. 理解用户用自然语言提出的问题
    2. 根据召回的元数据信息生成正确的 SQL 语句

    本项目支持任何兼容 OpenAI API 格式的大模型服务，只需修改 base_url 和 api_key。

    Attributes:
        model_name (str): 模型名称，如 "gpt-5.2-codex"（擅长代码和 SQL 生成）
        api_key (str):    API 密钥，用于身份认证。类似于"门禁卡"，
                          没有它就无法调用模型服务
        base_url (str):   API 服务的地址，可以是 OpenAI 官方地址，
                          也可以是代理地址或私有部署地址
    """
    model_name: str   # 模型名称
    api_key: str      # API 密钥（认证用）
    base_url: str     # API 基础地址


# =============================================================================
# 七、应用总配置（聚合所有子配置）
# =============================================================================
# 对应 app_config.yaml 的整个文件

@dataclass
class AppConfig:
    """
    应用总配置类 — 所有子配置的"大管家"

    这个类把上面定义的所有配置组件（日志、数据库、Qdrant、Embedding、ES、LLM）
    组合成一个完整的配置对象。

    可以把它理解为一个"总开关面板"，大管家的各个属性分别指向不同的子面板。
    项目代码中只需 import app_config，然后通过 app_config.db_meta、app_config.llm
    等方式访问任意配置项，不用到处传参数。

    Attributes:
        logging (LoggingConfig):     日志配置
        db_meta (DBConfig):          元数据库连接配置
        db_dw (DBConfig):            数据仓库连接配置
        qdrant (QdrantConfig):       Qdrant 向量数据库配置
        embedding (EmbeddingConfig): Embedding 推理服务配置
        es (ESConfig):               Elasticsearch 搜索引擎配置
        llm (LLMConfig):             大语言模型配置
    """
    logging: LoggingConfig        # 日志配置
    db_meta: DBConfig             # 元数据库配置
    db_dw: DBConfig               # 数据仓库配置
    qdrant: QdrantConfig          # Qdrant 向量数据库配置
    embedding: EmbeddingConfig    # Embedding 服务配置
    es: ESConfig                  # Elasticsearch 配置
    llm: LLMConfig                # 大语言模型配置


# =============================================================================
# 八、配置加载 — 把 YAML 文件转换成 Python 对象
# =============================================================================

# 第 1 步：定位 YAML 配置文件路径
# __file__ 是本文件的路径（即 app/conf/app_config.py）
# .parents[2] 向上两级目录：app/conf/ → app/ → data-agent/（项目根目录）
# / 'conf' / 'app_config.yaml' → 最终得到 data-agent/conf/app_config.yaml
config_file = Path(__file__).parents[2] / 'conf' / 'app_config.yaml'

# 第 2 步：读取 YAML 文件内容
# OmegaConf.load() 会把 YAML 文件解析成一个类似字典的结构（OmegaConf DictConfig）
# 此时 context 是一个"松散"的结构，没有做类型校验
context = OmegaConf.load(config_file)

# 第 3 步：根据 AppConfig dataclass 生成"模式"（Schema）
# OmegaConf.structured() 会根据 AppConfig 及其子类的定义，
# 生成一个带有类型信息的"模板"结构。这个模板定义了：
#   - 哪些字段是必须的
#   - 每个字段的类型（str / int / bool 等）
#   - 嵌套结构的层次关系
schema = OmegaConf.structured(AppConfig)

# 第 4 步：合并 schema 和 context，生成最终的配置对象
# OmegaConf.merge() 把 YAML 数据（context）和类型模板（schema）合并：
#   - YAML 中已有的值 → 保留，并做类型校验
#   - YAML 中缺失的值 → 使用 schema 中的默认值（如果有）
#   - 类型不匹配 → 报错，避免运行时才发现问题
# OmegaConf.to_object() 把合并后的结果转换成真正的 Python 对象（AppConfig 实例）
app_config: AppConfig = OmegaConf.to_object(OmegaConf.merge(schema, context))

# 现在 app_config 就是一个完整的、类型安全的配置对象了！
# 其他地方直接 import 使用即可：
#   from app.conf.app_config import app_config
#   print(app_config.db_meta.host)    # → "localhost"
#   print(app_config.llm.model_name)  # → "gpt-5.2-codex"
