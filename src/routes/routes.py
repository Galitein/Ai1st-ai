from fastapi import APIRouter, HTTPException

from src.app.services.google_service import google_oauth, drive_upload, file_list
# from src.app.models.google_models import UploadFile
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
    uploaded_files = drive_upload.upload_file(file_names)
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