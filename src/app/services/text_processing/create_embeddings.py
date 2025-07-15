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
from src.app.services.google_service.drive_file_loader import load_google_documents
from src.app.services.text_processing.local_file_loader import load_local_documents
from src.app.services.trello_service.trello_file_loader import load_trello_documents
from src.app.services.ms_exchange.mse_doc_processing import load_email_documents

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

async def process_and_build_index(ait_id, file_names, document_collection, destination, messages=None):
    """
    Incrementally indexes files using Qdrant and tracks file states using SQLRecordManager.

    Args:
        ait_id (str): Unique identifier for the AIT and Qdrant collection name.
        file_names (list): List of file names to process.
        document_collection (str): Qdrant sub_collection name.

    Returns:
        dict: Status and result of the indexing process.
    """
    # 1. Load and chunk documents from local files or Google Drive
    if destination == "google":
        try:
            document_response = await load_google_documents(
                file_names=file_names, 
                ait_id=ait_id, 
                document_collection=document_collection,
                logger=logging,
            )
            # Check for status in the returned document_response
            if not document_response.get("status"):
                logging.error(document_response.get("error") or document_response.get("message", "Unknown error"))
                return {
                    "status": False,
                    "message": document_response.get("error") or document_response.get("message", "Failed to load documents."),
                    "index_result": None
                }
            documents = document_response.get("documents", [])
            logging.info(f"Loaded {len(documents)} documents for indexing.")
        except FileNotFoundError as e:
            logging.error(str(e))
            return {
                "status": False,
                "message": str(e),
                "index_result": None
            }
        except Exception as e:
            logging.error(f"Unexpected error: {e}")
            return {
                "status": False,
                "message": f"Unexpected error: {e}",
                "index_result": None
            }
    elif destination == "local":
        try:
            document_response = await load_local_documents(
                file_names=file_names, 
                ait_id=ait_id, 
                document_collection=document_collection,
                logger=logging,
            )
            # Check for status in the returned document_response
            if not document_response.get("status"):
                logging.error(document_response.get("error") or document_response.get("message", "Unknown error"))
                return {
                    "status": False,
                    "message": document_response.get("error") or document_response.get("message", "Failed to load documents."),
                    "index_result": None
                }
            documents = document_response.get("documents", [])
            logging.info(f"Loaded {len(documents)} documents for indexing.")
        except Exception as e:
            logging.error(f"Unexpected error: {e}")
            return {
                "status": False,
                "message": f"Unexpected error: {e}",
                "index_result": None
            }
    elif destination == "trello":
        try:
            document_response = await load_trello_documents(
                ait_id=ait_id
            )
            # Check for status in the returned document_response
            if not document_response.get("status"):
                logging.error(document_response.get("error") or document_response.get("message", "Unknown error"))
                return {
                    "status": False,
                    "message": document_response.get("error") or document_response.get("message", "Failed to load documents."),
                    "index_result": None
                }
            documents = document_response.get("documents", [])
            logging.info(f"Loaded {len(documents)} Trello documents for indexing.")
        except Exception as e:
            logging.error(f"Unexpected error: {e}")
            return {
                "status": False,
                "message": f"Unexpected error: {e}",
                "index_result": None
            }
    elif destination == "email" and messages:
        if not messages:
            logging.error("No email messages provided for email destination")
            return {
                "status": False,
                "message": "No email messages provided for email destination",
                "index_result": None
            }
        
        documents = await load_email_documents(
            messages=messages,
            ait_id=ait_id,
            document_collection=document_collection,
            logger=logging
        )
        logging.info(f"Loaded {len(documents)} email documents for indexing.")
    # 2. Create Embeddings of the chunks
    try:
        embedding = SentenceTransformerEmbeddings(model_name=MODEL_NAME)

        qdrant_client = QdrantService(host=QDRANT_HOST, port=QDRANT_PORT)
        if not await qdrant_client.collection_exists(collection_name=ait_id):
            await qdrant_client.create_collection(
                collection_name=ait_id
            )
        vectorstore = QdrantVectorStore(
            client=qdrant_client.sync_client,
            collection_name=ait_id,
            embedding=embedding,
        )
        
        # 4. Set up SQLRecordManager for tracking
        namespace = f"qdrant/{ait_id}"
        record_manager = sql_record_manager(namespace=namespace)
    except Exception as e:
        logging.error(f"Error during embedding or vectorstore setup: {e}")
        return {
            "status": False,
            "message": f"Error during embedding or vectorstore setup: {e}",
            "index_result": None
        }
    
    # 5. Incremental indexing using LangChain's index function
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
        "message": "Incremental Qdrant index updated.",
        "index_result": result
    }
