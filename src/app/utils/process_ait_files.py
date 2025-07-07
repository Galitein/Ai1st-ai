import os
import uuid
import shutil
import logging

from datetime import datetime
from src.database.sql import AsyncMySQLDatabase

from typing import Literal, List, Optional
from dotenv import load_dotenv
from fastapi import (
    HTTPException, 
)

from src.app.services.text_processing import (
    create_embeddings, 
)

from src.app.services.text_generation import (
    generate_prompt,
)

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

async def insert_custom_gpt_files(custom_gpt_id: str, file_names: List[str], file_type: str = "bib") -> bool:
    """
    Insert multiple file records into custom_gpt_files table
    
    Args:
        custom_gpt_id: UUID of the custom GPT (ait_id)
        file_names: List of file names to insert
        file_type: Type of file (bib, pre, log)
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        if not file_names:
            return True  # No files to insert, consider it successful
            
        # Prepare file records for batch insert
        file_records = []
        current_time = datetime.utcnow()
        
        for file_name in file_names:
            file_record = {
                'custom_gpt_id': custom_gpt_id,
                'file_name': file_name,
                'file_type': file_type,
                'created_at': current_time,
                'updated_at': current_time
            }
            file_records.append(file_record)
        
        # Batch insert all file records
        success = await db.insert_many('custom_gpt_files', file_records)
        
        if success:
            logging.info(f"Successfully inserted {len(file_records)} file records for custom_gpt_id: {custom_gpt_id}")
        else:
            logging.error(f"Failed to insert file records for custom_gpt_id: {custom_gpt_id}")
            
        return success
        
    except Exception as e:
        logging.error(f"Error inserting custom_gpt_files: {str(e)}")
        return False



async def delete_custom_gpt_files_by_gpt_id(custom_gpt_id: str) -> bool:
    """
    Delete all files for a specific custom GPT (rollback function)
    
    Args:
        custom_gpt_id: UUID of the custom GPT (ait_id)
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        success = await db.delete(
            table='custom_gpt_files',
            where='custom_gpt_id = %s',
            params=(custom_gpt_id,)
        )
        
        if success:
            logging.info(f"Successfully deleted all files for custom_gpt_id: {custom_gpt_id}")
        else:
            logging.warning(f"No files found to delete for custom_gpt_id: {custom_gpt_id}")
            
        return success
        
    except Exception as e:
        logging.error(f"Error deleting custom_gpt_files: {str(e)}")
        return False


