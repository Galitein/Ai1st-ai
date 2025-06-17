import os
import json
import logging
from dotenv import load_dotenv
import asyncio
from concurrent.futures import ThreadPoolExecutor

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

async def list_folders_in_drive():
    """
    Lists folders in the user's Google Drive.

    Returns:
        dict: A dictionary containing the status and a list of folders (with their IDs and names).
    """

    # Load the credentials file
    try:
        credentials_data = json.load(open(CREDENTIALS_PATH, 'r'))
    except FileNotFoundError:
        logging.error("Credentials file not found at: %s", CREDENTIALS_PATH)
        return {"status": False, "folders": []}
    except json.JSONDecodeError as e:
        logging.error("Failed to parse credentials file: %s", e)
        return {"status": False, "folders": []}

    try:
        creds = Credentials.from_authorized_user_file(CREDENTIALS_PATH, SCOPES)
        drive_service = build('drive', 'v3', credentials=creds)
        logging.info("Google Drive service initialized successfully.")
    except Exception as e:
        logging.error("Failed to initialize Google Drive service: %s", e)
        return {"status": False, "folders": []}

    try:
        # To list all folders in the drive:
        query = "mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        # If you want folders inside a specific parent, uncomment and use:
        # query = f"'{parent_folder_id}' in parents and mimeType = 'application/vnd.google-apps.folder' and trashed = false"

        results = drive_service.files().list(
                q=query,
                pageSize=100,
                fields="nextPageToken, files(id, name)"
            ).execute()
        items = results.get('files', [])
        logging.info("Successfully retrieved %d folders from the drive.", len(items))

        folders = [{"id": item["id"], "name": item["name"]} for item in items]
        return {"status": True, "folders": folders}

    except HttpError as e:
        logging.error("Google Drive API error: %s", e)
        return {"status": False, "folders": []}
    except Exception as e:
        logging.error("An unexpected error occurred while listing folders: %s", e)
        return {"status": False, "folders": []}

# response = list_folders_in_drive()
# print(response)