import os
from dotenv import load_dotenv
from fastapi import APIRouter, Request, Query
from fastapi.responses import RedirectResponse, HTMLResponse, JSONResponse
from src.app.services.trello_service import (
    trello_auth, 
    trello_document_search, 
    trello_data_sync
)
from src.app.models.trello_auth_model import TrelloTokenPayload
from src.app.models.input_models import ChatInput, AitIdInput
load_dotenv(override=True)

trello_router = APIRouter(prefix="/trello", tags=["Trello"])
API_BASE = os.getenv("BACKEND_API_URL", "http://localhost:8080")

@trello_router.get("/auth/start")
async def auth_start(ait_id: str = Query(...)):
    """
    Redirects user to Trello for authentication, with ait_id passed in redirect URI
    """
    url = await trello_auth.generate_auth_url(ait_id)
    return RedirectResponse(url)


@trello_router.get("/auth/callback", response_class=HTMLResponse)
async def auth_callback(request: Request):
    ait_id = request.query_params.get("ait_id", "anonymous")
    html_with_user = f"""
    <html>
    <body>
        <h3>Authenticating...</h3>
        <script>
        const token = window.location.hash.split('=')[1];
        if (token) {{
            fetch('{API_BASE}/trello/auth/save-token', {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/json' }},
                body: JSON.stringify({{ token: token, ait_id: "{ait_id}" }})
            }}).then(response => {{
                if (response.ok) {{
                    document.body.innerHTML = "<h3>✅ Token saved successfully!</h3><p>You can close this tab.</p>";
                }} else {{
                    document.body.innerHTML = "<h3>❌ Error saving token</h3><p>Please try again.</p>";
                }}
            }}).catch(error => {{
                console.error('Error:', error);
                document.body.innerHTML = "<h3>❌ Network error</h3><p>Please try again.</p>";
            }});
        }} else {{
            document.body.innerHTML = "<h3>❌ No token received</h3><p>Authentication failed. Please try again.</p>";
        }}
        </script>
    </body>
    </html>
    """ 
    return HTMLResponse(content=html_with_user)

@trello_router.post("/auth/save-token")
async def save_token_endpoint(payload: TrelloTokenPayload):
    """
    Save the Trello token for the authenticated user
    """
    try:
        response = await trello_auth.save_token(payload.ait_id, {"token":payload.token})
        if not response:
            return JSONResponse(
                status_code=400,
                content={
                    "status": False,
                    "message": "Failed to save token"
                }
            )
        return {"status": True, "message": "Token saved successfully"}
    except Exception as e:
        return JSONResponse(
            status_code=400,
            content={
                "status": False,
                "message": "Failed to save token"
            }
        )

@trello_router.post("/trello_document_search")
async def trello_search(input_data: ChatInput):
    try:
        trello_documents = await trello_document_search.search_trello_documents(
            ait_id=input_data.ait_id, 
            query=input_data.query
            )
        if not trello_documents.get("status"):
            return JSONResponse(
                status_code=400,
                content={
                    "status": False,
                    "message": trello_documents.get("message")
                }
            )
        return trello_documents
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "status": False,
                "message": trello_documents.get("message", str(e))
            }
        )

@trello_router.post("/trello_document_sync")
async def trello_sync(input_data: AitIdInput):
    """
    Sync Trello documents for the authenticated user
    """
    try:
        trello_documents = await trello_data_sync.trello_data_sync(ait_id=input_data.ait_id)
        if not trello_documents.get("status"):
            return JSONResponse(
                status_code=400,
                content={
                    "status": False,
                    "message": trello_documents.get("message")
                }
            )
        return trello_documents
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "status": False,
                "message": trello_documents.get("message", str(e))
            }
        )