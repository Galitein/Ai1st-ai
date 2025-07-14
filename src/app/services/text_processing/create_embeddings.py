import os
import logging
from dotenv import load_dotenv
import nltk

nltk.download('punkt')

from langchain_community.embeddings import SentenceTransformerEmbeddings
from langchain_qdrant import QdrantVectorStore
from langchain.indexes import index

from src.database.sql_record_manager import sql_record_manager
from src.database.qdrant_service import QdrantService

load_dotenv()

MODEL_NAME = os.getenv("MODEL_NAME", "text-embedding-ada-002")
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("google_oauth.log"),
        logging.StreamHandler()
    ]
)

def process_and_build_index(ait_id, documents):
    """
    Incrementally indexes files using Qdrant and tracks file states using SQLRecordManager.

    Args:
        ait_id (str): Unique identifier for the AIT and Qdrant collection name.
        documents (list): List of documents to process.

    Returns:
        dict: Status and result of the indexing process.
    """
    try:
        embedding = SentenceTransformerEmbeddings(model_name=MODEL_NAME)

        qdrant_client = QdrantService(host=QDRANT_HOST, port=QDRANT_PORT)
        if not qdrant_client.sync_client.collection_exists(collection_name=ait_id):
            qdrant_client.sync_client.create_collection(
                collection_name=ait_id
            )
        vectorstore = QdrantVectorStore(
            client=qdrant_client.sync_client,
            collection_name=ait_id,
            embedding=embedding,
        )
        
        # Set up SQLRecordManager for tracking
        namespace = f"qdrant/{ait_id}"
        record_manager = sql_record_manager(namespace=namespace)
        
        # Incremental indexing using LangChain's index function
        result = index(
            documents,
            record_manager,
            vectorstore,
            cleanup="scoped_full",  # or "full" for full sync
            source_id_key="source_id",  # Use a unique identifier for each document
        )
        logging.info(f"Indexing result: {result}")
        return {
            "status": True,
            "message": "Qdrant index updated.",
            "index_result": result
        }
    except Exception as e:
        logging.error(f"Error in process_and_build_index: {str(e)}")
        return {
            "status": False,
            "message": f"Failed to update Qdrant index: {str(e)}"
        }
