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

async def check_email_duplicate(ait_id, subject, sent_datetime, sender_address):
    """
    Check if an email already exists based on subject, sent datetime, and sender address
    Returns True if duplicate exists, False otherwise
    """
    try:
        existing_email = await mysql_db.select_one(
            table="user_email_content",
            columns="id",
            where="ait_id = %s AND subject = %s AND sent_datetime = %s AND sender_address = %s",
            params=(ait_id, subject, sent_datetime, sender_address)
        )
        
        return existing_email is not None
        
    except Exception as e:
        logging.error(f"Error checking duplicate: {e}")
        return False


async def store_emails_in_mysql(messages, ait_id):
    """
    Store emails in MySQL user_email_content table with enhanced duplicate prevention.
    Returns tuple of (stored_count, skipped_count, new_emails_for_embedding)
    
    This function handles both:
    1. Fresh emails from Microsoft Graph API (original message structure)
    2. Enhanced duplicate checking based on subject, sent_datetime, and sender_address
    3. Returns only NEW emails that need vector embedding processing
    """
    stored_count = 0
    skipped_count = 0
    new_emails_for_embedding = []  # Track emails that are actually new
    
    try:
        await mysql_db.create_pool()
        
        for message in messages:
            try:
                
                # Parse datetime fields from API format
                def parse_api_datetime(dt_str):
                    if not dt_str:
                        return None
                    try:
                        if dt_str.endswith('Z'):
                            return datetime.strptime(dt_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                        else:
                            return datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
                    except (ValueError, TypeError) as e:
                        logging.error(f"Error parsing datetime {dt_str}: {e}")
                        return None
                
                flag_status = 'notFlagged'  # Default value
                flag_data = message.get("flag", {})
                if flag_data and flag_data.get("flagStatus") == "flagged":
                    flag_status = 'flagged'
                
                categories = message.get("categories", [])
                categories_json = json.dumps(categories) if categories else None
                
                content = ""
                body_data = message.get("body", {})
                if body_data and body_data.get("content"):
                    content = html2text.html2text(body_data.get("content", "")).replace("\n", "    ")
                
                sender_data = message.get("sender", {})
                sender_email_data = sender_data.get("emailAddress", {}) if sender_data else {}
                sender_name = sender_email_data.get("name", "") if sender_email_data else ""
                sender_address = sender_email_data.get("address", "") if sender_email_data else ""
                
                # Parse required fields for duplicate check
                subject = message.get("subject", "")
                sent_datetime = parse_api_datetime(message.get("sentDateTime"))
                
                # Enhanced duplicate check based on subject, sent_datetime, and sender_address
                if await check_email_duplicate(ait_id, subject, sent_datetime, sender_address):
                    logging.info(f"Duplicate email found - Subject: '{subject[:50]}...', Sender: {sender_address}, Sent: {sent_datetime}")
                    skipped_count += 1
                    continue
                
                email_data = {
                    "email_id": message.get("id", ""),
                    "ait_id": ait_id,
                    "categories": categories_json,
                    "content": content,
                    "created_datetime": parse_api_datetime(message.get("createdDateTime")),
                    "flag_status": flag_status,
                    "has_attachments": message.get("hasAttachments", False),
                    "inference_classification": message.get("inferenceClassification", ""),
                    "is_read": message.get("isRead", False),
                    "last_modified_datetime": parse_api_datetime(message.get("lastModifiedDateTime")),
                    "received_datetime": parse_api_datetime(message.get("receivedDateTime")),
                    "sender_address": sender_address,
                    "sender_name": sender_name,
                    "sent_datetime": sent_datetime,
                    "subject": subject,
                    "sync_timestamp": datetime.now(timezone.utc)
                }
                
                # Check if email already exists by email_id (fallback check)
                existing_email = await mysql_db.select_one(
                    table="user_email_content",
                    columns="id",
                    where="email_id = %s AND ait_id = %s",
                    params=(email_data["email_id"], ait_id)
                )
                
                email_is_new = False
                
                if existing_email:
                    # Update existing record
                    update_data = {k: v for k, v in email_data.items() if k not in ["email_id", "ait_id"]}
                    success = await mysql_db.update(
                        table="user_email_content",
                        data=update_data,
                        where="email_id = %s AND ait_id = %s",
                        where_params=(email_data["email_id"], ait_id)
                    )
                    
                    if success:
                        logging.info(f"Updated existing email: {email_data['subject'][:50]}...")
                        stored_count += 1
                        # Don't add to embedding queue since it's an update
                    else:
                        logging.info(f"Failed to update email: {email_data['subject'][:50]}...")
                        skipped_count += 1
                else:
                    # Insert new record
                    success = await mysql_db.insert(
                        table="user_email_content",
                        data=email_data
                    )
                    
                    if success:
                        logging.info(f"Stored new email: {email_data['subject'][:50]}...")
                        stored_count += 1
                        email_is_new = True
                    else:
                        logging.info(f"Failed to store email: {email_data['subject'][:50]}...")
                        skipped_count += 1
                
                # Only add to embedding queue if email is genuinely new
                if email_is_new:
                    new_emails_for_embedding.append(message)
                    
            except Exception as e:
                logging.error(f"Error processing email: {e}")
                skipped_count += 1
                continue
                
    except Exception as e:
        logging.error(f"Database connection error: {e}")
        return 0, len(messages), []
    finally:
        await mysql_db.close_pool()
    
    return stored_count, skipped_count, new_emails_for_embedding

