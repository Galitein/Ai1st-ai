import os
import json
import uuid
from dotenv import load_dotenv
from datetime import datetime
from msal import ConfidentialClientApplication
from fastapi import Path, BackgroundTasks, HTTPException, status, APIRouter, Request, Depends, Query
from fastapi.responses import RedirectResponse, JSONResponse, HTMLResponse
from src.app.services.ms_exchange.mse_main import sync_emails as sync_email_data, sync_all_emails, BATCH_SIZE, get_all_folders
from src.app.services.ms_exchange.mse_token_store import save_token
from src.app.models.mse_email_models import EmailQueryParams, EmailCBQuery, SyncStatusResponse
from typing import Optional, List, Dict, Tuple
from src.app.utils.ms_email_utils import get_processing_metadata
from src.database.sql import AsyncMySQLDatabase
mysql_db = AsyncMySQLDatabase()
from src.app.utils.helpers import is_valid_ait_id

load_dotenv(override=True)

ms_router = APIRouter(prefix="/ms_exchange", tags=["MSExchange"])

AZURE_CLIENT_ID = os.getenv("AZURE_CLIENT_ID")
AZURE_SECRET_ID = os.getenv("AZURE_SECRET_VALUE")
TENANT_ID = os.getenv("TENANT_ID")
REDIRECT_URI = os.getenv("MSE_REDIRECT_URI")
AUTHORITY = "https://login.microsoftonline.com/common"
AUTH_SCOPES = ["Mail.ReadWrite", "Calendars.ReadWrite", "Contacts.ReadWrite"]
GRAPH_SCOPES = ["Mail.ReadWrite", "Calendars.ReadWrite", "Contacts.ReadWrite"]
DEFAULT_USER_ID = "anonymous"
import time 

time.sleep(2)
msal_app = ConfidentialClientApplication(
    client_id=AZURE_CLIENT_ID,
    client_credential=AZURE_SECRET_ID,
    authority=AUTHORITY
)

@ms_router.get("/login")
async def login(ait_id: str = Query(...)):
    if not await is_valid_ait_id(ait_id):
        raise HTTPException(status_code=400, detail="Invalid ait_id")
    
    auth_url = msal_app.get_authorization_request_url(
        scopes=AUTH_SCOPES,
        redirect_uri=REDIRECT_URI,
        state=ait_id
    )
    return RedirectResponse(auth_url)


@ms_router.get("/azurecallback")
async def callback(request: Request):
    code = request.query_params.get("code")
    state = request.query_params.get("state", DEFAULT_USER_ID)
    if not await is_valid_ait_id(state):
        raise HTTPException(status_code=400, detail="Invalid ait_id")

    result = msal_app.acquire_token_by_authorization_code(
        code,
        scopes=GRAPH_SCOPES,
        redirect_uri=REDIRECT_URI
    )
    if "access_token" in result:
        await save_token(state, result)
        html_content = """
        <html>
            <head>
                <title>Login Successful</title>
                <script>
                    setTimeout(function() {
                        window.close();
                    }, 3000);
                </script>
            </head>
            <body>
                <p>Login successful. This window will be closed</p>
            </body>
        </html>
        """
        return HTMLResponse(content=html_content)
    
    return JSONResponse({"error": result.get("error_description")})


@ms_router.post("/email/sync_new_emails")
async def sync_emails(params: EmailQueryParams):
    """
    Sync emails to MySQL and create vector embeddings in Qdrant with proper chunking.
    """
    if not await is_valid_ait_id(params.ait_id):
        raise HTTPException(status_code=400, detail="Invalid ait_id")

    response = await sync_email_data(
        ait_id=params.ait_id
    )
    return response

@ms_router.post("/sync-all-emails")
async def sync_all_emails_endpoint(
    background_tasks: BackgroundTasks,
    input_data : EmailQueryParams = Query(..., description="User authentication ID")
):
    """
    Sync all emails from Outlook to vector database.
    Use this endpoint when a user logs in to get all existing emails.
    """
    if not await is_valid_ait_id(input_data.ait_id):
        raise HTTPException(status_code=400, detail="Invalid ait_id")

    progress_id = str(uuid.uuid4())
    try:
        # 1. Get the total number of emails to establish the 'total' for our progress bar.
        total_email_count = await get_all_folders(input_data.ait_id)

        print(f"here is the total email coutn : {total_email_count}")

        initial_record = {
            'progress_id': progress_id,
            'custom_gpt_id': input_data.ait_id,
            'total': total_email_count,
            'processed': 0,
            'status': 'pending',
            'meta': json.dumps({'request_time': datetime.utcnow().isoformat()}),
            'remarks': 'Synchronization has been queued and is waiting to start.'
        }
        await mysql_db.create_pool()
        await mysql_db.insert('processing_status', initial_record)
        await mysql_db.close_pool()

        background_tasks.add_task(sync_all_emails, ait_id=input_data.ait_id, progress_id=progress_id)

        return {"processing_id": progress_id}

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not start the synchronization process. Error: {e}"
        )

@ms_router.get("/status/{processing_id}", response_model=SyncStatusResponse)
async def get_sync_status(
    ait_id, processing_id: str = Path(..., title="Processing ID", description="The unique ID generated when the synchronization process started.")
):
    """
    Retrieves the real-time synchronization status for a given processing ID.
    """
    if not processing_id or not await is_valid_ait_id(input_data.ait_id):
        raise HTTPException(status_code=400, detail="Invalid ait_id")

    response = await get_processing_metadata(processing_id)

    return response