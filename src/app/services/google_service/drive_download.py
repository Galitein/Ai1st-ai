import io
import os
import json
import logging
from dotenv import load_dotenv
import asyncio
from concurrent.futures import ThreadPoolExecutor

from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from google.oauth2.credentials import Credentials

load_dotenv()

SCOPES = os.getenv("SCOPES")
CREDENTIALS_PATH = os.getenv("CREDENTIALS_PATH")
DOWNLOAD_PATH = os.getenv("DOWNLOAD_PATH")

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("google_oauth.log"),
        logging.StreamHandler()
    ]
)

async def download_files(file_names):
    """
    Downloads specified text files from a Google Drive folder.

    Args:
        file_names (list): List of filenames to download.
    Returns:
        dict: { "status": bool, "files": list }
    """
    executor = ThreadPoolExecutor()

    # Load credentials JSON and folder_id
    try:
        credentials_data = json.load(open(CREDENTIALS_PATH, 'r'))
        folder_id = credentials_data.get('folder_id').get('folder_id', None)
        if not folder_id:
            raise ValueError("Missing 'folder_id' in credentials file.")
    except Exception as e:
        logging.error("Error loading credentials: %s", e)
        return {"status": False, "files": []}

    # Load OAuth credentials
    try:
        creds = Credentials.from_authorized_user_file(CREDENTIALS_PATH, SCOPES)
        drive_service =  build('drive', 'v3', credentials=creds)
        logging.info("Google Drive service initialized.")
    except Exception as e:
        logging.error("Failed to initialize Drive API: %s", e)
        return {"status": False, "files": []}

    downloaded_files = []
    os.makedirs(DOWNLOAD_PATH, exist_ok=True)

    # Iterate and download each file
    for file_name in file_names:
        try:
            query = f"'{folder_id}' in parents and name = '{file_name}' and trashed = false"
            results = drive_service.files().list(
                    q=query,
                    spaces='drive',
                    fields='files(id, name)',
                    pageSize=1
                ).execute()
            files = results.get('files', [])

            if not files:
                logging.warning("File not found: %s", file_name)
                continue

            file_id = files[0]['id']
            logging.info("Downloading file '%s' (ID: %s)", file_name, file_id)

            request = drive_service.files().get_media(fileId=file_id)
            file_content = io.BytesIO()
            downloader = MediaIoBaseDownload(file_content, request)

            done = False
            while not done:
                status, done =  downloader.next_chunk
                logging.info("Download progress for '%s': %d%%", file_name, int(status.progress() * 100))

            # Save to local directory
            file_content.seek(0)
            local_path = os.path.join(DOWNLOAD_PATH, file_name)
            with open(local_path, 'wb') as f:
                f.write(file_content.read())
            logging.info("File saved to: %s", local_path)

            downloaded_files.append(local_path)

        except Exception as e:
            logging.error("Failed to download '%s': %s", file_name, e)
        
    return {"status": bool(downloaded_files), "files": downloaded_files}


if __name__ == '__main__':
    import asyncio
    files_to_download = ["symfonyUpgrade.txt","symfonySetup.txt", "symfonyFundamentals.txt", "symfonyDoctrine.txt", "symfonyDoc.txt"] # Replace with your target filenames
    result = asyncio.run(download_files(files_to_download))

    if result['status']:
        logging.info(f"✅ Successfully downloaded files: {result['files']}")
    else:
        logging.error("❌ Failed to download one or more files. Check logs.")
