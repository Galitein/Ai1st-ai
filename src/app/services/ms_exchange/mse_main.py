import os
import json
import re
import time
import asyncio
import requests
import html2text
from typing import Optional, List, Dict
import logging
from dotenv import load_dotenv
from urllib.parse import quote
from datetime import datetime, timedelta, timezone
from fastapi import Query
from fastapi.responses import JSONResponse
from src.app.services.ms_exchange.mse_token_store import get_token, refresh_access_token
from src.database.sql_record_manager import sql_record_manager
from src.app.services.text_processing.create_embeddings import process_and_build_index

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("msexchange_mse_main.log"),
        logging.StreamHandler()
    ]
)

MAX_TOP = 100
MAX_SEARCH_LENGTH = 255
MAX_DATE_RANGE_DAYS = 3
DEFAULT_DAYS_RANGE = 2

BATCH_SIZE = 1000
MAX_EMAILS_PER_REQUEST = 999
DELAY_BETWEEN_BATCHES = 0.1
MAX_CONCURRENT_REQUESTS = 4
SYNC_ALL_CHUNK_SIZE = 100

# Helper functions
def validate_date_format(date_str: str) -> bool:
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        return True
    except ValueError:
        return False

def validate_email_format(email: str) -> bool:
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(email_pattern, email) is not None

def validate_search_query(search: str) -> bool:
    return len(search.strip()) <= MAX_SEARCH_LENGTH if search else True

def validate_email_type(email_type: str) -> bool:
    return email_type in ["received", "sent", "both"]

def get_default_date_range(days: int = DEFAULT_DAYS_RANGE) -> tuple:
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)
    return start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")

def build_headers(access_token: str) -> dict:
    return {
        "Authorization": f"Bearer {access_token}",
        "Prefer": 'outlook.timezone="UTC"',
        "Content-Type": "application/json"
    }

def sanitize_message(message: dict, email_type: str = "received") -> dict:
    """
    Sanitize message data and add email type information
    """
    # For sent emails, we need to handle the 'to' field instead of 'from'
    if email_type == "sent":
        recipient_info = message.get("toRecipients", [])
        primary_recipient = recipient_info[0] if recipient_info else {}
        contact_info = primary_recipient.get("emailAddress", {}) if primary_recipient else {}
    else:
        contact_info = message.get("from", {})
    
    return {
        "id": message.get("id", ""),
        "subject": message.get("subject", ""),
        "from": message.get("from", {}) if email_type == "received" else message.get("sender", {}),
        "to": message.get("toRecipients", []) if email_type == "sent" else [],
        "receivedDateTime": message.get("receivedDateTime", ""),
        "sentDateTime": message.get("sentDateTime", ""),
        "content": html2text.html2text(message.get("body", {}).get("content", "")).replace("\n", "    "),
        "hasAttachments": message.get("hasAttachments", False),
        "emailType": email_type,  # Add email type for identification
        "isRead": message.get("isRead", False)
    }

def apply_client_side_filters(messages: list, filters: dict, email_type: str = "received") -> list:
    filtered_messages = []
    for message in messages:
        if filters.get('start_date') or filters.get('end_date'):
            # Use sentDateTime for sent emails, receivedDateTime for received emails
            datetime_field = "sentDateTime" if email_type == "sent" else "receivedDateTime"
            received_dt_str = message.get(datetime_field, "")
            if received_dt_str:
                try:
                    received_dt = datetime.fromisoformat(received_dt_str.replace('Z', '+00:00'))
                    received_date = received_dt.date()
                    
                    if filters.get('start_date'):
                        start_dt = datetime.strptime(filters['start_date'], "%Y-%m-%d").date()
                        if received_date < start_dt:
                            continue
                    
                    if filters.get('end_date'):
                        end_dt = datetime.strptime(filters['end_date'], "%Y-%m-%d").date()
                        if received_date > end_dt:
                            continue
                except (ValueError, TypeError):
                    continue
        
        if filters.get('unread_only') and message.get("isRead", True):
            continue
            
        if filters.get('from_email'):
            if email_type == "sent":
                # For sent emails, check if the email was sent TO the specified address
                to_recipients = message.get("toRecipients", [])
                found_recipient = False
                for recipient in to_recipients:
                    if recipient.get("emailAddress", {}).get("address", "").lower() == filters['from_email'].lower():
                        found_recipient = True
                        break
                if not found_recipient:
                    continue
            else:
                # For received emails, check the from field
                msg_from = message.get("from", {}).get("emailAddress", {}).get("address", "")
                if msg_from.lower() != filters['from_email'].lower():
                    continue
                
        if filters.get('search'):
            searchable_text = f"{message.get('subject', '')} {message.get('bodyPreview', '')}"
            if filters['search'].lower() not in searchable_text.lower():
                continue
                
        filtered_messages.append(message)
        
        if filters.get('top') and len(filtered_messages) >= filters['top']:
            break
            
    return filtered_messages

