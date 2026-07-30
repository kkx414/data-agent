"""
Qdrant 客户端管理器
====================

这个文件负责管理与 Qdrant（一种向量数据库）的连接。

打个比方：Qdrant 就像一个"语义图书馆"，里面存的不是传统的文字，
而是把文字转换成的数学向量（一串数字）。比如 "苹果手机" 和 "iPhone"
虽然字面上不同，但它们的向量在数学空间中非常接近，Qdrant 就能把它们
关联起来。

这个管理器的作用是：
1. 创建与 Qdrant 的连接（类似打电话拨号）
2. 提供统一的连接入口给项目其他部分使用
3. 用完后关闭连接（类似挂电话）

当你运行本文件作为脚本时（python qdrant_client_manager.py），
它会执行一个简单的测试：创建集合、插入数据、查询数据，验证连接是否正常。
"""
import asyncio

# =============================================================================
# 导入依赖
# =============================================================================


from qdrant_client import QdrantClient, AsyncQdrantClient
from qdrant_client.models import Distance, VectorParams
from app.conf.app_config import QdrantConfig, app_config
from qdrant_client.models import PointStruct


# =============================================================================
# 客户端管理器类
# =============================================================================

class QdrantClientManager:
    """
    Qdrant 客户端管理器

    封装了 Qdrant 客户端从创建到销毁的完整生命周期。
    你可以把它理解为一个"遥控器"——拿着它就能操作远端的 Qdrant 服务。

    Attributes（属性）:
        client: Qdrant 客户端实例，所有操作都通过它完成。初始为 None，
                调用 init() 后才会被赋值。
        config: 从配置文件加载的 Qdrant 连接参数（主机地址、端口等）。
    """

    def __init__(self, config: QdrantConfig):
        """
        初始化管理器，但此时还不会真正连接 Qdrant。

        Args:
            config: Qdrant 的配置对象，包含 host（主机地址）、
                    port（端口号）等信息，来自 app_config.yaml。

        Note:
            这里只是"准备好遥控器"，还没有"按下开机键"。
            真正的连接在调用 init() 时才会建立。
        """
        # 客户端实例，初始为 None，等 init() 调用后才真正创建
        # QdrantClient | None 是类型注解，表示该变量可以是 QdrantClient 或 None
        self.client: AsyncQdrantClient | None = None

        # 保存配置，后续 get_url() 需要从这里读取 host 和 port
        self.config: QdrantConfig = config

    def get_url(self):
        """
        根据配置拼接 Qdrant 服务的完整访问地址。

        Returns:
            str: 形如 "http://localhost:6333" 的完整 URL。

        Example:
            如果 host="localhost", port=6333，返回 "http://localhost:6333"
        """
        # 使用 f-string 拼接 URL：从配置中取 host（主机名）和 port（端口号）
        return f"http://{self.config.host}:{self.config.port}"

    def init(self):
        """
        建立与 Qdrant 服务的连接。

        这是真正"拨通电话"的时刻。调用此方法后，self.client 就不再是 None，
        而是一个可以执行增删改查操作的 Qdrant 客户端实例。

        Warning:
            调用此方法前，必须确保 Qdrant 服务已经在 Docker 中启动
            （执行 docker compose up -d），否则会报"连接被拒绝"错误。
        """
        # 使用配置中的 URL 创建 QdrantClient 实例
        # QdrantClient 内部会尝试连接指定的地址
        self.client = AsyncQdrantClient(url=self.get_url())

    async def close(self):
        """
        关闭与 Qdrant 服务的连接，释放资源。

        类似于"挂断电话"。在程序结束或不再需要查询 Qdrant 时调用，
        避免占用连接资源。
        """
        # 调用客户端自身的 close() 方法断开连接
        await self.client.close()


# =============================================================================
# 模块级单例
# =============================================================================

# 创建一个全局唯一的 QdrantClientManager 实例（单例模式）。
# 整个项目中所有需要操作 Qdrant 的地方都共用这一个实例，
# 避免重复创建连接造成资源浪费。
#
# app_config.qdrant 是从 conf/app_config.yaml 加载的 Qdrant 配置，
# 包含 host、port、embedding_size 等信息。
qdrant_client_manager = QdrantClientManager(app_config.qdrant)


