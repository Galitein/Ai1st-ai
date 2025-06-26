import os
from dotenv import load_dotenv
from msal import ConfidentialClientApplication
from fastapi import APIRouter, Request, Depends, Query
from fastapi.responses import RedirectResponse, JSONResponse
from src.app.services.msexchange_auth.mse_main import get_emails as fetch_emails, sync_emails as sync_email_data
from src.app.services.msexchange_auth.token_store import save_token
from src.app.models.mse_email_models import EmailQueryParams

load_dotenv(override=True)

ms_router = APIRouter(prefix="/ms_auth", tags=["MSExchange"])

AZURE_CLIENT_ID = os.getenv("AZURE_CLIENT_ID")
AZURE_SECRET_ID = os.getenv("AZURE_SECRET_VALUE")
TENANT_ID = os.getenv("TENANT_ID")
REDIRECT_URI = os.getenv("REDIRECT_URI")
AUTHORITY = "https://login.microsoftonline.com/common"
AUTH_SCOPES = ["Mail.ReadWrite", "Calendars.ReadWrite", "Contacts.ReadWrite"]
GRAPH_SCOPES = ["Mail.ReadWrite", "Calendars.ReadWrite", "Contacts.ReadWrite"]
DEFAULT_USER_ID = "anonymous"

msal_app = ConfidentialClientApplication(
    client_id=AZURE_CLIENT_ID,
    client_credential=AZURE_SECRET_ID,
    authority=AUTHORITY
)

@ms_router.get("/login")
def login(user_id: str = Query(...)):
    auth_url = msal_app.get_authorization_request_url(
        scopes=AUTH_SCOPES,
        redirect_uri=REDIRECT_URI,
        state=user_id 
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
        await save_token(state, result)  # state = user_id
        return JSONResponse({"message": "Login successful, you can close this window"})
    return JSONResponse({"error": result.get("error_description")})


@ms_router.get("/me/emails")
async def get_emails(params: EmailQueryParams = Depends()):
    """
    Get emails with proper filtering and edge case handling.
    """
    response = await fetch_emails(
        user_id=params.user_id,
        start_date=params.start_date,
        end_date=params.end_date,
        from_email=params.from_email,
        unread_only=params.unread_only,
        search=params.search,
        top=params.top,
        orderby=params.orderby,
        next_url=params.next_url
    )
    return response


@ms_router.post("/me/emails/sync")
async def sync_emails(params: EmailQueryParams):
    """
    Sync emails to MongoDB with proper filtering and edge case handling.
    """
    response = await sync_email_data(
        user_id=params.user_id,
        start_date=params.start_date,
        end_date=params.end_date,
        from_email=params.from_email,
        unread_only=params.unread_only,
        search=params.search,
        top=params.top,
        orderby=params.orderby,
        next_url=params.next_url
    )
    return response
