import os
from dotenv import load_dotenv
from datetime import datetime, timezone
from msal import ConfidentialClientApplication
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv(override=True)

AZURE_CLIENT_ID = os.getenv("AZURE_CLIENT_ID")
AZURE_SECRET_ID = os.getenv("AZURE_SECRET_VALUE")
TENANT_ID = os.getenv("TENANT_ID")
AUTHORITY = f"https://login.microsoftonline.com/common"
MONGO_URI = os.getenv("MONGO_URI")
mongo_client = AsyncIOMotorClient(MONGO_URI)
db = mongo_client["ai1st_customgpt"]
collection = db["token_data"]
GRAPH_SCOPES = ["Mail.ReadWrite","Calendars.ReadWrite","Contacts.ReadWrite"]

msal_app = ConfidentialClientApplication(
    client_id=AZURE_CLIENT_ID,
    client_credential=AZURE_SECRET_ID,
    authority=AUTHORITY
)

async def save_token(user_id, token_data):

    await collection.update_one({"user_id": user_id},
                                {"$set":{"user_token":token_data,
                                         "updated_at": datetime.now(timezone.utc)},
                                "$setOnInsert":{"created_at": datetime.now(timezone.utc)}
                                        },
                                upsert=True)

async def get_token(user_id):
    doc = await collection.find_one({"user_id":user_id})
    return doc["user_token"] if doc else None

async def refresh_access_token(user_id : str):
    print(f"Going to generate new access token for user id : {user_id}")
    user_token = await get_token(user_id)

    if not user_token:
        print("No token data found")
        return None

    refresh_token = user_token.get("refresh_token")
    if not refresh_token:
        print("Refresh token not found")
        return None
    
    result = msal_app.acquire_token_by_refresh_token(refresh_token, scopes=GRAPH_SCOPES)

    if "access_token" in result:
        await save_token(user_id, result)
        print(f"New token generated for user {user_id}")
        return result["access_token"]

    print(f"Failed to generated user token for user id : {user_id}")
    return None
