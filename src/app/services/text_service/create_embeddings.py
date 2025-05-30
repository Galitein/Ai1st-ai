import os
import json
import io
import logging

from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from google.oauth2.credentials import Credentials

from txtai import Embeddings
from txtai.pipeline import Similarity

import torch
import nltk
nltk.download('punkt')

DATA_DIR = "downloads"  # Directory containing text files
INDEX_DIR = "index"
CHUNK_BY = "paragraphs"  # or "sentences"
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
CREDENTIALS_PATH = "src/app/utils/token.json"
SCOPES = ['https://www.googleapis.com/auth/drive']
similarity = Similarity("valhalla/distilbart-mnli-12-3")

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("google_oauth.log"),
        logging.StreamHandler()
    ]
)

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
logging.info(f"Using device: {device}")

def chunk_text(text, max_len=500, overlap=50):
    """
    Splits text into chunks of max_len characters with overlap.
    """
    chunks = []
    start = 0
    while start < len(text):
        end = start + max_len
        chunks.append(text[start:end])
        start = end - overlap  # Move the start back by the overlap
    return chunks

def load_documents(file_names):
    """
    Loads documents from Google Drive based on the provided file names.

    Args:
        file_names (list): List of file names to load.

    Returns:
        list: A list of text chunks from the loaded files.
    """
    try:
        with open(CREDENTIALS_PATH, 'r') as cred_file:
            credentials_data = json.load(cred_file)
        folder_id = credentials_data.get('folder_id', {}).get('folder_id', None)
        if not folder_id:
            raise ValueError("Missing 'folder_id' in credentials file.")
    except Exception as e:
        logging.error("Error loading credentials: %s", e)
        return []

    # Load OAuth credentials
    try:
        creds = Credentials.from_authorized_user_file(CREDENTIALS_PATH, SCOPES)
        drive_service = build('drive', 'v3', credentials=creds)
        logging.info("Google Drive service initialized.")
    except Exception as e:
        logging.error("Failed to initialize Drive API: %s", e)
        return []

    documents = []

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
                status, done = downloader.next_chunk()
                logging.info("Download progress for '%s': %d%%", file_name, int(status.progress() * 100))

            file_content.seek(0)
            page_content = file_content.read().decode('utf-8')
            preprocessed_content = page_content.replace('\n', ' ')
            chunks = chunk_text(preprocessed_content, max_len=500, overlap=50)
            logging.info(f"Loaded {len(chunks)} chunks from file: {file_name}")
            for chunk in chunks:
                documents.append(chunk.strip())
        except Exception as e:
            logging.error(f"Error processing file {file_name}: {e}")
            continue

    logging.info(f"Total paragraphs loaded: {len(documents)}")
    return documents

def build_index(documents, model=MODEL_NAME, save_path=INDEX_DIR):
    """
    Builds and saves a txtai index from the provided documents.

    Args:
        documents (list): List of text chunks to index.
        model (str): Path to the embedding model.
        save_path (str): Directory to save the index.

    Returns:
        dict: A dictionary containing the status and index details.
    """
    try:
        index = Embeddings({"path": model, "content": True, "metric": "cosine"})
        index.index(documents)
        index.save(save_path)
        logging.info(f"Contents of {save_path} after saving: {os.listdir(save_path)}")
        if not os.path.exists(os.path.join(save_path, "ids")):
            raise FileNotFoundError("The 'ids' file is missing after saving the index.")
        return {"status": True, "message": "Index built successfully.", "index_path": save_path}
    except Exception as e:
        logging.error(f"Error building index: {e}")
        return {"status": False, "message": str(e)}

def process_and_build_index(file_names):
    """
    Loads documents from the given file names, builds an index, and saves it.

    Args:
        file_names (list): List of file names to process.

    Returns:
        dict: A dictionary containing the status and index details.
    """
    documents = load_documents(file_names)
    if not documents:
        return {"status": False, "message": "No documents were loaded."}
    return build_index(documents)

