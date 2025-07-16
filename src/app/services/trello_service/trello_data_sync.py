import os
from dotenv import load_dotenv
import logging
import httpx
from src.app.services.trello_service.trello_data_loader import load_trello_documents
from src.app.services.text_processing import create_embeddings

load_dotenv(override=True)

BACKEND_API_URL = os.getenv("BACKEND_API_URL")

async def trello_data_sync(ait_id: str) -> dict:
    """
    Sync Trello documents for the authenticated user.
    """
    try:
        document_response = await load_trello_documents(ait_id=ait_id)
        if not document_response.get("status"):
            logging.error(f"Document loading failed: {document_response.get('message')}")
            return {
                "status": False,
                "message": document_response.get("message"),
                "index_result": None
            }
        documents = document_response.get("data", [])
        logging.info(f"Loaded {len(documents)} Trello documents for indexing.")
        
        if not documents:
            logging.info("No documents found to index.")
            return {
                "status": True,
                "message": "No documents found to index.",
                "index_result": None
            }
        # Convert Document objects to dicts
        document_dicts = [
                {"page_content": doc.page_content, "metadata": doc.metadata}
                for doc in documents
            ] if isinstance(documents, list) else []
        logging.info(f"Preparing to index {len(document_dicts)} documents for AIT ID: {ait_id}")
        logging.info(f"Document dicts: {document_dicts}")  # Log first two for debugging
        async with httpx.AsyncClient() as client:
            try:
                create_embedding_response = await client.post(
                    f"{BACKEND_API_URL}/create_embeddings",
                    json={
                        "ait_id": ait_id,
                        "documents": document_dicts,
                    }
                )
                response_data = create_embedding_response.json()
                if not response_data.get('status', False):
                    logging.error(f"Indexing failed {response_data.get('message', 'Unknown error')}")
                    return {
                        "status": False,
                        "message": f"Indexing failed: {response_data.get('message', 'Unknown error')}",
                        "index_result": None
                    }
                logging.info(f"Indexing response: {response_data}")
                trello_data = response_data.get("index_result")
                logging.info(f"Indexed results: {trello_data.get('index_result')} for ait_id: {ait_id}")
                return {
                    "status": True,
                    "message": "Documents indexed successfully.",
                    "index_result": trello_data.get("index_result")
                }
                    
            except Exception as e:
                logging.error(f"Exception during indexing: {e}")
                return {
                    "status": False,
                    "message": f"Exception during indexing: {str(e)}",
                    "index_result": None
                }
    except Exception as e:
        logging.error(f"Exception in sync: {e}")
        return {
            "status": False,
            "message": f"Exception in sync: {str(e)}",
            "index_result": None
        }