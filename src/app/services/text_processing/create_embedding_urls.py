import os
import logging
from dotenv import load_dotenv
from datetime import datetime

from src.database.sql import AsyncMySQLDatabase
from src.app.services.text_processing import create_embeddings_main

load_dotenv(override=True)

DB_HOST = os.getenv("DB_HOST")
DB_PORT = int(os.getenv("DB_PORT"))
DB_USER = os.getenv("DB_USER") 
DB_PASS = os.getenv("DB_PASS") 
DB_NAME = os.getenv("DB_NAME") 

db = AsyncMySQLDatabase(
    host=DB_HOST,
    port=DB_PORT,
    user=DB_USER,
    password=DB_PASS,
    database=DB_NAME
)

async def create_embeddings_urls(ait_id:str, file_urls:str, document_collection:list) -> dict:
    try:
        await db.create_pool()
    except Exception as e:
        logging.error(f"Database connection failed: {str(e)}")
        return {"status":False, "message": f"Database connection failed: {str(e)}"}
    file_names_list = []
    try:
        for file_url in file_urls:
            if not file_url.strip():
                logging.error("File URL cannot be empty")
                return {"status": False, "message": "File URL cannot be empty"}

            # TODO: Implement the extraction function "extract_documents_from_url(file_url)" as needed
            # documents = await extract_documents_from_url(file_url)
            # file_name = extract_file_name_from_url(file_url)
            documents = []
            file_name = file_url.split("/")[-1]  # Simple extraction from URL
            index_response = await create_embeddings_main.process_and_build_index(
                ait_id=ait_id,
                documents=documents
            )

            if not index_response.get("status"):
                logging.error(f"Indexing failed for {file_url}: {index_response.get('message')}")
                return {"status": False, "message": index_response.get("message")}
            
            current_time = datetime.utcnow()

            file_record = {
            'custom_gpt_id': ait_id,
            'file_name': file_name,
            'file_type': document_collection,
            'created_at': current_time,
            'updated_at': current_time
            }
        
            # Batch insert all file records
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
        logging.error(f"Unexpected error in create_embeddings_main: {str(e)}")
        return {"status": False, "message": str(e)}
    finally:
        await db.close_pool()
