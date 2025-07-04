import os
import json
import uuid
import shutil
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
# from pydantic import BaseModel
# from typing import List
# from fastapi.responses import RedirectResponse, JSONResponse
from urllib.parse import urlencode

load_dotenv()

from src.app.services.google_service import (
    google_oauth, 
    drive_upload,
    file_list, 
    folder_list, 
    drive_download
)
from src.app.services.text_processing import (
    create_embeddings, 
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
    FileListOutput,
    CreateAitInput,
    ChatInput
)

from src.database.mongo import MongoDBClient

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
            print(f"Writing to temporary file: {temp_path}")
            print(f"File name: {upload.filename}")
            # print(f"File content: {file_content}")  # Uncomment to see content
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
    print(f"Listing files in folder ID: {folder_id}")
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
    files: Optional[list[UploadFile]] = File(None),
    file_names: Optional[List[str]] = Form(None),
    task_or_prompt: str = Form(...),
    destination: Literal["google", "local"] = Form("google")
):
    ait_id = str(uuid.uuid4())
    file_names_list = []
    
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
        
        # Handle both string and list inputs for file_names
        if isinstance(file_names, str):
            file_names_list = [name.strip() for name in file_names.split(",") if name.strip()]
        else:
            file_names_list = [name for name in file_names if name.strip()]
        
        if not file_names_list:
            raise HTTPException(status_code=400, detail="At least one valid file name must be provided")
        
        print(f"Parsed file names: {file_names_list}")
    
    # Rest of your code remains the same...
    # Build index with UUID and file names
    index_response = await create_embeddings.process_and_build_index(
        ait_id=ait_id,
        file_names=file_names_list,
        document_collection='bib',
        destination=destination
    )
    
    if not index_response.get("status"):
        raise HTTPException(status_code=400, detail=index_response.get("message"))
    
    # Generate prompt with UUID and task_or_prompt
    prompt_response = await generate_prompt.generate_system_prompt(ait_id, task_or_prompt)
    if prompt_response.get('status') == 'failed':
        raise HTTPException(status_code=400, detail=prompt_response.get('message'))
    
    insert_document = {
        "status": True,
        "ait_id": ait_id,
        "ait_description": str(task_or_prompt),
        "bib_file_names": file_names_list,
        "prompt_response": prompt_response.get('prompt')
    }
    
    client = MongoDBClient()
    doc_response = await client.insert(collection_name="ait", doc=insert_document)
    print(f"Document inserted with ID: {doc_response.get('inserted_id')}")
    
    if doc_response.get("status"):
        temp_folder_path = os.path.join("temp", ait_id)
        if os.path.exists(temp_folder_path):
            try:
                shutil.rmtree(temp_folder_path)
                logging.info(f"Cleaned up temp folder: {temp_folder_path}")
            except Exception as e:
                logging.error(f"Error cleaning up temp folder: {e}")
        return {"status": True, "ait_id": ait_id}
    else:
        raise HTTPException(status_code=500, detail="Failed to insert document into MongoDB")

@router.post("/create_embeddings")
async def build_index_route(
    files: Optional[list[UploadFile]] = File(None),
    file_names: Optional[List[str]] = Form(None),
    task_or_prompt: str = Form(...),
    destination: Literal["google", "local"] = Form("google"),
    document_collection: Literal["bib", "log"] = Form("bib"),
    ait_id: str = Form(...),
    ):
    """
    Builds an index from the given list of file names.pip install "langchain<0.1.0" "pydantic<2.0"
    """
    # Build index with UUID and file names
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
        
        # Handle both string and list inputs for file_names
        if isinstance(file_names, str):
            file_names_list = [name.strip() for name in file_names.split(",") if name.strip()]
        else:
            file_names_list = [name for name in file_names if name.strip()]
        
        if not file_names_list:
            raise HTTPException(status_code=400, detail="At least one valid file name must be provided")
        
    index_response = await create_embeddings.process_and_build_index(
        ait_id=ait_id,
        file_names=file_names_list,
        document_collection='bib',
        destination=destination
    )

    if not index_response.get("status"):
        raise HTTPException(status_code=400, detail=index_response.get("message"))

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
    response = await generate_prompt.generate_system_prompt(input_data.task_or_prompt)  # should be async
    
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

    if response.get('status') == 'error':
        raise HTTPException(status_code=400, detail=response.get('message'))
    
    return response