from fastapi import APIRouter, HTTPException

from src.app.services.google_service import (
    google_oauth, 
    drive_upload, 
    file_list, 
    drive_download
)
from src.app.services.text_service import (
    create_embeddings, 
    text_search
)

router = APIRouter()

@router.get("/")
async def root():
    return {"message": "Welcome to the Uvicorn App"}

@router.get("/service")
async def service_example():
    return example_service.get_example_data()

@router.get("/authenticate")
async def authenticate():
    credentials = google_oauth.authenticate()
    if not credentials.get("status"):  # Check if authentication failed
        raise HTTPException(status_code=400, detail=credentials.get("message"))
    return credentials

@router.post("/upload")
async def upload_file(file_names: list[str]):
    """
    Uploads a file to Google Drive.
    
    Args:
        file_name (str): The name of the file to upload.
    
    Returns:
        dict: A dictionary containing the file ID of the uploaded file.
    """
    uploaded_files = drive_upload.upload_files(file_names)
    return {"uploaded_files": uploaded_files}


@router.get("/list_files")
async def list_files():
    """
    Lists files in a specified Google Drive folder.
    
    Returns:
        list: A list of files (with their IDs and names) in the folder.
    """
    response = file_list.list_files_in_folder()
    if not response.get("status"):
        raise HTTPException(status_code=400, detail="Failed to list files")
    return response

@router.post("/download")
async def download_files(file_names: list[str]):
    """
    Downloads specified files from Google Drive.
    
    Args:
        file_names (list): List of filenames to download.
    
    Returns:
        dict: A dictionary containing the status and list of downloaded files.
    """
    downloaded_files = drive_download.download_files(file_names)
    if not downloaded_files.get("status"):
        raise HTTPException(status_code=400, detail="Failed to download files")
    return downloaded_files

@router.post("/build_index")
async def build_index_route(file_names: list[str]):
    """
    Builds an index from the given list of file names.

    Args:
        file_names (list): List of file names to process.

    Returns:
        dict: A dictionary containing the status and index details.
    """
    response = create_embeddings.process_and_build_index(file_names)
    if not response.get("status"):
        raise HTTPException(status_code=400, detail=response.get("message"))
    return response


@router.post("/search")
async def search_route(query: str):
    """
    Searches the index for the given query and returns ranked results.

    Args:
        query (str): The search query.

    Returns:
        list: A list of ranked search results.
    """
    index = text_search.load_index()
    if not index:
        raise HTTPException(status_code=400, detail="Failed to load the index.")
    
    results = text_search.ranksearch(index, query)
    if not results:
        raise HTTPException(status_code=400, detail="No results found.")
    
    return {"query": query, "results": results}