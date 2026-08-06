from qdrant_client import AsyncQdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct

from app.conf.app_config import app_config
from app.entities.metric_info import MetricInfo


class MetricQdrantRepository:
    collection_name = "metric_info_collection"

    def __init__(self, client: AsyncQdrantClient):
        self.client = client

    async def ensure_collection(self, columns: dict):
        if not await self.client.collection_exists(self.collection_name):
            await self.client.create_collection(
                collection_name="collection_name",
                vectors_config=VectorParams(size=app_config.qdrant.embedding_size, distance=Distance.COSINE)
            )

    async def upset(self, ids: list[str], embeddings: list[list[float]], payloads: list[str], batch_size: int=10):
       points:list[PointStruct] = [PointStruct(id=id,vector=embedding,payload=payload) for id,embedding,payload in
                                   zip(ids, embeddings, payloads)]
       for i in range(0, len(points), batch_size):
           await self.client.upsert(collection_name=self.collection_name,points=points[i:i + batch_size])

    async def search(self, embedding, score_threshold: float = 0.6, limit: int = 20):
        result = await self.client.query_points(
            collection_name=self.collection_name,  # 在哪个集合中搜索
            query=embedding,  # 查询向量（4 维）
            limit=limit,  # 只返回前 3 个最相似的结果
            score_threshold=score_threshold
        )

        return [MetricInfo(**point.payload) for point in result.points]