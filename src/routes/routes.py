from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List

from src.app.services.google_service import (
    google_oauth, 
    drive_upload, 
    file_list, 
    drive_download
)
from src.app.services.text_processing import (
    create_embeddings, 
    vector_search
)

from src.app.services.text_generation import (
    generate_prompt,
    generate_response
)

router = APIRouter()

# Input models
class FileNamesInput(BaseModel):
    file_names: List[str]

class QueryInput(BaseModel):
    query: str

class TaskOrPromptInput(BaseModel):
    task_or_prompt: str

@router.get("/")
async def root():
    return {"message": "Welcome to the Uvicorn App"}

@router.get("/authenticate")
async def authenticate():
    credentials = google_oauth.authenticate()
    if not credentials.get("status"):  # Check if authentication failed
        raise HTTPException(status_code=400, detail=credentials.get("message"))
    return credentials

@router.post("/upload")
async def upload_file(input_data: FileNamesInput):
    """
    Uploads files to Google Drive.
    """
    uploaded_files = drive_upload.upload_files(input_data.file_names)
    return {"uploaded_files": uploaded_files}

@router.get("/list_files")
async def list_files():
    """
    Lists files in a specified Google Drive folder.
    """
    response = file_list.list_files_in_folder()
    if not response.get("status"):
        raise HTTPException(status_code=400, detail="Failed to list files")
    return response

@router.post("/download")
async def download_files(input_data: FileNamesInput):
    """
    Downloads specified files from Google Drive.
    """
    downloaded_files = drive_download.download_files(input_data.file_names)
    if not downloaded_files.get("status"):
        raise HTTPException(status_code=400, detail="Failed to download files")
    return downloaded_files

@router.post("/build_index")
async def build_index_route(input_data: FileNamesInput):
    """
    Builds an index from the given list of file names.
    """
    response = create_embeddings.process_and_build_index(input_data.file_names)
    if not response.get("status"):
        raise HTTPException(status_code=400, detail=response.get("message"))
    return response

@router.post("/search")
async def search_route(input_data: QueryInput):
    """
    Searches the index for the given query and returns ranked results.
    """
    index = vector_search.load_index()
    if not index:
        raise HTTPException(status_code=400, detail="Failed to load the index.")
    
    results = vector_search.ranksearch(index, input_data.query)
    if not results.get('status'):
        raise HTTPException(status_code=400, detail="No results found.")
    
    return {"query": input_data.query, "results": results.get('ranked_results', [])}

@router.post("/generate_prompt")
async def prompt_generator(input_data: TaskOrPromptInput):
    """
    Generates a system prompt based on the provided task or existing prompt.
    """
    response = generate_prompt.generate_system_prompt(input_data.task_or_prompt)
    
    if response.get('status') == 'failed':
        raise HTTPException(status_code=400, detail=response.get('message'))
    
    return response

@router.post("/generate_response")
async def generate_query_response(input_data: QueryInput):
    """
    Generates a response based on the user's query using the system prompt.
    """
    response = generate_response.generate_chat_completion(input_data.query)
    
    if response.get('status') == 'error':
        raise HTTPException(status_code=400, detail=response.get('message'))
    
    return response