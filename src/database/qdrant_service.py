from qdrant_client import QdrantClient
from qdrant_client.async_qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, VectorParams, Filter, FieldCondition, MatchValue

class QdrantService:
    def __init__(self, host="localhost", port=6333):
        # Synchronous client for LangChain and sync operations
        self.sync_client = QdrantClient(host=host, port=port)
        self.client = AsyncQdrantClient(host=host, port=port)

    async def collection_exists(self, collection_name):
        try:
            exists = await self.client.collection_exists(collection_name=collection_name)
            return exists
        except Exception:
            return False

    async def create_collection(self, collection_name):
        await self.client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(
                size=self.client.get_embedding_size("sentence-transformers/all-MiniLM-L6-v2"),
                distance=Distance.COSINE
            )
        )

    async def upsert_points(self, collection_name, points):
        await self.client.upsert(
            collection_name=collection_name,
            points=points
        )

    async def search(self, document_collection, query_vector, ait_id, limit=5):
        exp_filter = Filter(
            must=[
                FieldCondition(
                    key="metadata.type",
                    match=MatchValue(value=document_collection)
                )
            ]
        )
        return await self.client.search(
            collection_name=ait_id,
            query_vector=query_vector,
            limit=limit,
            query_filter=exp_filter
        )
    
    async def delete_by_source_id(self, collection_name, source_id):
        """
        Asynchronously delete all points in the collection with the given source_id in payload.
        """
        filter_ = Filter(
            must=[
                FieldCondition(
                    key="metadata.source_id",
                    match=MatchValue(value=source_id)
                )
            ]
        )
        return await self.client.delete(
            collection_name=collection_name,
            points_selector=filter_
        )


