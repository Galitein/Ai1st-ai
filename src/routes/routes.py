import os
import json
import logging

from typing import Literal, List, Optional
from dotenv import load_dotenv
from fastapi import (
    APIRouter, 
    HTTPException, 
    Request, 
    UploadFile, 
    File, 
    Form,
    Body
)

load_dotenv()

from src.app.services.google_service import (
    google_oauth, 
    drive_upload,
    file_list, 
    folder_list, 
    drive_download
)
from src.app.services.text_processing import (
    vector_search,
    delete_embeddings
)

from src.app.services.text_generation import (
    generate_prompt,
    generate_response
)

from src.app.models.input_models import (
    FileNamesInput,
    QueryInput,
    TaskOrPromptInput,
    ChatInput
)

from src.app.utils.process_ait_files import create_ait_main, create_embeddings_main

router = APIRouter()

CREDENTIALS_PATH = os.getenv("CREDENTIALS_PATH", "credentials.json")

@router.get("/")
async def root():
    return {"message": "Welcome to the Uvicorn App"}

@router.post("/authenticate")
async def authenticate(request: Request):
    credentials = await google_oauth.authenticate(request)  # likely async
    if not credentials.get("status"):
        raise HTTPException(status_code=400, detail=credentials.get("message"))
    return credentials

@router.post("/upload")
# async def upload_file(input_data: FileNamesInput):
async def upload_file(
    files: list[UploadFile] = File(...),
    # destination: str = Form("google")
    ):
    """
    Uploads files to Google Drive.
    """
    file_paths = []
    for upload in files:
        # file_content = await upload.read()
        temp_path = f"/tmp/{upload.filename}"
        with open(temp_path, "wb") as f:
            file_content = await upload.read()
            logging.info(f"Writing to temporary file: {temp_path}")
            logging.info(f"File name: {upload.filename}")
            # logging.info(f"File content: {file_content}")  # Uncomment to see content
            f.write(file_content)
        file_paths.append(temp_path)
    uploaded_files = await drive_upload.upload_files(file_paths)  # should be async
    # uploaded_files = await drive_upload.upload_files(input_data.file_names)  # should be async
    return {"uploaded_files": uploaded_files}

@router.get("/list_folders")
async def list_folders_in_drive():
    """
    Lists files in a specified Google Drive folder.
    """
    response = await folder_list.list_folders_in_drive()  # should be async
    if not response.get("status"):
        raise HTTPException(status_code=400, detail="Failed to list files")
    return response

@router.get("/list_files")
async def list_files_in_drive(folder_id: str):
    """
    Lists files in a specified Google Drive folder.
    """
    logging.info(f"Listing files in folder ID: {folder_id}")
    response = await file_list.list_files_in_folder(folder_id)  # should be async
    if not response.get("status"):
        raise HTTPException(status_code=400, detail="Failed to list files")
    return response

@router.post("/download")
async def download_files(input_data: FileNamesInput):
    """
    Downloads specified files from Google Drive.
    """
    downloaded_files = await drive_download.download_files(input_data.file_names)  # should be async
    if not downloaded_files.get("status"):
        raise HTTPException(status_code=400, detail="Failed to download files")
    return downloaded_files

@router.get("/refresh_token")
async def refresh_token():
    """
    Refreshes the Google OAuth token.
    """
    try:
        # Reading from disk is blocking; consider using aiofiles for true async
        with open(CREDENTIALS_PATH, "r") as f:
            credentials_json = json.load(f)
        return credentials_json
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not read credentials: {str(e)}")

@router.post("/create_ait")
async def create_ait(
    user_id: int = Form(None),
    ait_name: str = Form("Undefined"),
    files: Optional[list[UploadFile]] = File(None),
    file_names: Optional[List[str]] = Form(None),
    task_or_prompt: str = Form(...),
    destination: Literal["google", "local"] = Form("google")
):

    if file_names and len(file_names) == 1:
        file_names = [f.strip() for f in file_names[0].split(',')]

    response = await create_ait_main(user_id,
    ait_name,
    files,
    file_names,
    task_or_prompt,
    destination)

    return response

@router.post("/create_embeddings")
async def build_index_route(
    files: Optional[list[UploadFile]] = File(None),
    file_names: Optional[List[str]] = Form(None),
    task_or_prompt: Optional[str] = Form(None),
    destination: Literal["google", "local", "trello"] = Form("google"),
    document_collection: Literal["bib", "log_diary", "log_trello"] = Form("bib"),
    ait_id: str = Form(...),
    ):
    
    if file_names and len(file_names) == 1:
        file_names = [f.strip() for f in file_names[0].split(',')]

    response = await create_embeddings_main(files,
    file_names,
    task_or_prompt,
    destination,
    document_collection,
    ait_id)
    return response
    

@router.post("/search")
async def search_route(input_data: QueryInput):
    """
    Searches the index for the given query and returns ranked results.
    """
    response = await vector_search.search(
        ait_id=input_data.ait_id, 
        query=input_data.query, 
        document_collection=input_data.document_collection, 
        limit=input_data.limit, 
        similarity_threshold=input_data.similarity_threshold
    )  
    if not response.get('status'):
        raise HTTPException(status_code=400, detail="No results found.")

    return response

@router.post("/desc_sys_prompt")
async def prompt_generator(input_data: TaskOrPromptInput):
    """
    Generates a system prompt based on the provided task or existing prompt.
    """
    response = await generate_prompt.generate_system_prompt(input_data.ait_id, input_data.task_or_prompt)  # should be async
    
    if response.get('status') == 'failed':
        raise HTTPException(status_code=400, detail=response.get('message'))
    
    return response

@router.post("/delete_embeddings")
async def delete_index(input_data: FileNamesInput):
    """
    Deletes all vectors and records for a specific file (all chunks) in Qdrant and SQLRecordManager.
    """
    try:
        delete_response = await delete_embeddings.delete_file_index(
            input_data.ait_id, 
            input_data.file_names,
            input_data.document_collection
        )
        if not delete_response.get("status"):
            raise HTTPException(status_code=400, detail=delete_response.get("message"))
        return delete_response
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting index and records: {str(e)}")

@router.post("/chat")
async def generate_query_response(input_data: ChatInput):
    """
    Generates a response based on the user's query using the system prompt.
    """
    response = await generate_response.generate_chat_completion(
        input_data.ait_id, 
        input_data.query
    )

    if not response.get('status'):
        raise HTTPException(status_code=400, detail=response.get('message'))
    
    return response