# Core functions
async def validate_and_prepare_filters(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    from_email: Optional[str] = None,
    unread_only: Optional[bool] = False,
    search: Optional[str] = None,
    top: Optional[int] = Query(10, ge=1, le=MAX_TOP),
    orderby: Optional[str] = "receivedDateTime desc",
    email_type: Optional[str] = "both"
) -> tuple:
    # Validate inputs
    if start_date and not validate_date_format(start_date):
        return None, JSONResponse({"error": "Invalid start_date format. Use YYYY-MM-DD."}, status_code=400)
    
    if end_date and not validate_date_format(end_date):
        return None, JSONResponse({"error": "Invalid end_date format. Use YYYY-MM-DD."}, status_code=400)
    
    if from_email and not validate_email_format(from_email):
        return None, JSONResponse({"error": "Invalid email format."}, status_code=400)
    
    if search and not validate_search_query(search):
        return None, JSONResponse({"error": "Search query too long (max 255 characters)."}, status_code=400)
    
    if email_type and not validate_email_type(email_type):
        return None, JSONResponse({"error": "Invalid email_type. Must be 'received', 'sent', or 'both'."}, status_code=400)
    
    # Set default date range if no filters provided
    filters_provided = any([start_date, end_date, from_email, unread_only, search])
    if not filters_provided:
        start_date, end_date = get_default_date_range()
    
    # Validate date range
    if start_date and end_date:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        if start_dt > end_dt:
            return None, JSONResponse({"error": "start_date cannot be after end_date."}, status_code=400)
        if (end_dt - start_dt).days > MAX_DATE_RANGE_DAYS:
            return None, JSONResponse({"error": f"Date range cannot exceed {MAX_DATE_RANGE_DAYS} days."}, status_code=400)
    
    # Adjust orderby for sent emails
    if email_type == "sent" and orderby == "receivedDateTime desc":
        orderby = "sentDateTime desc"
    
    return {
        'start_date': start_date,
        'end_date': end_date,
        'from_email': from_email,
        'unread_only': unread_only,
        'search': search,
        'top': top,
        'orderby': orderby,
        'email_type': email_type
    }, None

