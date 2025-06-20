import os
import json
import logging
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from langchain_core.documents import Document
from dotenv import load_dotenv
from src.app.utils.helpers import chunk_text, load_content_drive_file

load_dotenv()
CREDENTIALS_PATH = os.getenv("CREDENTIALS_PATH")
SCOPES = os.getenv("SCOPES")

async def load_documents(file_names, ait_id, logger=None):
    """
    Loads and chunks documents from Google Drive.

    Args:
        file_names (list): List of file names to load.
        ait_id (str): Unique identifier for the AIT.
        logger: Logger instance (optional).

    Returns:
        list: List of Document objects.
    """
    if logger is None:
        logger = logging.getLogger(__name__)
    try:
        with open(CREDENTIALS_PATH, 'r') as cred_file:
            credentials_data = json.loads(cred_file.read())
        folder_id = credentials_data.get('folder_id', {}).get('folder_id', None)
        if not folder_id:
            raise ValueError("Missing 'folder_id' in credentials file.")
    except Exception as e:
        logger.error("Error loading credentials: %s", e)
        return []

    try:
        creds = Credentials.from_authorized_user_file(CREDENTIALS_PATH, SCOPES)
        drive_service = build('drive', 'v3', credentials=creds)
        logger.info("Google Drive service initialized.")
    except Exception as e:
        logger.error("Failed to initialize Drive API: %s", e)
        return []

    documents = []

    for file_name in file_names:
        try:
            page_content, modified_time = load_content_drive_file(drive_service, folder_id, file_name, logger)
            if not page_content:
                continue
            preprocessed_content = page_content.replace('\n', ' ')
            chunks = chunk_text(preprocessed_content, max_len=500, overlap=50)
            logger.info(f"Loaded {len(chunks)} chunks from file: {file_name}")
            for idx, chunk in enumerate(chunks):
                documents.append(
                    Document(
                        page_content=chunk.strip(),
                        metadata={
                            "ait_id": ait_id,
                            "type": "bib",
                            "file_name": file_name,
                            "chunk_index": idx,
                            "modified_time": modified_time,
                            "source_id": f"{ait_id}_{file_name}_{idx}"
                        }
                    )
                )
        except Exception as e:
            logger.error(f"Error processing file {file_name}: {e}")
            continue

    logger.info(f"Total paragraphs loaded: {len(documents)}")
    return documents
