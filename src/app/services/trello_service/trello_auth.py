import os
import logging
from urllib.parse import urlencode
from datetime import datetime, timezone
from src.database.sql import AsyncMySQLDatabase
from src.app.services.trello_service.trello_utils import get_trello_api_key, get_trello_service_id

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("trello_auth.log"),
        logging.StreamHandler()
    ]
)

TRELLO_AUTH_BASE = "https://trello.com/1/authorize"
TRELLO_REDIRECT_URI = os.getenv("TRELLO_REDIRECT_URI")
db = AsyncMySQLDatabase()

async def generate_auth_url(ait_id: str) -> str:
    """
    Generate Trello OAuth authorization URL for a given user.
    """
    TRELLO_API_KEY = await get_trello_api_key()
    redirect_with_user = f"{TRELLO_REDIRECT_URI}?ait_id={ait_id}"
    params = {
        "expiration": "never",
        "name": "TrelloAgentAccess",
        "scope": "read,write",
        "response_type": "token",
        "key": TRELLO_API_KEY,
        "return_url": redirect_with_user,
    }
    return f"{TRELLO_AUTH_BASE}?{urlencode(params)}"

async def save_token(ait_id: str, token: str):
    """
    Save or update a user's Trello token in MySQL user_services table.
    """
    try:
        TRELLO_SERVICE_ID = await get_trello_service_id()
        await db.create_pool()
        
        existing_service = await db.select_one(
            table="user_services",
            where="custom_gpt_id = %s AND service_id = %s",
            params=(ait_id, TRELLO_SERVICE_ID)
        )
        
        if existing_service:
            success = await db.update(
                table="user_services",
                data={
                    "auth_secret": token,
                    "updated_at": datetime.now(timezone.utc)
                },
                where="custom_gpt_id = %s AND service_id = %s",
                where_params=(ait_id, TRELLO_SERVICE_ID)
            )
        else:
            success = await db.insert(
                table="user_services",
                data={
                    "custom_gpt_id": ait_id,
                    "service_id": TRELLO_SERVICE_ID,
                    "auth_secret": token,
                    "created_at": datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc)
                }
            )
        
        await db.close_pool()
        
        if success:
            logging.info(f"Trello token saved successfully for user {ait_id}")
        else:
            logging.info(f"Failed to save Trello token for user {ait_id}")
            
        return success
        
    except Exception as e:
        logging.error(f"Error saving Trello token: {e}")
        await db.close_pool()
        return False

async def get_token(ait_id: str) -> str:
    """
    Retrieve a user's Trello token from MySQL.
    """
    try:
        TRELLO_SERVICE_ID = await get_trello_service_id()
        await db.create_pool()
        
        service_record = await db.select_one(
            table="user_services",
            columns="auth_secret",
            where="custom_gpt_id = %s AND service_id = %s",
            params=(ait_id, TRELLO_SERVICE_ID)
        )
        
        await db.close_pool()
        
        if service_record:
            return service_record['auth_secret']
        else:
            logging.info(f"No Trello token found for user {ait_id}")
            return None
            
    except Exception as e:
        logging.error(f"Error retrieving Trello token: {e}")
        await db.close_pool()
        return None

async def delete_token(ait_id: str) -> bool:
    """
    Delete a user's Trello token from MySQL (soft delete).
    """
    try:
        TRELLO_SERVICE_ID = await get_trello_service_id()
        await db.create_pool()
        
        success = await db.update(
            table="user_services",
            data={
                "deleted_at": datetime.now(timezone.utc)
            },
            where="custom_gpt_id = %s AND service_id = %s AND deleted_at IS NULL",
            where_params=(ait_id, TRELLO_SERVICE_ID)
        )
        
        await db.close_pool()
        
        if success:
            logging.info(f"Trello token deleted successfully for user {ait_id}")
        else:
            logging.info(f"No active Trello token found to delete for user {ait_id}")
            
        return success
        
    except Exception as e:
        logging.error(f"Error deleting Trello token: {e}")
        await db.close_pool()
        return False

async def is_user_authenticated(ait_id: str) -> bool:
    """
    Check if user has a valid Trello token.
    """
    try:
        TRELLO_SERVICE_ID = await get_trello_service_id()
        await db.create_pool()
        
        service_record = await db.select_one(
            table="user_services",
            columns="id",
            where="custom_gpt_id = %s AND service_id = %s AND deleted_at IS NULL",
            params=(ait_id, TRELLO_SERVICE_ID)
        )
        
        await db.close_pool()
        
        return service_record is not None
        
    except Exception as e:
        logging.error(f"Error checking user authentication: {e}")