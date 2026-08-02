from typing import TypedDict

from langchain_huggingface import HuggingFaceEmbeddings

from app.repositories.qdrant.column_qdrant_repository import ColumnQdrantRepository


class DataAgentContext(TypedDict):
    column_qdrant_repository: ColumnQdrantRepository
    embedding_client: HuggingFaceEmbeddings