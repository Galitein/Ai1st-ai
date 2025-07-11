import os
from dotenv import load_dotenv
import logging
import httpx
from src.app.services.trello_service.trello_data_loader import load_trello_documents

load_dotenv(override=True)

BACKEND_API_URL = os.getenv("BACKEND_API_URL")

async def trello_data_sync(ait_id: str) -> dict:
    """
    Sync Trello documents for the authenticated user.
    
    Args:
        ait_id (str): Unique identifier for the AIT and Qdrant collection name.
    
    Returns:
        dict: Status and data of the Trello documents.
    """
    try:
        document_response = await load_trello_documents(ait_id=ait_id)
        if not document_response.get("status"):
            logging.error(document_response.get("message"))
            return {
                "status": False,
                "message": document_response.get("message"),
                "index_result": None
            }
        documents = document_response.get("data", [])
        logging.info(f"Loaded {len(documents)} Trello documents for indexing.")
        if not documents:
            return {
                "status": True,
                "message": "No documents found to index.",
                "index_result": None
            }
        async with httpx.AsyncClient() as client:
            try:
                create_embedding_response = await client.post(
                    f"{BACKEND_API_URL}/create_embeddings",
                    json={
                        "ait_id": ait_id,
                        "documents": documents,
                    }
                )
                if create_embedding_response.status_code == 200:
                    trello_data = create_embedding_response.json()
                    logging.info(f"Trello data sync indexed results {trello_data.get('index_result')} successfully for {ait_id}.")
                    return {
                        "status": True,
                        "message": "Documents indexed successfully.",
                        "index_result": trello_data.get("index_result")
                    }
                else:
                    logging.warning(f"trello_log search failed: {create_embedding_response.text}")
                    return {
                        "status": False,
                        "message": f"Indexing failed: {create_embedding_response.text}",
                        "index_result": None
                    }
            except Exception as e:
                logging.error(f"Error searching trello_log: {e}")
                return {
                    "status": False,
                    "message": f"Exception during indexing: {str(e)}",
                    "index_result": None
                }
    except Exception as e:
        logging.error(f"Error in trello_data_sync: {e}")
        return {
            "status": False,
            "message": f"Exception in sync: {str(e)}",
            "index_result": None
        }