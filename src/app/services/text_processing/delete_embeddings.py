import re
import os
import logging
from src.database.qdrant_service import QdrantService
from src.database.sql_record_manager import sql_record_manager, delete_source_ids, get_all_source_ids
from langchain_qdrant import QdrantVectorStore

from dotenv import load_dotenv
from langchain_community.embeddings import SentenceTransformerEmbeddings
import csv
import sqlite3

load_dotenv()

MODEL_NAME = os.getenv("MODEL_NAME", "text-embedding-ada-002")
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
QDRANT_COLLECTION = os.getenv("QDRANT_BIB_COLLECTION", "bib")

async def delete_file_index(ait_id, file_names, qdrant_collection):
    """
    Deletes all vectors and records for specific files (all chunks) in Qdrant and SQLRecordManager.
    Args:
        ait_id (str): Unique identifier for the AIT.
        file_names (list): List of file names to delete.
        qdrant_collection (str): Qdrant collection name.
    """
    try:
        embedding = SentenceTransformerEmbeddings(model_name=MODEL_NAME)
        qdrant_client = QdrantService(host=QDRANT_HOST, port=QDRANT_PORT)
        namespace = f"qdrant/{ait_id}"
        record_manager = sql_record_manager(namespace=namespace)
        all_source_ids = get_all_source_ids(namespace)
        for file_name in file_names:
            prefix = f"{ait_id}_{file_name}_"
            file_source_ids = [sid for sid in all_source_ids if sid.startswith(prefix)]
            if not file_source_ids:
                logging.info(f"No index found for file: {file_name}")
                continue
            # Use qdrant_collection here if needed for deletion
            delete_source_ids(namespace, file_source_ids)
            logging.info(f"Deleted index and records for file: {file_name}")
        return {"status": True, "ait_id": ait_id, "file_names": file_names}
    except Exception as e:
        logging.error(f"Error deleting index and records for files {file_names}: {e}")
        return {"status": False, "message": str(e)}