async def create_ait_main(user_id,
    ait_name,
    files,
    file_names,
    task_or_prompt,
    pre_context,
    destination):
    
    ait_id = str(uuid.uuid4())
    file_names_list = []

    try:
        await db.create_pool()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database connection failed: {str(e)}")

    try:
        # Handle destination logic
        if destination == "local":
            if not files or len(files) == 0 or (len(files) == 1 and files[0].filename == ''):
                raise HTTPException(status_code=400, detail="Files must be provided for local uploads")
            save_dir = f"./temp/{ait_id}"
            os.makedirs(save_dir, exist_ok=True)
            local_file_paths = []
            for upload in files:
                if upload.filename:
                    file_path = os.path.join(save_dir, upload.filename)
                    file_content = await upload.read()
                    with open(file_path, "wb") as f:
                        f.write(file_content)
                    local_file_paths.append(upload.filename)
            file_names_list = local_file_paths

        elif destination == "google":
            if not file_names:
                raise HTTPException(status_code=400, detail="File names must be provided for Google Drive uploads")
            if isinstance(file_names, str):
                file_names_list = [name.strip() for name in file_names.split(",") if name.strip()]
            else:
                file_names_list = [name for name in file_names if name.strip()]
            if not file_names_list:
                raise HTTPException(status_code=400, detail="At least one valid file name must be provided")

        # Generate system prompt
        prompt_response = await generate_prompt.generate_system_prompt(ait_id, task_or_prompt)
        if prompt_response.get('status') == 'failed':
            raise HTTPException(status_code=400, detail=prompt_response.get('message'))

        # Insert into custom_gpts table FIRST
        custom_gpt_data = {
            "id": ait_id,
            "user_id": int(user_id),
            "name": ait_name,
            "sys": prompt_response.get("prompt", ""),
            "pre": pre_context,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }

        insert_gpt_status = await db.insert("custom_gpts", custom_gpt_data)
        if not insert_gpt_status:
            raise HTTPException(status_code=500, detail="Failed to insert record into custom_gpts table")

        # Then insert file records
        file_insert_success = await insert_custom_gpt_files(ait_id, file_names_list)
        if not file_insert_success:
            await db.delete("custom_gpts", "id = %s", (ait_id,))
            raise HTTPException(status_code=500, detail="Failed to insert file records into database")

        # Now build index
        index_response = await create_embeddings.process_and_build_index(
            ait_id=ait_id,
            file_names=file_names_list,
            document_collection='bib',
            destination=destination
        )
        if not index_response.get("status"):
            await delete_custom_gpt_files_by_gpt_id(ait_id)
            await db.delete("custom_gpts", "id = %s", (ait_id,))
            raise HTTPException(status_code=400, detail=index_response.get("message"))

        # Cleanup temp files
        temp_folder_path = os.path.join("temp", ait_id)
        if os.path.exists(temp_folder_path):
            try:
                shutil.rmtree(temp_folder_path)
                logging.info(f"Cleaned up temp folder: {temp_folder_path}")
            except Exception as e:
                logging.error(f"Error cleaning up temp folder: {e}")

        return {"status": True, "ait_id": ait_id}

    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Unexpected error in create_ait: {str(e)}")
        await delete_custom_gpt_files_by_gpt_id(ait_id)
        await db.delete("custom_gpts", "id = %s", (ait_id,))
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
    finally:
        await db.close_pool()


async def create_embeddings_main(files,
    file_names,
    task_or_prompt,
    destination,
    document_collection,
    ait_id):
    try:
        await db.create_pool()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database connection failed: {str(e)}")
    
    try:
        # Validate inputs based on destination
        if destination == "local":
            if not files or len(files) == 0 or (len(files) == 1 and files[0].filename == ''):
                raise HTTPException(status_code=400, detail="Files must be provided for local uploads")
            
            save_dir = f"./temp/{ait_id}"
            os.makedirs(save_dir, exist_ok=True)
            local_file_paths = []
            
            for upload in files:
                if upload.filename:  # Check if file actually exists
                    file_path = os.path.join(save_dir, upload.filename)
                    file_content = await upload.read()
                    with open(file_path, "wb") as f:
                        f.write(file_content)
                    local_file_paths.append(upload.filename)
            
            file_names_list = local_file_paths
            
        elif destination == "google":
            if not file_names:
                raise HTTPException(status_code=400, detail="File names must be provided for Google Drive uploads")
            
            if isinstance(file_names, str):
                file_names_list = [name.strip() for name in file_names.split(",") if name.strip()]
            else:
                file_names_list = [name for name in file_names if name.strip()]
            
            if not file_names_list:
                raise HTTPException(status_code=400, detail="At least one valid file name must be provided")
        
        elif destination == "trello":
            file_names_list = []
        
        file_insert_success = await insert_custom_gpt_files(ait_id, file_names_list, document_collection)
        
        if not file_insert_success:
            raise HTTPException(status_code=500, detail="Failed to insert file records into database")
            
        index_response = await create_embeddings.process_and_build_index(
            ait_id=ait_id,
            file_names=file_names_list,
            document_collection=document_collection,
            destination=destination
        )

        if not index_response.get("status"):
            await delete_custom_gpt_files_by_gpt_id(ait_id)
            raise HTTPException(status_code=400, detail=index_response.get("message"))
            
        return {"status": True, "ait_id": ait_id, "files_inserted": len(file_names_list)}
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Unexpected error in build_index_route: {str(e)}")
        await delete_custom_gpt_files_by_gpt_id(ait_id)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
    finally:
        await db.close_pool()

