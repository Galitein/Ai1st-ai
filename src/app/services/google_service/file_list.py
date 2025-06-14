import os
import json
import logging
from dotenv import load_dotenv

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

load_dotenv()

SCOPES = os.getenv("SCOPES")
CREDENTIALS_PATH = os.getenv("CREDENTIALS_PATH")

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("google_oauth.log"),
        logging.StreamHandler()
    ]
)

def list_files_in_folder():
    """
    Lists files in a specified Google Drive folder.

    Returns:
        dict: A dictionary containing the status and a list of files (with their IDs and names).
    """

    # Load the credentials file
    try:
        with open(CREDENTIALS_PATH, 'r') as cred_file:
            credentials_data = json.load(cred_file)
        folder_id = credentials_data.get('folder_id', None).get('folder_id', None)
    except FileNotFoundError:
        logging.error("Credentials file not found at: %s", CREDENTIALS_PATH)
        return {"status": False, "files": []}
    except json.JSONDecodeError as e:
        logging.error("Failed to parse credentials file: %s", e)
        return {"status": False, "files": []}

    try:
        creds = Credentials.from_authorized_user_file(CREDENTIALS_PATH, SCOPES)
        drive_service = build('drive', 'v3', credentials=creds)
        logging.info("Google Drive service initialized successfully.")
    except Exception as e:
        logging.error("Failed to initialize Google Drive service: %s", e)
        return {"status": False, "files": []}

    try:
        query = f"'{folder_id}' in parents"  # Query to list files in the folder
        results = drive_service.files().list(
            q=query,
            pageSize=100,  # Adjust the page size as needed
            fields="nextPageToken, files(id, name)"
        ).execute()
        items = results.get('files', [])
        logging.info("Successfully retrieved %d files from the folder.", len(items))

        # Prepare the response structure
        files = [{"id": item["id"], "name": item["name"]} for item in items]
        return {"status": True, "files": files}

    except HttpError as e:
        logging.error("Google Drive API error: %s", e)
        return {"status": False, "files": []}
    except Exception as e:
        logging.error("An unexpected error occurred while listing files: %s", e)
        return {"status": False, "files": []}

# response = list_files_in_folder()
# print(response)