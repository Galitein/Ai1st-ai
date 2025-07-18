import os
from dotenv import load_dotenv
from msal import ConfidentialClientApplication
from fastapi import APIRouter, Request, Depends, Query
from fastapi.responses import RedirectResponse, JSONResponse, HTMLResponse
from src.app.services.ms_exchange.mse_main import sync_emails as sync_email_data, sync_all_emails, BATCH_SIZE
from src.app.services.ms_exchange.mse_token_store import save_token
from src.app.models.mse_email_models import EmailQueryParams, EmailCBQuery
from typing import Optional, List, Dict, Tuple

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
def login(ait_id: str = Query(...)):
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
    response = await sync_email_data(
        ait_id=params.ait_id #,
        # start_date=params.start_date,
        # end_date=params.end_date,
        # from_email=params.from_email,
        # unread_only=params.unread_only,
        # search=params.search,
        # top=params.top,
        # orderby=params.orderby,
        # next_url=params.next_url
    )
    return response

@ms_router.post("/sync-all-emails")
async def sync_all_emails_endpoint(
    ait_id: str = Query(..., description="User authentication ID"),
    # start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    # end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    # batch_size: int = Query(BATCH_SIZE, ge=100, le=2000, description="Batch size for processing"),
    # max_emails: Optional[int] = Query(None, ge=1, description="Maximum emails to sync (for testing)"),
    # resume_token: Optional[str] = Query(None, description="Resume token for continuing previous sync")
):
    """
    Sync all emails from Outlook to vector database.
    Use this endpoint when a user logs in to get all existing emails.
    """
    result = await sync_all_emails(
        ait_id=ait_id #,
        # start_date=start_date,
        # end_date=end_date,
        # batch_size=batch_size,
        # max_emails=max_emails,
        # resume_token=resume_token
    )
    
    if result.get("success"):
        return JSONResponse(content=result, status_code=200)
    else:
        return JSONResponse(content=result, status_code=result.get("status_code", 500))