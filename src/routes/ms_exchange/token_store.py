import json
from pathlib import Path
from msal import ConfidentialClientApplication
import os
from dotenv import load_dotenv
load_dotenv(override=True)

AZURE_CLIENT_ID = os.getenv("AZURE_CLIENT_ID")
AZURE_SECRET_ID = os.getenv("AZURE_SECRET_VALUE")
TENANT_ID = os.getenv("TENANT_ID")
AUTHORITY = f"https://login.microsoftonline.com/common"

GRAPH_SCOPES = ["Mail.ReadWrite","Calendars.ReadWrite","Contacts.ReadWrite"]

msal_app = ConfidentialClientApplication(
    client_id=AZURE_CLIENT_ID,
    client_credential=AZURE_SECRET_ID,
    authority=AUTHORITY
)

TOKEN_FILE = Path("tokens.json")

def save_token(user_id, token_data):
    tokens = load_tokens()
    tokens[user_id] = token_data
    with open(TOKEN_FILE, "w") as f:
        json.dump(tokens, f, indent=4)

def load_tokens():
    if TOKEN_FILE.exists():
        with open(TOKEN_FILE, "r") as f:
            return json.load(f)
    return {}

def get_token(user_id):
    return load_tokens().get(user_id)

def refresh_access_token(user_id: str) -> str | None:
    print("Going for refreshing token")
    token_data = get_token(user_id)
    refresh_token = token_data.get("refresh_token")
    
    if not refresh_token:
        return None

    result = msal_app.acquire_token_by_refresh_token(
        refresh_token,
        scopes=GRAPH_SCOPES
    )

    if "access_token" in result:
        save_token(user_id, result)
        print("New token updated successfully")
        return result["access_token"]
    
    print("Failed to refresh token:", result.get("error_description"))
    return None

