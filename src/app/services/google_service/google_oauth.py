import os
import json
import logging
import threading
import requests

from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from google.auth.exceptions import GoogleAuthError
import google.auth.transport.requests

from src.app.services.google_service.create_folder import get_or_create_drive_folder

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("google_oauth.log"),
        logging.StreamHandler()
    ]
)

token_file = 'src/app/utils/token.json'
scopes = ['https://www.googleapis.com/auth/drive']
client_file = 'src/app/utils/client_secret.json'
repo_name = "ai1st_docs"

def authenticate():
    try:
        logging.info("Starting authentication process.")
        creds = None

        if os.path.exists(token_file):
            logging.info(f"Token file found at {token_file}. Loading credentials.")
            creds = Credentials.from_authorized_user_file(token_file, scopes)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                logging.info("Access token expired. Refreshing token.")
                request = google.auth.transport.requests.Request()
                creds.refresh(request)
            else:
                logging.info("Credentials are invalid or not found. Initiating OAuth flow.")
                flow = InstalledAppFlow.from_client_secrets_file(client_file, scopes)
                creds = flow.run_local_server(
                    bind_addr='127.0.0.1', 
                    port=9090, 
                    access_type='offline', 
                    prompt='consent',
                    timeout_seconds=120
                )
                with open(token_file, 'w') as token:
                    token.write(creds.to_json())

        logging.info(f"Attempting to create or retrieve folder '{repo_name}' in Google Drive.")
        folder_id = get_or_create_drive_folder(repo_name, token_file)
        if folder_id:
            logging.info(f"Folder '{repo_name}' is ready with ID: {folder_id}")
        else:
            logging.error(f"Failed to create or retrieve the folder '{repo_name}'.")

        # Save the credentials and folder_id to the token file
        creds_data = json.loads(creds.to_json())
        creds_data['folder_id'] = folder_id  # Add folder_id to the credentials data
        with open(token_file, 'w') as token:
            json.dump(creds_data, token, indent=4)
        logging.info("New credentials and folder_id saved to token file.")

        response = {'status': True, 'message': 'Authentication successful'}
        logging.info("Authentication process completed successfully.")
    except GoogleAuthError as e:
        logging.error(f"Google authentication error: {e}")
        response = {'status': False, 'message': f'Google authentication error: {e}'}
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")
        response = {'status': False, 'message': f'An unexpected error occurred: {e}'}

    return response