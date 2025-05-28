from fastapi import APIRouter
from src.app.services import example_service, google_oauth

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