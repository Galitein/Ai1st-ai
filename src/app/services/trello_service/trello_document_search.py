import os
import sys
sys.path.append(".")
import logging
from dotenv import load_dotenv
import httpx

load_dotenv(override=True)

# Fix import paths as needed
from src.app.services.trello_service.trello_query_extractor import trello_query_entities

TRELLO_API_KEY = os.getenv("TRELLO_API_KEY")
TRELLO_TOKEN = os.getenv("TRELLO_TOKEN")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def search_trello_documents(query: str, ait_id: str, limit: int = 10, similarity_threshold: float = 0.3) -> dict:
    """
    Search Trello documents based on the provided query.

    Args:
        query (str): The search query.
        ait_id (str): The AI tool ID for the search context.
        limit (int): The maximum number of results to return.
        similarity_threshold (float): The minimum similarity score for results.

    Returns:
        dict: A dictionary containing the search results.
    """
    try:
        logger.info(f"Starting Trello document search for query: {query}")
        log_entity_string = await trello_query_entities(query=query)
        logger.info(f"Entity string from trello_query_entities: {log_entity_string}")

        trello_log_documents = []
        trello_card_documents = []
        trello_member_documents = []
        trello_user_documents = []

        async with httpx.AsyncClient() as client:
            # Search trello_log
            try:
                trello_log_response = await client.post(
                    "http://192.168.1.207:8081/search",
                    json={
                        "ait_id": ait_id,
                        "query": log_entity_string,
                        "document_collection": "trello_log",
                        "limit": 30,
                        "similarity_threshold": 0.4
                    }
                )
                if trello_log_response.status_code == 200:
                    trello_log_documents = trello_log_response.json().get("results", [])
                    logger.info(f"trello_log search returned {len(trello_log_documents)} results")
                else:
                    logger.warning(f"trello_log search failed: {trello_log_response.text}")
            except Exception as e:
                logger.error(f"Error searching trello_log: {e}")

            # Search trello_card
            try:
                trello_card_response = await client.post(
                    "http://localhost:8081/search",
                    json={
                        "ait_id": ait_id,
                        "query": query,
                        "document_collection": "trello_card",
                        "limit": 20,
                        "similarity_threshold": 0.2
                    }
                )
                if trello_card_response.status_code == 200:
                    trello_card_documents = trello_card_response.json().get("results", [])
                    logger.info(f"trello_card search returned {len(trello_card_documents)} results")
                else:
                    logger.warning(f"trello_card search failed: {trello_card_response.text}")
            except Exception as e:
                logger.error(f"Error searching trello_card: {e}")

            # Search trello_member
            try:
                trello_member_response = await client.post(
                    "http://localhost:8081/search",
                    json={
                        "ait_id": ait_id,
                        "query": query,
                        "document_collection": "trello_member",
                        "limit": 10,
                        "similarity_threshold": 0.2
                    }
                )
                if trello_member_response.status_code == 200:
                    trello_member_documents = trello_member_response.json().get("results", [])
                    logger.info(f"trello_member search returned {len(trello_member_documents)} results")
                else:
                    logger.warning(f"trello_member search failed: {trello_member_response.text}")
            except Exception as e:
                logger.error(f"Error searching trello_member: {e}")

            # Get Trello user info
            try:
                trello_user_response = await client.get(
                    f"https://trello.com/1/members/me?token={TRELLO_TOKEN}&key={TRELLO_API_KEY}"
                )
                if trello_user_response.status_code == 200:
                    user_json = trello_user_response.json()
                    trello_user_documents = [{
                        "username": user_json.get("username", ""),
                        "fullName": user_json.get("fullName", ""),
                        "id": user_json.get("id", ""),
                        "url": user_json.get("url", "")
                    }]
                    logger.info("Fetched Trello user info successfully")
                else:
                    logger.warning(f"Trello user fetch failed: {trello_user_response.text}")
                    trello_user_documents = []
            except Exception as e:
                logger.error(f"Error fetching Trello user: {e}")
                trello_user_documents = []

        trello_documents = {
            "trello_log": trello_log_documents,
            "trello_card": trello_card_documents,
            "trello_member": trello_member_documents,
            "trello_user": trello_user_documents
        }

        logger.info("Trello document search completed successfully")
        return trello_documents
    except Exception as e:
        logger.error(f"Error during Trello document search: {e}")
        return {"error": str(e)}


# if __name__ == "__main__":
#     import asyncio
#     # Provide test values for query and ait_id
#     result = asyncio.run(search_trello_documents("What task assigned to kaushal is doing?", "string1"))
#     print(result)