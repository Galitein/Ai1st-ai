import os
from dotenv import load_dotenv
from datetime import datetime, timezone
from msal import ConfidentialClientApplication
from motor.motor_asyncio import AsyncIOMotorClient
import html2text

load_dotenv(override=True)

AZURE_CLIENT_ID = os.getenv("AZURE_CLIENT_ID")
AZURE_SECRET_ID = os.getenv("AZURE_SECRET_VALUE")
TENANT_ID = os.getenv("TENANT_ID")
AUTHORITY = f"https://login.microsoftonline.com/common"
MONGO_URI = os.getenv("MONGO_URI")
mongo_client = AsyncIOMotorClient(MONGO_URI)
db = mongo_client["ai1st_customgpt"]
collection = db["ms_token_data"]
emails_collection = db["email_data"]
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

async def store_emails_in_mongodb(messages, user_id):
    """
    Store emails in MongoDB collection with duplicate prevention.
    Returns tuple of (stored_count, skipped_count)
    """
    stored_count = 0
    skipped_count = 0
    
    for message in messages:
        try:
            # Extract and format email data
            email_document = {
                "user_id": user_id,
                "email_id": message.get("id", ""),
                "flag": message.get("flag", {}),
                "subject": message.get("subject", ""),
                "sender_name": message.get("sender", {}).get("emailAddress", {}).get("name", ""),
                "sender_address": message.get("sender", {}).get("emailAddress", {}).get("address", ""),
                "inference_classification": message.get("inferenceClassification", ""),
                "categories": message.get("categories", []),
                "content": html2text.html2text(message.get("body", {}).get("content", "")).replace("\n", "    "),
                "has_attachments": message.get("hasAttachments", False),
                "is_read": message.get("isRead", False),
                "received_datetime": message.get("receivedDateTime", ""),
                "sync_timestamp": datetime.now(timezone.utc)
            }
            
            # Parse and convert datetime fields
            datetime_fields = ["createdDateTime", "lastModifiedDateTime", "sentDateTime"]
            for field in datetime_fields:
                if field in message and message[field]:
                    try:
                        # Parse the datetime string and convert to UTC datetime object
                        dt_str = message[field]
                        if dt_str.endswith('Z'):
                            dt_obj = datetime.strptime(dt_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                        else:
                            dt_obj = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
                        
                        # Map field names to more readable names
                        field_mapping = {
                            "createdDateTime": "created_datetime",
                            "lastModifiedDateTime": "last_modified_datetime",
                            "sentDateTime": "sent_datetime"
                        }
                        
                        email_document[field_mapping.get(field, field)] = dt_obj
                    except (ValueError, TypeError) as e:
                        print(f"Error parsing datetime field {field}: {e}")
                        email_document[field_mapping.get(field, field)] = None
            
            # Try to insert the document
            try:
                # Use upsert to prevent duplicates based on email_id and user_id
                result = await emails_collection.update_one(
                    {"email_id": email_document["email_id"], "user_id": user_id},
                    {"$set": email_document},
                    upsert=True
                )
                
                if result.upserted_id:
                    stored_count += 1
                    print(f"Stored new email: {email_document['subject'][:50]}...")
                else:
                    skipped_count += 1
                    print(f"Skipped duplicate email: {email_document['subject'][:50]}...")
                    
            except Exception as db_error:
                print(f"Database error storing email {email_document.get('email_id', 'unknown')}: {db_error}")
                skipped_count += 1
                
        except Exception as e:
            print(f"Error processing email: {e}")
            skipped_count += 1
            continue
    
    return stored_count, skipped_count        