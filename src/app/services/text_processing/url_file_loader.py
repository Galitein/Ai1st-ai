import json
import logging
import re
from langchain_core.documents import Document
from src.app.utils.helpers import load_content_url_file


async def load_url_documents(file_url, ait_id, document_collection, logger=None):
    """
    Loads and chunks documents from Google Drive.

    Args:
        file_names (list): List of file names to load.
        ait_id (str): Unique identifier for the AIT and Qdrant collection name.
        logger: Logger instance (optional).
        document_collection (str): Qdrant sub_collection name.

    Returns:
        dict: A dictionary with status and either documents or an error message.
    """

    documents = []
    try:
        file_name = file_url.split('/')[-1]
        content_response = load_content_url_file(file_url=file_url, logger=logger)
        if not content_response.get("status"):
            return {"status": False, "message": content_response.get("message", "Unkown Error")}
        content_chunks = content_response.get('content_chunks')
        file_type = content_response.get('file_type')
        logger.info(f"Loaded {len(content_response.get('content_chunks'))} chunks from file: {file_name} of Content type: {file_type}")
        if file_type in ("text", "audio", "image") and isinstance(content_chunks, list):
            for idx, chunk in enumerate(content_chunks):
                documents.append(
                    Document(
                        page_content=chunk.strip(),
                        metadata={
                            "ait_id": ait_id,
                            "type": document_collection,
                            "file_name": file_name,
                            "chunk_index": idx,
                            "modified_time": content_response.get('modified_time'),
                            "source_id": f"{document_collection}_{file_name}_{idx}"
                        }
                    )
                )
    except Exception as e:
        logger.error(f"Error processing file {file_name}: {e}")
        return {"status": False, "error": f"Error processing file {file_name}: {e}"}

    logger.info(f"Total paragraphs loaded: {len(documents)} for file name {file_name}")
    return {"status": True, "documents": documents}