def build_graph_url(filters: dict) -> str:
    email_type = filters.get('email_type', 'received')
    
    # Choose the correct endpoint based on email type
    if email_type == "sent":
        base_endpoint = "https://graph.microsoft.com/v1.0/me/mailFolders/SentItems/messages"
        datetime_field = "sentDateTime"
    else:
        # MODIFICATION: Target the 'Inbox' folder specifically for 'received' emails
        # to prevent fetching items from other folders like 'Sent Items'.
        base_endpoint = "https://graph.microsoft.com/v1.0/me/mailFolders/Inbox/messages"
        datetime_field = "receivedDateTime"
    
    if filters.get('search'):
        search_terms = [filters['search']]
        if filters.get('from_email'):
            if email_type == "sent":
                search_terms.append(f"to:{filters['from_email']}")
            else:
                search_terms.append(f"from:{filters['from_email']}")
        search_query = " ".join(search_terms)
        return f"{base_endpoint}?$search=\"{quote(search_query)}\"&$top={min(filters['top'] * 3, 300)}"
    
    elif filters.get('from_email') and not (filters.get('start_date') or filters.get('end_date') or filters.get('unread_only')):
        if email_type == "sent":
            return f"{base_endpoint}?$search=\"to:{filters['from_email']}\"&$top={filters['top']}"
        else:
            return f"{base_endpoint}?$search=\"from:{filters['from_email']}\"&$top={filters['top']}"
    
    else:
        query_filters = []
        if filters.get('start_date'):
            query_filters.append(f"{datetime_field} ge {filters['start_date']}T00:00:00Z")
        if filters.get('end_date'):
            query_filters.append(f"{datetime_field} le {filters['end_date']}T23:59:59Z")
        if filters.get('unread_only'):
            query_filters.append("isRead eq false")
        if filters.get('from_email'):
            if email_type == "sent":
                query_filters.append(f"toRecipients/any(a:a/emailAddress/address eq '{filters['from_email']}')")
            else:
                query_filters.append(f"from/emailAddress/address eq '{filters['from_email']}'")
        
        if query_filters:
            filter_query = " and ".join(query_filters)
            return f"{base_endpoint}?$filter={quote(filter_query)}&$top={filters['top']}&$orderby={filters['orderby']}"
        else:
            default_filter = f"{datetime_field} ge {(datetime.utcnow() - timedelta(days=DEFAULT_DAYS_RANGE)).strftime('%Y-%m-%d')}T00:00:00Z"
            return f"{base_endpoint}?$filter={quote(default_filter)}&$top={filters['top']}&$orderby={filters['orderby']}"

async def make_graph_request(url: str, headers: dict, ait_id: str):
    max_retries = 3
    for attempt in range(max_retries):
        try:
            logging.info(f"Attempt {attempt + 1} of {max_retries}")
            response = requests.get(url, headers=headers, timeout=30)
            logging.info(f"Response received with status code: {response.status_code}")

            if response.status_code == 200:
                logging.info(f"Successful response: {response.json()}")
                return response, None

            elif response.status_code == 401:
                logging.warning("Received 401 Unauthorized. Attempting token refresh...")
                new_access_token = await refresh_access_token(ait_id)
                headers = build_headers(new_access_token)
                logging.info(f"Refreshed token. New headers: {headers}")
                continue

            elif response.status_code == 403:
                logging.error("Received 403 Forbidden. Insufficient permissions.")
                return None, JSONResponse({"error": "Insufficient permissions to access emails."}, status_code=403)

            elif response.status_code == 429:
                logging.warning("Received 429 Too Many Requests. Retrying after delay...")
                if attempt < max_retries - 1:
                    import time
                    delay = 2 ** attempt
                    logging.info(f"Sleeping for {delay} seconds before retry")
                    time.sleep(delay)
                    continue
                return None, JSONResponse({"error": "Rate limit exceeded. Please try again later."}, status_code=429)

            elif response.status_code >= 500:
                logging.warning(f"Received {response.status_code} Server Error. Retrying...")
                if attempt < max_retries - 1:
                    import time
                    time.sleep(1)
                    continue
                return None, JSONResponse({"error": "Microsoft Graph service temporarily unavailable."}, status_code=503)

            else:
                logging.error(f"Unhandled error. Status: {response.status_code}, Body: {response.text[:500]}")
                return None, JSONResponse({
                    "error": f"API request failed with status {response.status_code}",
                    "details": response.text[:500]
                }, status_code=response.status_code)

        except requests.exceptions.Timeout:
            logging.warning("Request timed out.")
            if attempt < max_retries - 1:
                continue
            return None, JSONResponse({"error": "Request timeout. Please try again."}, status_code=408)

        except requests.exceptions.RequestException as e:
            logging.error(f"RequestException occurred: {str(e)}")
            if attempt < max_retries - 1:
                continue
            return None, JSONResponse({"error": f"Network error: {str(e)}"}, status_code=500)

    logging.critical("Max retries exceeded. Giving up.")
    return None, JSONResponse({"error": "Max retries exceeded."}, status_code=500)


