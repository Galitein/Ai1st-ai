import os
import logging
import httpx
from dotenv import load_dotenv
from datetime import datetime

from src.database.sql import AsyncMySQLDatabase
from src.app.services.text_processing import url_file_loader

load_dotenv(override=True)

DB_HOST = os.getenv("DB_HOST")
DB_PORT = int(os.getenv("DB_PORT"))
DB_USER = os.getenv("DB_USER") 
DB_PASS = os.getenv("DB_PASS") 
DB_NAME = os.getenv("DB_NAME")
BACKEND_API_URL = os.getenv("BACKEND_API_URL")

db = AsyncMySQLDatabase(
    host=DB_HOST,
    port=DB_PORT,
    user=DB_USER,
    password=DB_PASS,
    database=DB_NAME
)

async def create_embedding_urls(ait_id:str, file_urls:str, document_collection:list) -> dict:
    try:
        await db.create_pool()
    except Exception as e:
        logging.error(f"Database connection failed: {str(e)}")
        return {"status": False, "message": f"Database connection failed: {str(e)}"}
    file_names_list = []
    try:
        for file_url in file_urls:
            if not file_url.strip():
                logging.error("File URL cannot be empty")
                return {"status": False, "message": "File URL cannot be empty"}

            # TODO: Implement the extraction function "extract_documents_from_url(file_url)" as needed
            documents = await url_file_loader.load_url_documents(file_url, document_collection)
            # documents = []
            file_name = file_url.split("/")[-1]  # Simple extraction from URL

            index_response = None
            try:
                async with httpx.AsyncClient() as client:
                    create_embedding_response = await client.post(
                        f"{BACKEND_API_URL}/create_embeddings",
                        json={
                            "ait_id": ait_id,
                            "documents": documents,
                        }
                    )
                    if create_embedding_response.status_code == 200:
                        trello_data = create_embedding_response.json()
                        logging.info(f"Indexed results: {trello_data.get('index_result')} for ait_id: {ait_id}")
                        index_response = {
                            "status": True,
                            "message": "Documents indexed successfully.",
                            "index_result": trello_data.get("index_result")
                        }
                    else:
                        logging.warning(f"Indexing failed: {create_embedding_response.text}")
                        index_response = {
                            "status": False,
                            "message": f"Indexing failed: {create_embedding_response.text}",
                            "index_result": None
                        }
            except Exception as e:
                logging.error(f"Exception during indexing: {e}")
                index_response = {
                    "status": False,
                    "message": f"Exception during indexing: {str(e)}",
                    "index_result": None
                }

            if not index_response or not index_response.get("status"):
                logging.error(f"Indexing failed for {file_url}: {index_response.get('message') if index_response else 'Unknown error'}")
                return {"status": False, "message": index_response.get("message") if index_response else "Unknown error"}
            
            current_time = datetime.utcnow()
            file_record = {
                'custom_gpt_id': ait_id,
                'file_name': file_name,
                'file_type': document_collection,
                'created_at': current_time,
                'updated_at': current_time
            }
        
            db_response = await db.insert('custom_gpt_files', file_record)
            if not db_response:
                logging.error(f"Failed to insert file records for custom_gpt_id: {ait_id}")
                return {"status": False, "message": "Failed to insert file records into database"}

            file_names_list.append(file_name)
            logging.info(f"Successfully indexed and inserted {file_name} file records for custom_gpt_id: {ait_id}")
        logging.info(f"Files {file_names_list} processed and indexed for AIT ID: {ait_id}")
        return {
            "status": True,
            "ait_id": ait_id,
            "files_inserted": file_names_list,
            "document_collection": document_collection
        }

    except Exception as e:
        logging.error(f"Unexpected error in create_embeddings_urls: {str(e)}")
        return {"status": False, "message": str(e)}
    finally:
        await db.close_pool()
