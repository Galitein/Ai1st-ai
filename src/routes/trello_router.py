import os
from dotenv import load_dotenv
from fastapi import APIRouter, Request, Query
from fastapi.responses import RedirectResponse, HTMLResponse
from src.app.services.trello_service.trello_auth import generate_auth_url, save_token
from src.app.models.trello_auth_model import TrelloTokenPayload

load_dotenv(override=True)

trello_auth_router = APIRouter(prefix="/trello", tags=["Trello"])
API_BASE = os.getenv("BACKEND_API_URL", "http://localhost:8080")

@trello_auth_router.get("/auth/start")
async def auth_start(ait_id: str = Query(...)):
    """
    Redirects user to Trello for authentication, with ait_id passed in redirect URI
    """
    url = await generate_auth_url(ait_id)
    return RedirectResponse(url)


@trello_auth_router.get("/auth/callback", response_class=HTMLResponse)
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


@trello_auth_router.post("/auth/save-token")
async def save_token_endpoint(payload: TrelloTokenPayload):
    """
    Save the Trello token for the authenticated user
    """
    try:
        success = await save_token(payload.ait_id, {"token":payload.token})
        if success:
            return {"status": "success", "message": "Token saved successfully"}
        else:
            return {"status": "error", "message": "Failed to save token"}
    except Exception as e:
        return {"status": "error", "message": "Internal server error"}