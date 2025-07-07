import os
import json
import logging
import asyncio
from dotenv import load_dotenv

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.oauth2.credentials import Credentials

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("google_oauth.log"),
        logging.StreamHandler()
    ]
)

SCOPES_URL = os.getenv("SCOPES_URL")
SCOPES = [SCOPES_URL]
CREDENTIALS_PATH = os.getenv("CREDENTIALS_PATH")

async def get_or_create_drive_folder(folder_name, CREDENTIALS_PATH):
    """
    Check if a folder exists in Google Drive. If not, create it.

    Args:
        folder_name (str): Name of the folder.
        CREDENTIALS_PATH (str): Path to token.json containing credentials.

    Returns:
        dict: {
            "status": bool,
            "folder_id": str or None
        }
    """
    try:
        creds = await Credentials.from_authorized_user_file(CREDENTIALS_PATH, SCOPES)
        service = await build('drive', 'v3', credentials=creds)
        logging.info("Google Drive API initialized.")

        # Search for the folder
        query = f"name = '{folder_name}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        results = await service.files().list(
                q=query,
                spaces='drive',
                fields='files(id, name)',
                pageSize=1
            ).execute()

        folders = results.get('files', [])
        if folders:
            folder_id = folders[0]['id']
            logging.info("✅ Folder '%s' already exists with ID: %s", folder_name, folder_id)
            return {"status": True, "folder_id": folder_id}

        # Folder does not exist, create it
        folder_metadata = {
            'name': folder_name,
            'mimeType': 'application/vnd.google-apps.folder'
        }
        folder = await  service.files().create(body=folder_metadata, fields='id').execute()
        folder_id = folder.get('id')
        logging.info("📁 Created new folder '%s' with ID: %s", folder_name, folder_id)
        return {"status": True, "folder_id": folder_id}

    except HttpError as error:
        logging.error("Drive API error: %s", error)
        return {"status": False, "folder_id": None}
    except Exception as e:
        logging.error("Unexpected error: %s", e)
        return {"status": False, "folder_id": None}

# ------------------------- USAGE EXAMPLE -------------------------

if __name__ == '__main__':
    folder_name = "txtai_docs"
    CREDENTIALS_PATH = "src/app/utils/token.json"

    async def main():
        result = await get_or_create_drive_folder(folder_name, CREDENTIALS_PATH)
        logging.info(json.dumps(result, indent=2))

    asyncio.run(main())