# =============================================================================
# 脚本入口（仅当直接运行本文件时执行）
# =============================================================================

# __name__ 是 Python 的内置变量：
#   当本文件被直接运行（python qdrant_client_manager.py）时，__name__ == "__main__"
#   当本文件被 import 导入时，__name__ == "qdrant_client_manager"
# 下面的代码只在直接运行时执行，被导入时不会执行。
if __name__ == '__main__':
    # ---- 第 1 步：初始化连接 ----
    # 调用 init() 建立与 Qdrant 服务的连接
    qdrant_client_manager.init()

    # 获取已创建好的客户端实例，方便后续调用
    client = qdrant_client_manager.client

    # ---- 第 2 步：创建集合（Collection） ----
    # 集合类似于关系数据库中的"表"，是存放向量数据的容器。
    # 每个集合需要定义向量的维度（size）和距离计算方式（distance）。
    #   size=4：每个向量由 4 个数字组成（这里仅为测试，实际项目中是 1024 维）
    #   Distance.DOT：使用"点积"来衡量两个向量的相似度
    async def test():

        await client.create_collection(
            collection_name='test_collection_async',       # 集合名称，类似表名
            vectors_config=VectorParams(
                size=4,                              # 向量维度：这里用 4 维方便展示
                distance=Distance.DOT                # 距离度量方式：Dot Product（点积）
            ),
        )

        # ---- 第 3 步：插入数据（Upsert） ----
        # upsert = update + insert，如果数据已存在就更新，不存在就插入（幂等操作）。
        # 每条数据是一个 PointStruct，包含三个部分：
        #   id：唯一编号
        #   vector：向量值（必须和创建集合时定义的维度一致）
        #   payload：附带的有效载荷，可以存储任意额外信息
        operation_info = await client.upsert(
            collection_name="test_collection_async",       # 要插入哪个集合
            wait=True,                               # 等待写入完成后再继续
            points=[
                PointStruct(
                    id=1,                            # 数据点编号
                    vector=[0.05, 0.61, 0.76, 0.74], # 4 维向量
                    payload={"city": "Berlin"}        # 附加信息：所属城市
                ),
                PointStruct(
                    id=2,
                    vector=[0.19, 0.81, 0.75, 0.11],
                    payload={"city": "London"}
                ),
                PointStruct(
                    id=3,
                    vector=[0.36, 0.55, 0.47, 0.94],
                    payload={"city": "Moscow"}
                ),
                PointStruct(
                    id=4,
                    vector=[0.18, 0.01, 0.85, 0.80],
                    payload={"city": "New York"}
                ),
                PointStruct(
                    id=5,
                    vector=[0.24, 0.18, 0.22, 0.44],
                    payload={"city": "Beijing"}
                ),
                PointStruct(
                    id=6,
                    vector=[0.35, 0.08, 0.11, 0.44],
                    payload={"city": "Mumbai"}
                ),
            ],
        )

        # ---- 第 4 步：查询数据（向量相似度搜索） ----
        # 给定一个查询向量 [0.2, 0.1, 0.9, 0.7]，Qdrant 会在集合中
        # 找出与它"最相似"的 top-3 条数据。这就像"以图搜图"，只是换成了"以向量搜向量"。
        #   query：要搜索的目标向量
        #   with_payload=False：不返回 payload，只返回匹配结果的基本信息
        #   limit=3：最多返回 3 条最相似的结果
        search_result = await client.query_points(
            collection_name="test_collection_async",       # 在哪个集合中搜索
            query=[0.2, 0.1, 0.9, 0.7],             # 查询向量（4 维）
            with_payload=False,                      # 不需要返回附加信息
            limit=3                                  # 只返回前 3 个最相似的结果
        ) # .points 取出搜索结果中的"节点列表"
        print(search_result.points)

        await qdrant_client_manager.close()

        # 打印查询结果
    asyncio.run(test())
