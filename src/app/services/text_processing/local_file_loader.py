import os
import mimetypes
from langchain_core.documents import Document
from src.app.utils.helpers import chunk_text, load_content_local_file

async def load_local_documents(file_names, ait_id, document_collection, logger=None):
    """
    Loads and chunks documents from the local filesystem.
    """
    documents = []
    for file_name in file_names:
        try:
            print(file_name)
            file_path = os.path.join("temp", ait_id, file_name)
            content_response = load_content_local_file(file_path, logger)
            content_chunks = content_response.get('content_chunks')
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
            if logger:
                logger.error(f"Error loading local file {file_name}: {e}")
            continue
    return documents

