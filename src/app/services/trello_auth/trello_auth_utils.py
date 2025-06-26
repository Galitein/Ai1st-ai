import os
from urllib.parse import urlencode
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URI = os.getenv("MONGO_URI")
TRELLO_AUTH_BASE = "https://trello.com/1/authorize"
TRELLO_API_KEY = os.getenv("TRELLO_API_KEY") 
TRELLO_REDIRECT_URI = os.getenv("TRELLO_REDIRECT_URI")

mongo_client = AsyncIOMotorClient(MONGO_URI)
db = mongo_client["ai1st_customgpt"]
collection = db["trello_token_store"]

def generate_auth_url(user_id: str):
    redirect_with_user = f"{TRELLO_REDIRECT_URI}?user_id={user_id}"
    params = {
        "expiration": "never",
        "name": "TrelloAgentAccess",
        "scope": "read,write",
        "response_type": "token",
        "key": TRELLO_API_KEY,
        "return_url": redirect_with_user,
    }
    return f"{TRELLO_AUTH_BASE}?{urlencode(params)}"

async def save_token(user_id, token_data):

    await collection.update_one({"user_id": user_id},
                                {"$set":{"user_token":token_data,
                                         "updated_at": datetime.now(timezone.utc)},
                                "$setOnInsert":{"created_at": datetime.now(timezone.utc)}
                                        },
                                upsert=True)    
    return