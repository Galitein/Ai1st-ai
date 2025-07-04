import os
import json
import logging
from urllib.parse import urlencode
from datetime import datetime, timezone
from src.database.sql import AsyncMySQLDatabase
from src.app.services.trello_service.trello_utils import get_trello_api_key, get_trello_service_id
from dotenv import load_dotenv
load_dotenv(override=True)

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

async def save_token(ait_id: str, auth_data: dict):
    """
    Save or update a user's Trello token in MySQL user_services table.
    Expects `auth_data` as a dictionary (will be stored as JSON).
    """
    try:
        TRELLO_SERVICE_ID = await get_trello_service_id()
        await db.create_pool()

        existing_service = await db.select_one(
            table="user_services",
            where="custom_gpt_id = %s AND service_id = %s",
            params=(ait_id, TRELLO_SERVICE_ID)
        )

        auth_secret_json = json.dumps(auth_data)
        timestamp = datetime.now(timezone.utc)

        if existing_service:
            success = await db.update(
                table="user_services",
                data={
                    "auth_secret": auth_secret_json,
                    "updated_at": timestamp,
                    "deleted_at": None  # ensure we "revive" soft-deleted tokens
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
                    "auth_secret": auth_secret_json,
                    "created_at": timestamp,
                    "updated_at": timestamp
                }
            )

        logging.info(f"Trello token {'updated' if existing_service else 'inserted'} for user {ait_id}")
        return success

    except Exception as e:
        logging.error(f"Error saving Trello token: {e}")
        return False

    finally:
        await db.close_pool()

async def get_token(ait_id: str) -> dict | None:
    """
    Retrieve a user's Trello token (auth data as dict) from MySQL.
    """
    try:
        TRELLO_SERVICE_ID = await get_trello_service_id()
        await db.create_pool()

        service_record = await db.select_one(
            table="user_services",
            columns="auth_secret",
            where="custom_gpt_id = %s AND service_id = %s AND deleted_at IS NULL",
            params=(ait_id, TRELLO_SERVICE_ID)
        )

        if service_record:
            return json.loads(service_record['auth_secret']).get("token")

        logging.info(f"No Trello token found for user {ait_id}")
        return None

    except Exception as e:
        logging.error(f"Error retrieving Trello token: {e}")
        return None

    finally:
        await db.close_pool()

async def delete_token(ait_id: str) -> bool:
    """
    Soft delete a user's Trello token in the DB.
    """
    try:
        TRELLO_SERVICE_ID = await get_trello_service_id()
        await db.create_pool()

        success = await db.update(
            table="user_services",
            data={"deleted_at": datetime.now(timezone.utc)},
            where="custom_gpt_id = %s AND service_id = %s AND deleted_at IS NULL",
            where_params=(ait_id, TRELLO_SERVICE_ID)
        )

        if success:
            logging.info(f"Trello token deleted for user {ait_id}")
        else:
            logging.info(f"No active Trello token found to delete for user {ait_id}")

        return success

    except Exception as e:
        logging.error(f"Error deleting Trello token: {e}")
        return False

    finally:
        await db.close_pool()

async def is_user_authenticated(ait_id: str) -> bool:
    """
    Check if a user has an active Trello token.
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

        return service_record is not None

    except Exception as e:
        logging.error(f"Error checking authentication for user {ait_id}: {e}")
        return False

    finally:
        await db.close_pool()