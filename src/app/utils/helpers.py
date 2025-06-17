def chunk_text(text, max_len=500, overlap=50):
    """
    Splits text into overlapping chunks.

    Args:
        text (str): The input text to chunk.
        max_len (int): Maximum length of each chunk.
        overlap (int): Number of overlapping characters between chunks.

    Returns:
        list: List of text chunks.
    """
    chunks = []
    start = 0
    while start < len(text):
        end = start + max_len
        chunks.append(text[start:end])
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
    import io
    from googleapiclient.http import MediaIoBaseDownload
    from datetime import datetime

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
        page_content = file_content.read().decode('utf-8')
        return page_content, modified_time

    except Exception as e:
        logger.error(f"Error downloading file {file_name}: {e}")
        return None, None
