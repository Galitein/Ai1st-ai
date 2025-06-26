import os
from dotenv import load_dotenv
from fastapi import APIRouter, Request, Query
from fastapi.responses import RedirectResponse, HTMLResponse
from src.app.services.trello_auth.trello_auth_utils import generate_auth_url, save_token
from src.app.models.trello_auth_model import TrelloTokenPayload

load_dotenv(override=True)

trello_auth_router = APIRouter(prefix="/trello", tags=["Trello"])
API_BASE = os.getenv("BACKEND_API_URL", "http://localhost:8080")

@trello_auth_router.get("/auth/start")
async def auth_start(user_id: str = Query(...)):
    """
    Redirects user to Trello for authentication, with user_id passed in redirect URI
    """
    url = generate_auth_url(user_id)
    return RedirectResponse(url)


@trello_auth_router.get("/auth/callback", response_class=HTMLResponse)
async def auth_callback(request: Request):
    user_id = request.query_params.get("user_id", "anonymous")  # Now you should get real user_id
    html_with_user = f"""
    <html>
    <body>
        <h3>Authenticating...</h3>
        <script>
        const token = window.location.hash.split('=')[1];
        fetch('{API_BASE}/trello/auth/save-token', {{
            method: 'POST',
            headers: {{ 'Content-Type': 'application/json' }},
            body: JSON.stringify({{ token: token, user_id: "{user_id}" }})
        }}).then(() => {{
            document.body.innerHTML = "Token saved successfully. You can close this tab.";
        }});
        </script>
    </body>
    </html>
    """ 
    return HTMLResponse(content=html_with_user)


@trello_auth_router.post("/auth/save-token")
async def save_token_endpoint(payload: TrelloTokenPayload):
    print("🔐 Trello Login Payload:", payload)
    await save_token(payload.user_id, payload.token)
    return {"status": "Token saved successfully"}
