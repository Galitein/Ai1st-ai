import os
import logging
from dotenv import load_dotenv

import torch
import asyncio

from txtai import Embeddings
from txtai.pipeline import Similarity

load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("vector_search.log"),  # Updated log file name
        logging.StreamHandler()
    ]
)

# Configuration
MODEL_NAME = os.getenv("MODEL_NAME")
INDEX_DIR = os.getenv("INDEX_DIR")
SIMILARITY_MODEL = os.getenv("SIMILARITY_MODEL")

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
logging.info(f"Using device: {device}")
similarity = Similarity(SIMILARITY_MODEL)

from src.database.qdrant_service import QdrantService
from langchain_community.embeddings import SentenceTransformerEmbeddings

QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))

async def search(ait_id, query, qdrant_collection, limit=10, similarity_threshold=0.3):
    embedding = SentenceTransformerEmbeddings(model_name=MODEL_NAME)
    query_vector = embedding.embed_query(query)
    qdrant_client = QdrantService(host=QDRANT_HOST, port=QDRANT_PORT)

    # Await the async search method
    search_result = await qdrant_client.search(
        collection_name=qdrant_collection,
        query_vector=query_vector,
        ait_id=ait_id,
        limit=limit,
    )
    filtered_results = []
    for hit in search_result:
        if hit.score >=similarity_threshold:
            filtered_results.append({
                "page_content": hit.payload.get("page_content", ''),
                "file_name": hit.payload.get("metadata", {}).get("file_name", ""),
            })
    print(f"Filtered results: {filtered_results}")
    return {"status": True, "results": filtered_results}
