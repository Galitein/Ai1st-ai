import io
import tiktoken
from datetime import datetime
import tempfile

from googleapiclient.http import MediaIoBaseDownload

from src.app.utils.extractors import image_to_text, audio_to_text


def chunk_text(text, max_tokens=200, overlap=20, encoding_name="cl100k_base"):
    """
    Splits text into overlapping chunks based on tokens.

    Args:
        text (str): The input text to chunk.
        max_tokens (int): Maximum number of tokens per chunk.
        overlap (int): Number of overlapping tokens between chunks.
        encoding_name (str): Encoding name for tiktoken.

    Returns:
        list: List of text chunks.
    """
    enc = tiktoken.get_encoding(encoding_name)
    tokens = enc.encode(text)
    chunks = []
    start = 0
    while start < len(tokens):
        end = start + max_tokens
        chunk_tokens = tokens[start:end]
        chunk_text_part = enc.decode(chunk_tokens)
        chunks.append(chunk_text_part)
        start = end - overlap
    return chunks

def load_content_drive_file(drive_service, folder_id, file_name, logger):
    """
    Download a file from Google Drive by name and folder_id.
    Returns (page_content, modified_time) if found, else (None, None).

    Args:
        drive_service: Google Drive API service instance.
        folder_id (str): ID of the folder to search in.
        file_name (str): Name of the file to download.
        logger: Logger instance for logging.

    Returns:
        tuple: (page_content, modified_time) or (None, None) on failure.
    """

    try:
        query = f"'{folder_id}' in parents and name = '{file_name}' and trashed = false"
        results = drive_service.files().list(
            q=query,
            spaces='drive',
            fields='files(id, name, mimeType, modifiedTime)',
            pageSize=1
        ).execute()
        files = results.get('files', [])

        if not files:
            logger.warning("File not found: %s", file_name)
            return None, None

        file_id = files[0]['id']
        file_mime_type = files[0].get('mimeType', '')
        modified_time = files[0].get('modifiedTime', str(datetime.utcnow()))
        logger.info("Downloading file '%s' (ID: %s)", file_name, file_id)

        request = drive_service.files().get_media(fileId=file_id)
        file_content = io.BytesIO()
        downloader = MediaIoBaseDownload(file_content, request)

        done = False
        while not done:
            status, done = downloader.next_chunk()
            logger.info("Download progress for '%s': %d%%", file_name, int(status.progress() * 100))

        file_content.seek(0)

        if file_mime_type == "text/plain":
            page_content = file_content.read().decode('utf-8')
            content_chunks = chunk_text(page_content.replace('\n', ' '), max_tokens=200, overlap=20)
            return {
                "content_chunks":content_chunks,
                "modified_time":modified_time,
                "file_type":"text"
                }

        elif file_mime_type in ["image/jpeg", "image/png"]:
            suffix = ".jpg" if file_mime_type == "image/jpeg" else ".png"
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_img:
                tmp_img.write(file_content.read())
                tmp_img_path = tmp_img.name
            page_content = image_to_text(tmp_img_path)
            content_chunks = chunk_text(page_content.replace('\n', ' '), max_tokens=200, overlap=20)
            return {
                "content_chunks":content_chunks,
                "modified_time":modified_time,
                "file_type":"image"
                }

        elif file_mime_type in ["audio/x-wav", "audio/mpeg"]:
            suffix = ".wav" if file_mime_type == "audio/x-wav" else ".mp3"
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_audio:
                tmp_audio.write(file_content.read())
                tmp_audio_path = tmp_audio.name
            page_content = audio_to_text(tmp_audio_path)
            content_chunks = chunk_text(page_content.replace('\n', ' '), max_tokens=200, overlap=20)
            return {
                "content_chunks":content_chunks,
                "modified_time":modified_time,
                "file_type":"audio"
                }

        else:
            logger.warning("Unsupported mimeType: %s", file_mime_type)
            return None, None

    except Exception as e:
        logger.error(f"Error downloading file {file_name}: {e}")
        return None, None


def load_content_local_file(file_name, logger):
    """
    Download a file from Google Drive by name and folder_id.
    Returns (page_content, modified_time) if found, else (None, None).

    Args:
        drive_service: Google Drive API service instance.
        folder_id (str): ID of the folder to search in.
        file_name (str): Name of the file to download.
        logger: Logger instance for logging.

    Returns:
        tuple: (page_content, modified_time) or (None, None) on failure.
    """

    try:
        file_mime_type, _ = mimetypes.guess_type(file_name)
        with open(f"./temp/{ait_id}/{file_name}", 'rb') as file:
            file_content = file.read()

        # Text files
        if file_mime_type == "text/plain" or file_path.endswith(('.txt', '.md', '.csv')):
            page_content = file_content.decode('utf-8')
            content_chunks = chunk_text(page_content.replace('\n', ' '), max_tokens=200, overlap=20)
            return {
                "content_chunks": content_chunks,
                "modified_time": modified_time,
                "file_type": "text"
            }

        # Image files
        elif file_mime_type in ["image/jpeg", "image/png"] or file_path.endswith(('.jpg', '.jpeg', '.png')):
            suffix = ".jpg" if file_path.endswith(('.jpg', '.jpeg')) else ".png"
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_img:
                tmp_img.write(file_content)
                tmp_img_path = tmp_img.name
            page_content = image_to_text(tmp_img_path)
            content_chunks = chunk_text(page_content.replace('\n', ' '), max_tokens=200, overlap=20)
            return {
                "content_chunks": content_chunks,
                "modified_time": modified_time,
                "file_type": "image"
            }

        # Audio files
        elif file_mime_type in ["audio/x-wav", "audio/mpeg"] or file_path.endswith(('.wav', '.mp3')):
            suffix = ".wav" if file_path.endswith('.wav') else ".mp3"
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_audio:
                tmp_audio.write(file_content)
                tmp_audio_path = tmp_audio.name
            page_content = audio_to_text(tmp_audio_path)
            content_chunks = chunk_text(page_content.replace('\n', ' '), max_tokens=200, overlap=20)
            return {
                "content_chunks": content_chunks,
                "modified_time": modified_time,
                "file_type": "audio"
            }

        else:
            logger.warning("Unsupported file type: %s", file_mime_type)
            return None

    except Exception as e:
        logger.error(f"Error loading local file {file_path}: {e}")
        return None