def process_graph_response(response_data: dict, filters: dict, b_sanitize: bool = True) -> dict:
    if "error" in response_data:
        error_code = response_data["error"].get("code", "Unknown")
        error_message = response_data["error"].get("message", "Unknown error")
        
        if error_code == "InefficientFilter":
            return None, JSONResponse({
                "error": "Query too complex. Please use simpler filters or smaller date ranges.",
                "suggestion": "Try using fewer filters or a shorter date range (max 30 days)."
            }, status_code=400)
        elif error_code == "Forbidden":
            return None, JSONResponse({"error": "Access denied. Check application permissions."}, status_code=403)
        elif error_code == "TooManyRequests":
            return None, JSONResponse({"error": "Rate limit exceeded. Please wait before making another request."}, status_code=429)
        else:
            return None, JSONResponse({
                "error": f"Microsoft Graph API error: {error_code}",
                "message": error_message
            }, status_code=400)

    if "value" not in response_data:
        return None, JSONResponse({"error": "Invalid response format from Microsoft Graph API."}, status_code=500)

    messages = response_data.get("value", [])
    email_type = filters.get('email_type', 'received')
    
    if filters.get('search') and (filters.get('start_date') or filters.get('end_date') or filters.get('unread_only')):
        messages = apply_client_side_filters(messages, filters, email_type)
    
    elif filters.get('from_email') and not filters.get('search'):
        if email_type == "sent":
            # Filter sent emails by recipient
            filtered_messages = []
            for msg in messages:
                to_recipients = msg.get("toRecipients", [])
                for recipient in to_recipients:
                    if recipient.get("emailAddress", {}).get("address", "").lower() == filters['from_email'].lower():
                        filtered_messages.append(msg)
                        break
            messages = filtered_messages
        else:
            # Filter received emails by sender
            messages = [msg for msg in messages if msg.get("from", {}).get("emailAddress", {}).get("address", "").lower() == filters['from_email'].lower()]

    sanitized_messages = []
    if b_sanitize:
        for message in messages:
            try:
                sanitized_messages.append(sanitize_message(message, email_type))
            except Exception as e:
                continue
    else:
        # Add email type to unsanitized messages for processing
        for message in messages:
            message["emailType"] = email_type
        sanitized_messages = messages
    
    return {
        "messages": sanitized_messages,
        "next_link": response_data.get("@odata.nextLink"),
        "total_count": len(sanitized_messages)
    }, None

