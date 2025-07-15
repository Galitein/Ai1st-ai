import os
from dotenv import load_dotenv
from datetime import datetime, timezone
from msal import ConfidentialClientApplication
import html2text
import json
from src.database.sql import AsyncMySQLDatabase 
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("msexchange_token_store.log"),
        logging.StreamHandler()
    ]
)

load_dotenv(override=True)

AZURE_CLIENT_ID = os.getenv("AZURE_CLIENT_ID")
AZURE_SECRET_ID = os.getenv("AZURE_SECRET_VALUE")
TENANT_ID = os.getenv("TENANT_ID")
AUTHORITY = f"https://login.microsoftonline.com/common"

# MySQL setup for both token storage and email storage
mysql_db = AsyncMySQLDatabase()

GRAPH_SCOPES = ["Mail.ReadWrite","Calendars.ReadWrite","Contacts.ReadWrite"]

msal_app = ConfidentialClientApplication(
    client_id=AZURE_CLIENT_ID,
    client_credential=AZURE_SECRET_ID,
    authority=AUTHORITY
)

async def get_mse_service_id():
    await mysql_db.create_pool()
    service_id = await mysql_db.select_one(table ="master_service", columns = "id", where= "service_name = 'MSExchange'")
    await mysql_db.close_pool()
    return service_id.get("id")

async def save_token(ait_id, token_data):
    """Save token data to MySQL user_services table"""
    try:
        service_id = await get_mse_service_id()

        await mysql_db.create_pool()
        
        auth_secret_json = json.dumps(token_data)
        current_time = datetime.now(timezone.utc)
        
        existing_record = await mysql_db.select_one(
            table="user_services",
            where="custom_gpt_id = %s AND service_id = %s",
            params=(ait_id, service_id)
        )
        
        if existing_record:
            update_data = {
                "auth_secret": auth_secret_json,
                "updated_at": current_time
            }
            await mysql_db.update(
                table="user_services",
                data=update_data,
                where="custom_gpt_id = %s AND service_id = %s",
                where_params=(ait_id, service_id)
            )
        else:
            # Insert new record
            insert_data = {
                "custom_gpt_id": ait_id,
                "service_id": service_id,  
                "auth_secret": auth_secret_json,
                "created_at": current_time,
                "updated_at": current_time
            }
            await mysql_db.insert(table="user_services", data=insert_data)
            
    except Exception as e:
        logging.error(f"Error saving token: {e}")
    finally:
        await mysql_db.close_pool()

async def get_token(ait_id):
    """Get token data from MySQL user_services table"""
    try:
        service_id = await get_mse_service_id()

        await mysql_db.create_pool()
        
        record = await mysql_db.select_one(
            table="user_services",
            where="custom_gpt_id = %s AND service_id = %s",
            params=(ait_id, service_id)
        )
        
        if record and record.get("auth_secret"):
            # Parse JSON string back to dictionary
            return json.loads(record["auth_secret"])
        return None
        
    except Exception as e:
        logging.error(f"Error getting token: {e}")
        return None
    finally:
        await mysql_db.close_pool()

async def refresh_access_token(ait_id : str):
    logging.info(f"Going to generate new access token for user id : {ait_id}")
    user_token = await get_token(ait_id)

    if not user_token:
        logging.info("No token data found")
        return None

    refresh_token = user_token.get("refresh_token")
    if not refresh_token:
        logging.info("Refresh token not found")
        return None
    
    result = msal_app.acquire_token_by_refresh_token(refresh_token, scopes=GRAPH_SCOPES)

    if "access_token" in result:
        await save_token(ait_id, result)
        logging.info(f"New token generated for user {ait_id}")
        return result["access_token"]

    logging.info(f"Failed to generated user token for user id : {ait_id}")
    return None
