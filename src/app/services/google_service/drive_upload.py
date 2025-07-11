import os
import json
import logging
import asyncio
from dotenv import load_dotenv

from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials

import aiofiles

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

async def upload_files(file_names):
    """
    Uploads a list of files to a specific Google Drive folder.

    Args:
        file_names (list): List of file paths to upload.

    Returns:
        dict: { "status": bool, "files": {file_name: file_id} }
    """
    logging.info("Starting upload for files: %s", file_names)

    # Load folder ID from credentials file
    try:
        async with aiofiles.open(CREDENTIALS_PATH, 'r') as f:
            cred_data = json.loads(await f.read())
        folder_id = cred_data.get('folder_id').get('folder_id')
        if not folder_id:
            raise ValueError("Missing 'folder_id' in token.json.")
    except Exception as e:
        logging.error("Failed to load credentials: %s", e)
        return {"status": False, "message": "Failed to load credentials."}

    # Load authorized credentials
    try:
        creds = Credentials.from_authorized_user_file(CREDENTIALS_PATH, SCOPES)
        drive_service = build('drive', 'v3', credentials=creds)
        logging.info("Google Drive service initialized.")
    except Exception as e:
        logging.error("Failed to initialize Google Drive API: %s", e)
        return {"status": False, "message": "Failed to initialize Google Drive API."}

    uploaded_files = {}

    # Upload each file
    for file_path in file_names:
        if not os.path.exists(file_path):
            logging.error("File not found: %s", file_path)
            return {"status": False, "message": f"File '{file_path}' does not exist."}

        try:
            file_name = os.path.basename(file_path)
            file_metadata = {'name': file_name, 'parents': [folder_id]}
            media = MediaFileUpload(file_path, resumable=True)

            uploaded = drive_service.files().create(
                    body=file_metadata,
                    media_body=media,
                    fields='id'
                ).execute()

            file_id = uploaded.get('id')
            uploaded_files[file_name] = file_id
            logging.info("Uploaded '%s' (ID: %s)", file_name, file_id)

        except Exception as e:
            logging.error("Failed to upload '%s': %s", file_path, e)

    if uploaded_files:
        return {"status": True, "files": uploaded_files}
    else:
        return {"status": False, "message": f"File '{file_path}' does not upload successfully"}


# if __name__ == '__main__':
#     import sys
#     files = ['README.md', 'requirements.txt']  # Replace with your file list

#     async def main():
#         response = upload_files(files)
#         print("Response:", json.dumps(response, indent=2))

#     asyncio.run(main())
