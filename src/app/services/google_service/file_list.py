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

async def list_files_in_folder(parent_folder_id: str):
    """
    Lists all files in the specified folder in the user's Google Drive,
    and saves the parent_folder_id in the credentials file.

    Args:
        parent_folder_id (str): The ID of the parent folder.

    Returns:
        dict: A dictionary containing the status and a list of files (with their IDs and names).
    """

    # Load the credentials file
    try:
        credentials_data = json.load(open(CREDENTIALS_PATH, 'r'))
    except FileNotFoundError:
        logging.error("Credentials file not found at: %s", CREDENTIALS_PATH)
        return {"status": False, "files": []}
    except json.JSONDecodeError as e:
        logging.error("Failed to parse credentials file: %s", e)
        return {"status": False, "files": []}

    # Save the parent_folder_id in the credentials file
    credentials_data["folder_id"] = {
        "status": True,
        "folder_id": parent_folder_id
    }
    try:
        json.dump(credentials_data, open(CREDENTIALS_PATH, 'w'), indent=4)
        logging.info("Saved parent_folder_id %s to credentials file.", parent_folder_id)
    except Exception as e:
        logging.error("Failed to save parent_folder_id to credentials file: %s", e)

    try:
        creds = Credentials.from_authorized_user_file(CREDENTIALS_PATH, SCOPES)
        drive_service = build('drive', 'v3', credentials=creds)
        logging.info("Google Drive service initialized successfully.")
    except Exception as e:
        logging.error("Failed to initialize Google Drive service: %s", e)
        return {"status": False, "files": []}

    try:
        query = f"'{parent_folder_id}' in parents and trashed = false"
        files = []
        page_token = None

        while True:
            results = drive_service.files().list(
                    q=query,
                    pageSize=100,
                    fields="nextPageToken, files(id, name, mimeType)",
                    pageToken=page_token
                ).execute()
            items = results.get('files', [])
            print(f"Found {items} files in the folder.")
            files.extend({"id": item["id"], "name": item["name"], "file_type":item["mimeType"]} for item in items)
            page_token = results.get('nextPageToken', None)
            if not page_token:
                break

        logging.info("Successfully retrieved %d files from the folder.", len(files))
        return {"status": True, "files": files}

    except HttpError as e:
        logging.error("Google Drive API error: %s", e)
        return {"status": False, "files": []}
    except Exception as e:
        logging.error("An unexpected error occurred while listing files: %s", e)
        return {"status": False, "files": []}
