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
from src.app.services.google_service.drive_file_loader import load_documents

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

async def process_and_build_index(ait_id, file_names, qdrant_collection):
    """
    Incrementally indexes files using Qdrant and tracks file states using SQLRecordManager.

    Args:
        ait_id (str): Unique identifier for the AIT.
        file_names (list): List of file names to process.
        qdrant_collection (str): Qdrant collection name.

    Returns:
        dict: Status and result of the indexing process.
    """
    # 1. Load and chunk documents
    documents = await load_documents(file_names, ait_id, logger=logging)
    logging.info(f"Loaded {len(documents)} documents for indexing.")

    # 2. Create Embeddings of the chunks
    embedding = SentenceTransformerEmbeddings(model_name=MODEL_NAME)

    qdrant_client = QdrantService(host=QDRANT_HOST, port=QDRANT_PORT)
    if not await qdrant_client.collection_exists(qdrant_collection):
        await qdrant_client.create_collection(
            collection_name=qdrant_collection
        )
    vectorstore = QdrantVectorStore(
        client=qdrant_client.sync_client,
        collection_name=qdrant_collection,
        embedding=embedding,
    )
    
    # 4. Set up SQLRecordManager for tracking
    namespace = f"qdrant/{ait_id}"
    record_manager = sql_record_manager(namespace=namespace)
    
    # 5. Incremental indexing using LangChain's index function
    result = index(
        documents,
        record_manager,
        vectorstore,
        cleanup="scoped_full",  # or "full" for full sync
        source_id_key="source_id",  # Use a unique identifier for each document
    )
    print(f"Indexing result: {result}")
    return {
        "status": True,
        "message": "Incremental Qdrant index updated.",
        "index_result": result
    }
