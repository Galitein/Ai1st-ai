import os
import json
import logging
# import threading
import requests
from dotenv import load_dotenv

from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from datetime import datetime, timedelta

from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from google.oauth2 import id_token
from google.auth.exceptions import GoogleAuthError
import google.auth.transport.requests

# from src.app.services.google_service.create_folder import get_or_create_drive_folder

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("google_oauth.log"),
        logging.StreamHandler()
    ]
)

load_dotenv()

SCOPES_URL = os.getenv("SCOPES_URL")
SCOPES = [SCOPES_URL]
CREDENTIALS_PATH = os.getenv("CREDENTIALS_PATH")
CLIENT_FILE = os.getenv("CLIENT_FILE")
REPO_NAME = os.getenv("REPO_NAME")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")


async def authenticate(request: Request):
    body = await request.json()

    code = body.get("code")
    print(f"[{datetime.now().isoformat()}] Received code: {code}")

    try:
        # Exchange authorization code for tokens using postmessage flow
        token_url = "https://oauth2.googleapis.com/token"
        data = {
            "code": code,
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "redirect_uri": "postmessage",  # Important for auth-code flow from browser
            "grant_type": "authorization_code",
        }

        token_request = requests.post(token_url, data=data)
        token_response = token_request.json()
        print(f"[{datetime.now().isoformat()}] Token response: {token_response}")

        access_token = token_response.get("access_token")
        id_token_str = token_response.get("id_token")
        refresh_token = token_response.get("refresh_token")
        expires_in = token_response.get("expires_in")

        if not access_token or not id_token_str:
            raise HTTPException(status_code=400, detail=f"Failed to get tokens: {token_response}")

        # Verify ID token
        id_info = id_token.verify_oauth2_token(id_token_str, google.auth.transport.requests.Request(), GOOGLE_CLIENT_ID)
        print(f"[{datetime.now().isoformat()}] ID Token Info: {id_info}")

        email = id_info.get("email")
        user_id = id_info.get("sub")

        # Fetch Google Drive files
        drive_url = "https://www.googleapis.com/drive/v3/files"
        headers = {"Authorization": f"Bearer {access_token}"}
        files_response = requests.get(drive_url, headers=headers).json()
        print(f"[{datetime.now().isoformat()}] Drive files response: {files_response}")

        if "error" in files_response:
            raise HTTPException(status_code=400, detail=f"Failed to fetch Drive files: {files_response}")

        expiry_time = datetime.utcnow() + timedelta(seconds=expires_in)

        response = {
            "status": True,
            "token": access_token,
            "refresh_token": refresh_token,
            "token_uri": token_url,
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "scopes": ["https://www.googleapis.com/auth/drive"],
            "universe_domain": "googleapis.com",
            "account": email,
            "expiry": expiry_time.isoformat() + "Z"
        }
        
        # Save the response_payload to CREDENTIALS_PATH as JSON
        with open(CREDENTIALS_PATH, "w") as f:
            json.dump(response, f, indent=4)

        logging.info("Authentication process completed successfully.")

    except GoogleAuthError as e:
        logging.error(f"Google authentication error: {e}")
        response = {'status': False, 'message': f'Google authentication error: {e}'}
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")
        response = {'status': False, 'message': f'An unexpected error occurred: {e}'}

    return response

# def authenticate():
#     try:
#         logging.info("Starting authentication process.")
#         creds = None

#         if os.path.exists(CREDENTIALS_PATH):
#             logging.info(f"Token file found at {CREDENTIALS_PATH}. Loading credentials.")
#             creds = Credentials.from_authorized_user_file(CREDENTIALS_PATH, SCOPES)
#         if not creds or not creds.valid:
#             if creds and creds.expired and creds.refresh_token:
#                 logging.info("Access token expired. Refreshing token.")
#                 request = google.auth.transport.requests.Request()
#                 creds.refresh(request)
#             else:
#                 logging.info("Credentials are invalid or not found. Initiating OAuth flow.")
#                 flow = InstalledAppFlow.from_client_secrets_file(CLIENT_FILE, SCOPES)
#                 creds = flow.run_local_server(
#                     port=9090, 
#                     access_type='offline', 
#                     prompt='consent',
#                     timeout_seconds=120
#                 )
#                 with open(CREDENTIALS_PATH, 'w') as token:
#                     token.write(creds.to_json())

#         logging.info(f"Attempting to create or retrieve folder '{REPO_NAME}' in Google Drive.")
#         folder_id = get_or_create_drive_folder(REPO_NAME, CREDENTIALS_PATH)
#         if folder_id:
#             logging.info(f"Folder '{REPO_NAME}' is ready with ID: {folder_id}")
#         else:
#             logging.error(f"Failed to create or retrieve the folder '{REPO_NAME}'.")

#         # Save the credentials and folder_id to the token file
#         creds_data = json.loads(creds.to_json())
#         creds_data['folder_id'] = folder_id  # Add folder_id to the credentials data
#         with open(CREDENTIALS_PATH, 'w') as token:
#             json.dump(creds_data, token, indent=4)
#         logging.info("New credentials and folder_id saved to token file.")

#         response = {'status': True, 'message': 'Authentication successful'}
#         logging.info("Authentication process completed successfully.")
#     except GoogleAuthError as e:
#         logging.error(f"Google authentication error: {e}")
#         response = {'status': False, 'message': f'Google authentication error: {e}'}
#     except Exception as e:
#         logging.error(f"An unexpected error occurred: {e}")
#         response = {'status': False, 'message': f'An unexpected error occurred: {e}'}

#     return response