async def process_email_documents(messages: List[Dict], ait_id: str) -> Dict:
    """
    Process email documents and create vector embeddings.
    Returns processing statistics.
    """
    total_processed = 0
    total_chunks_stored = 0
    total_chunks_skipped = 0
    
    # Initialize vector collection
    await vector_service.initialize_collection(ait_id = ait_id)
    
    for message in messages:
        try:
            # Parse datetime fields
            def parse_api_datetime(dt_str):
                if not dt_str:
                    return None
                try:
                    if dt_str.endswith('Z'):
                        return datetime.strptime(dt_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                    else:
                        return datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
                except (ValueError, TypeError):
                    return None
            
            # Extract and clean content
            content = ""
            body_data = message.get("body", {})
            if body_data and body_data.get("content"):
                content = html2text.html2text(body_data.get("content", "")).replace("\n", "    ")
            
            # Extract sender information (handle both sent and received emails)
            email_type = message.get("emailType", "received")
            if email_type == "sent":
                sender_data = message.get("sender", {})
                sender_email_data = sender_data.get("emailAddress", {}) if sender_data else {}
                sender_name = sender_email_data.get("name", "") if sender_email_data else ""
                sender_address = sender_email_data.get("address", "") if sender_email_data else ""
            else:
                sender_data = message.get("from", {})
                sender_email_data = sender_data.get("emailAddress", {}) if sender_data else {}
                sender_name = sender_email_data.get("name", "") if sender_email_data else ""
                sender_address = sender_email_data.get("address", "") if sender_email_data else ""
            
            # Prepare email data for vector processing
            email_data = {
                "email_id": message.get("id", ""),
                "ait_id": ait_id,
                "subject": message.get("subject", ""),
                "sender_name": sender_name,
                "sender_address": sender_address,
                "received_datetime": parse_api_datetime(message.get("receivedDateTime")),
                "sent_datetime": parse_api_datetime(message.get("sentDateTime")),
                "content": content,
                "has_attachments": message.get("hasAttachments", False),
                "is_read": message.get("isRead", False),
                "flag_status": message.get("flag", {}).get("flagStatus", "notFlagged"),
                "categories": json.dumps(message.get("categories", [])),
                "inference_classification": message.get("inferenceClassification", ""),
                "email_type": email_type  # Add email type to stored data
            }
            
            # Create vector embeddings
            chunks_stored, chunks_skipped = await vector_service.store_email_embeddings(email_data=email_data, ait_id=ait_id)
            
            total_chunks_stored += chunks_stored
            total_chunks_skipped += chunks_skipped
            total_processed += 1
            
            logging.info(f"Processed {email_type} email {email_data['email_id']}: {chunks_stored} chunks stored, {chunks_skipped} skipped")
            
        except Exception as e:
            logging.error(f"Error processing email document: {e}")
            continue
    
    return {
        "total_emails_processed": total_processed,
        "total_chunks_stored": total_chunks_stored,
        "total_chunks_skipped": total_chunks_skipped
    }

async def sync_emails(
    ait_id: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    from_email: Optional[str] = None,
    unread_only: Optional[bool] = False,
    search: Optional[str] = None,
    top: Optional[int] = 10,
    orderby: Optional[str] = "receivedDateTime desc",
    email_type: Optional[str] = "both", 
    next_url: Optional[str] = None
):
    """Updated sync_emails function that processes ALL emails with proper pagination."""
    
    token_data = await get_token(ait_id)
    if not token_data:
        return {"error": "User not authenticated.", "status_code": 401}
    
    access_token = token_data.get("access_token")
    if not access_token:
        return {"error": "Invalid access token.", "status_code": 401}
    
    headers = build_headers(access_token)
    
    total_processed = 0
    total_chunks_stored = 0
    total_chunks_skipped = 0
    
    # Process both received and sent emails
    email_types_to_process = ["received", "sent"] if email_type == "both" else [email_type]
    
    for current_type in email_types_to_process:
        logging.info(f"Starting to process {current_type} emails...")
        
        # Prepare filters for current email type
        filters, error_response = await validate_and_prepare_filters(
            start_date, end_date, from_email, unread_only, search, top, orderby, current_type
        )
        if error_response:
            return error_response
        
        # Start with the initial URL for current email type
        current_url = next_url if next_url else build_graph_url(filters)
        page_count = 0
        current_type_processed = 0
        
        # Continue fetching ALL pages for current email type
        while current_url:
            page_count += 1
            logging.info(f"Fetching page {page_count} for {current_type} emails...")
            
            response, error_response = await make_graph_request(current_url, headers, ait_id)
            if error_response:
                logging.error(f"Error fetching page {page_count} for {current_type} emails: {error_response}")
                return error_response
            
            try:
                data = response.json()
                result, error_response = process_graph_response(data, filters, b_sanitize=False)
                if error_response:
                    logging.error(f"Error processing page {page_count} for {current_type} emails: {error_response}")
                    return error_response
                
                page_messages = result["messages"]
                if not page_messages:
                    logging.info(f"No more {current_type} emails found on page {page_count}")
                    break
                
                logging.info(f"Found {len(page_messages)} {current_type} emails on page {page_count}")
                
                # Process current page messages immediately
                if page_messages:
                    index_result = await process_and_build_index(
                        ait_id=ait_id,
                        file_names=[],
                        document_collection="log_mse_email",
                        destination="email",
                        messages=page_messages
                    )
                    
                    if not index_result["status"]:
                        logging.error(f"Failed to index page {page_count} for {current_type} emails: {index_result['message']}")
                        return {
                            "success": False,
                            "error": index_result["message"],
                            "total_processed": total_processed,
                            "pages_processed": page_count - 1
                        }
                    
                    # Update counters
                    page_processed = len(page_messages)
                    total_processed += page_processed
                    current_type_processed += page_processed
                    
                    # Update chunk statistics if available
                    if "index_result" in index_result:
                        total_chunks_stored += index_result["index_result"].get("chunks_stored", 0)
                        total_chunks_skipped += index_result["index_result"].get("chunks_skipped", 0)
                    
                    logging.info(f"Successfully processed page {page_count}: {page_processed} {current_type} emails, Total processed: {total_processed}")
                
                # Get next page URL
                current_url = result.get("next_link")
                
                # Small delay to avoid rate limiting
                if current_url:
                    await asyncio.sleep(DELAY_BETWEEN_BATCHES)
                
            except ValueError as e:
                logging.error(f"Failed to parse JSON response for {current_type} emails on page {page_count}: {e}")
                return {
                    "error": f"Failed to parse JSON response from Microsoft Graph API for {current_type} emails.",
                    "details": str(e),
                    "status_code": 500
                }
            except Exception as e:
                logging.error(f"Unexpected error processing {current_type} emails on page {page_count}: {e}")
                return {
                    "error": f"Unexpected error processing {current_type} emails.",
                    "details": str(e),
                    "status_code": 500
                }
        
        logging.info(f"Completed processing {current_type} emails: {current_type_processed} emails across {page_count} pages")
    
    return {
        "success": True,
        "total_processed": total_processed,
        "total_chunks_stored": total_chunks_stored,
        "total_chunks_skipped": total_chunks_skipped,
        "email_types_processed": email_types_to_process,
        "message": f"Successfully processed all emails across all pages",
    }


async def sync_all_emails(
    ait_id: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    batch_size: int = BATCH_SIZE,
    max_emails: Optional[int] = None,
    resume_token: Optional[str] = None,
    default_days_sync: Optional[int] = 1825
) -> Dict:
    """Sync all emails with proper pagination handling for both received and sent emails."""
    start_time = time.time()
    
    token_data = await get_token(ait_id)
    if not token_data:
        return {"error": "User not authenticated.", "status_code": 401}
    
    access_token = token_data.get("access_token")
    if not access_token:
        return {"error": "Invalid access token.", "status_code": 401}
    
    headers = build_headers(access_token)
    
    if not start_date:
        start_date = (datetime.utcnow() - timedelta(days=default_days_sync)).strftime("%Y-%m-%d")
    if not end_date:
        end_date = datetime.utcnow().strftime("%Y-%m-%d")
    
    logging.info(f"Starting full email sync for user {ait_id} from {start_date} to {end_date}")
    
    total_stats = {
        "total_emails_processed": 0,
        "total_chunks_stored": 0,
        "total_chunks_skipped": 0,
        "batches_processed": 0,
        "pages_processed": 0,
        "received_emails": 0,
        "sent_emails": 0,
        "errors": [],
        "processing_time": 0,
        "next_resume_token": None
    }
    
    try:
        # Determine which email types to process
        email_types = ["sent", "received"]
        
        for email_type in email_types:
            logging.info(f"Starting to process {email_type} emails...")
            
            filters = {
                "start_date": start_date,
                "end_date": end_date,
                "email_type": email_type,
                "top": min(batch_size, MAX_EMAILS_PER_REQUEST),
                "orderby": "sentDateTime desc" if email_type == "sent" else "receivedDateTime desc"
            }
            
            # Use resume token if it matches current email type
            if resume_token and f"type={email_type}" in resume_token:
                current_url = resume_token
            else:
                current_url = build_graph_url(filters)
            
            page_count = 0
            current_type_processed = 0
            
            # Process ALL pages for current email type
            while current_url and (not max_emails or total_stats["total_emails_processed"] < max_emails):
                page_count += 1
                total_stats["pages_processed"] += 1
                
                logging.info(f"Processing page {page_count} for {email_type} emails...")
                
                response, error_response = await make_graph_request(current_url, headers, ait_id)
                if error_response:
                    error_msg = f"API request failed for {email_type} page {page_count}: {error_response}"
                    total_stats["errors"].append(error_msg)
                    logging.error(error_msg)
                    break
                
                try:
                    data = response.json()
                    result, error_response = process_graph_response(data, filters, b_sanitize=False)
                    if error_response:
                        error_msg = f"Response processing failed for {email_type} page {page_count}: {error_response}"
                        total_stats["errors"].append(error_msg)
                        logging.error(error_msg)
                        break
                    
                    messages = result["messages"]
                    if not messages:
                        logging.info(f"No more {email_type} emails to process on page {page_count}")
                        break
                    
                    # Apply max_emails limit
                    if max_emails and total_stats["total_emails_processed"] + len(messages) > max_emails:
                        remaining = max_emails - total_stats["total_emails_processed"]
                        messages = messages[:remaining]
                        logging.info(f"Applying max_emails limit: processing {len(messages)} out of {len(result['messages'])} messages")
                    
                    # Process the batch
                    batch_result = await _process_email_batch(messages, ait_id)
                    
                    if not batch_result["success"]:
                        error_msg = f"Batch processing failed for {email_type} page {page_count}: {batch_result.get('error', 'Unknown error')}"
                        total_stats["errors"].append(error_msg)
                        logging.error(error_msg)
                        # Continue to next page instead of breaking
                        current_url = result.get("next_link")
                        continue
                    
                    # Update stats
                    batch_processed = len(messages)
                    total_stats["total_emails_processed"] += batch_processed
                    total_stats["total_chunks_stored"] += batch_result["chunks_stored"]
                    total_stats["total_chunks_skipped"] += batch_result["chunks_skipped"]
                    total_stats["batches_processed"] += 1
                    current_type_processed += batch_processed
                    
                    if email_type == "received":
                        total_stats["received_emails"] += batch_processed
                    else:
                        total_stats["sent_emails"] += batch_processed
                    
                    logging.info(
                        f"Processed page {page_count} of {email_type} emails: "
                        f"{batch_processed} emails, {batch_result['chunks_stored']} chunks stored, "
                        f"Total processed: {total_stats['total_emails_processed']}"
                    )
                    
                    # Get next page URL
                    current_url = result.get("next_link")
                    if current_url:
                        # Include email type in resume token
                        total_stats["next_resume_token"] = f"{current_url}&type={email_type}"
                        await asyncio.sleep(DELAY_BETWEEN_BATCHES)
                    else:
                        total_stats["next_resume_token"] = None
                        logging.info(f"Completed all pages for {email_type} emails")
                    
                    # Check if we've reached max emails
                    if max_emails and total_stats["total_emails_processed"] >= max_emails:
                        logging.info(f"Reached max_emails limit: {max_emails}")
                        break
                
                except ValueError as e:
                    error_msg = f"JSON parsing error for {email_type} page {page_count}: {str(e)}"
                    total_stats["errors"].append(error_msg)
                    logging.error(error_msg)
                    break
                except Exception as e:
                    error_msg = f"Unexpected error processing {email_type} page {page_count}: {str(e)}"
                    total_stats["errors"].append(error_msg)
                    logging.error(error_msg)
                    # Continue to next page instead of breaking
                    current_url = result.get("next_link")
                    continue
            
            logging.info(f"Completed processing {email_type} emails: {current_type_processed} emails across {page_count} pages")
            
            # If we've reached max emails, break from email type loop
            if max_emails and total_stats["total_emails_processed"] >= max_emails:
                break
    
    except Exception as e:
        error_msg = f"Critical error in sync_all_emails: {str(e)}"
        total_stats["errors"].append(error_msg)
        logging.error(error_msg)
    
    total_stats["processing_time"] = time.time() - start_time
    
    success = len(total_stats["errors"]) == 0
    
    result = {
        "success": success,
        "message": "Email sync completed successfully" if success else "Email sync completed with errors",
        "statistics": total_stats,
        "date_range": {"start_date": start_date, "end_date": end_date}
    }
    
    if not success:
        result["error"] = "Completed with errors"
    
    return result


async def _process_email_batch(messages: List[Dict], ait_id: str) -> Dict:
    """
    Process a batch of emails using the existing indexing infrastructure.
    Enhanced with better error handling and logging.
    """
    try:
        if not messages:
            return {
                "chunks_stored": 0,
                "chunks_skipped": 0,
                "success": True,
                "message": "No messages to process"
            }
        
        logging.info(f"Processing batch of {len(messages)} emails for user {ait_id}")
        
        index_result = await process_and_build_index(
            ait_id=ait_id,
            file_names=[],
            document_collection="log_mse_email",
            destination="email",
            messages=messages
        )
        
        if index_result["status"]:
            chunks_stored = index_result.get("index_result", {}).get("chunks_stored", 0)
            chunks_skipped = index_result.get("index_result", {}).get("chunks_skipped", 0)
            
            logging.info(f"Batch processing successful: {chunks_stored} chunks stored, {chunks_skipped} chunks skipped")
            
            return {
                "chunks_stored": chunks_stored,
                "chunks_skipped": chunks_skipped,
                "success": True,
                "message": f"Successfully processed {len(messages)} emails"
            }
        else:
            error_msg = index_result.get("message", "Unknown indexing error")
            logging.error(f"Indexing failed: {error_msg}")
            return {
                "chunks_stored": 0,
                "chunks_skipped": 0,
                "success": False,
                "error": error_msg
            }
    
    except Exception as e:
        error_msg = f"Error in _process_email_batch: {str(e)}"
        logging.error(error_msg)
        return {
            "chunks_stored": 0,
            "chunks_skipped": 0,
            "success": False,
            "error": error_msg
        }

async def _process_email_type_in_batches(
    ait_id: str,
    email_type: str,
    start_date: str,
    end_date: str,
    batch_size: int,
    max_emails: Optional[int],
    headers: Dict,
    resume_token: Optional[str]
) -> Dict:
    """
    Process emails of a specific type (received/sent) in batches.
    """
    stats = {
        "emails_processed": 0,
        "chunks_stored": 0,
        "chunks_skipped": 0,
        "batches_processed": 0,
        "errors": []
    }
    
    filters = {
        "start_date": start_date,
        "end_date": end_date,
        "email_type": email_type,
        "top": min(batch_size, MAX_EMAILS_PER_REQUEST),
        "orderby": "sentDateTime desc" if email_type == "sent" else "receivedDateTime desc"
    }
    
    current_url = resume_token if resume_token else build_graph_url(filters)
    
    while current_url and (not max_emails or stats["emails_processed"] < max_emails):
        try:
            response, error_response = await make_graph_request(current_url, headers, ait_id)
            if error_response:
                stats["errors"].append(f"API request failed: {error_response}")
                break
            
            data = response.json()
            result, error_response = process_graph_response(data, filters, b_sanitize=False)
            if error_response:
                stats["errors"].append(f"Response processing failed: {error_response}")
                break
            
            messages = result["messages"]
            if not messages:
                logging.info(f"No more {email_type} emails to process")
                break
            
            if max_emails and stats["emails_processed"] + len(messages) > max_emails:
                remaining = max_emails - stats["emails_processed"]
                messages = messages[:remaining]
            
            batch_result = await _process_email_batch(messages, ait_id)
            
            stats["emails_processed"] += len(messages)
            stats["chunks_stored"] += batch_result["chunks_stored"]
            stats["chunks_skipped"] += batch_result["chunks_skipped"]
            stats["batches_processed"] += 1
            
            logging.info(f"Processed batch {stats['batches_processed']} of {email_type} emails: {len(messages)} emails, {batch_result['chunks_stored']} chunks stored")
            
            current_url = result.get("next_link")
            
            if current_url:
                await asyncio.sleep(DELAY_BETWEEN_BATCHES)
            
        except Exception as e:
            error_msg = f"Error processing {email_type} batch {stats['batches_processed'] + 1}: {str(e)}"
            stats["errors"].append(error_msg)
            logging.error(error_msg)
            
            continue
    
    return stats