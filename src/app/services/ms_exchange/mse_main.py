import os
import re
import requests
import html2text
from typing import Optional
from dotenv import load_dotenv
from urllib.parse import quote
from datetime import datetime, timedelta
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from src.app.services.ms_exchange.mse_token_store import get_token, refresh_access_token, store_emails_in_mysql

load_dotenv(override=True)

ms_router = APIRouter(prefix="/ms_exchange")

AZURE_CLIENT_ID = os.getenv("AZURE_CLIENT_ID")
AZURE_SECRET_ID = os.getenv("AZURE_SECRET_VALUE")
TENANT_ID = os.getenv("TENANT_ID")
REDIRECT_URI = os.getenv("REDIRECT_URI")
AUTHORITY = "https://login.microsoftonline.com/common"
AUTH_SCOPES = ["Mail.ReadWrite", "Calendars.ReadWrite", "Contacts.ReadWrite"]
TOKEN_SCOPES = ["Mail.ReadWrite", "Calendars.ReadWrite", "Contacts.ReadWrite"]
GRAPH_SCOPES = ["Mail.ReadWrite", "Calendars.ReadWrite", "Contacts.ReadWrite"]
DEFAULT_USER_ID = "anonymous"
MAX_TOP = 100
MAX_SEARCH_LENGTH = 255
MAX_DATE_RANGE_DAYS = 365
DEFAULT_DAYS_RANGE = 365

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

def sanitize_message(message: dict) -> dict:
    return {
        "id": message.get("id", ""),
        "subject": message.get("subject", ""),
        "from": message.get("from", {}),
        "receivedDateTime": message.get("receivedDateTime", ""),
        "content": html2text.html2text(message.get("body", {}).get("content", "")).replace("\n", "    "),
        "hasAttachments": message.get("hasAttachments", False)
    }

def apply_client_side_filters(messages: list, filters: dict) -> list:
    filtered_messages = []
    for message in messages:
        if filters.get('start_date') or filters.get('end_date'):
            received_dt_str = message.get("receivedDateTime", "")
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
    orderby: Optional[str] = "receivedDateTime desc"
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
    
    return {
        'start_date': start_date,
        'end_date': end_date,
        'from_email': from_email,
        'unread_only': unread_only,
        'search': search,
        'top': top,
        'orderby': orderby
    }, None

def build_graph_url(filters: dict) -> str:
    if filters.get('search'):
        search_terms = [filters['search']]
        if filters.get('from_email'):
            search_terms.append(f"from:{filters['from_email']}")
        search_query = " ".join(search_terms)
        return f"https://graph.microsoft.com/v1.0/me/messages?$search=\"{quote(search_query)}\"&$top={min(filters['top'] * 3, 300)}"
    
    elif filters.get('from_email') and not (filters.get('start_date') or filters.get('end_date') or filters.get('unread_only')):
        return f"https://graph.microsoft.com/v1.0/me/messages?$search=\"from:{filters['from_email']}\"&$top={filters['top']}"
    
    else:
        query_filters = []
        if filters.get('start_date'):
            query_filters.append(f"receivedDateTime ge {filters['start_date']}T00:00:00Z")
        if filters.get('end_date'):
            query_filters.append(f"receivedDateTime le {filters['end_date']}T23:59:59Z")
        if filters.get('unread_only'):
            query_filters.append("isRead eq false")
        if filters.get('from_email'):
            query_filters.append(f"from/emailAddress/address eq '{filters['from_email']}'")
        
        if query_filters:
            filter_query = " and ".join(query_filters)
            return f"https://graph.microsoft.com/v1.0/me/messages?$filter={quote(filter_query)}&$top={filters['top']}&$orderby={filters['orderby']}"
        else:
            default_filter = f"receivedDateTime ge {(datetime.utcnow() - timedelta(days=DEFAULT_DAYS_RANGE)).strftime('%Y-%m-%d')}T00:00:00Z"
            return f"https://graph.microsoft.com/v1.0/me/messages?$filter={quote(default_filter)}&$top={filters['top']}&$orderby={filters['orderby']}"

async def make_graph_request(url: str, headers: dict, ait_id: str):
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = requests.get(url, headers=headers, timeout=30)
            
            if response.status_code == 200:
                return response, None
            elif response.status_code == 401:
                new_access_token = await refresh_access_token(ait_id)
                headers = build_headers(new_access_token)
                continue
            elif response.status_code == 403:
                return None, JSONResponse({"error": "Insufficient permissions to access emails."}, status_code=403)
            elif response.status_code == 429:
                if attempt < max_retries - 1:
                    import time
                    time.sleep(2 ** attempt)
                    continue
                return None, JSONResponse({"error": "Rate limit exceeded. Please try again later."}, status_code=429)
            elif response.status_code >= 500:
                if attempt < max_retries - 1:
                    import time
                    time.sleep(1)
                    continue
                return None, JSONResponse({"error": "Microsoft Graph service temporarily unavailable."}, status_code=503)
            else:
                return None, JSONResponse({
                    "error": f"API request failed with status {response.status_code}",
                    "details": response.text[:500]
                }, status_code=response.status_code)
                
        except requests.exceptions.Timeout:
            if attempt < max_retries - 1:
                continue
            return None, JSONResponse({"error": "Request timeout. Please try again."}, status_code=408)
        except requests.exceptions.RequestException as e:
            if attempt < max_retries - 1:
                continue
            return None, JSONResponse({"error": f"Network error: {str(e)}"}, status_code=500)
    
    return None, JSONResponse({"error": "Max retries exceeded."}, status_code=500)

def process_graph_response(response_data: dict, filters: dict, b_sanitize:bool = True) -> dict:
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
    
    if filters.get('search') and (filters.get('start_date') or filters.get('end_date') or filters.get('unread_only')):
        messages = apply_client_side_filters(messages, filters)
    
    elif filters.get('from_email') and not filters.get('search'):
        messages = [msg for msg in messages if msg.get("from", {}).get("emailAddress", {}).get("address", "").lower() == filters['from_email'].lower()]

    sanitized_messages = []
    if b_sanitize:
        for message in messages:
            try:
                sanitized_messages.append(sanitize_message(message))
            except Exception as e:
                continue
    else:
        sanitized_messages = messages
    return {
        "messages": sanitized_messages,
        "next_link": response_data.get("@odata.nextLink"),
        "total_count": len(sanitized_messages)
    }, None

async def get_emails(
    ait_id: str = DEFAULT_USER_ID,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    from_email: Optional[str] = None,
    unread_only: Optional[bool] = False,
    search: Optional[str] = None,
    top: Optional[int] = Query(10, ge=1, le=MAX_TOP),
    orderby: Optional[str] = "receivedDateTime desc",
    next_url: Optional[str] = None
):
    # Get access token
    token_data = await get_token(ait_id)
    if not token_data:
        return JSONResponse({"error": "User not authenticated."}, status_code=401)

    access_token = token_data.get("access_token")
    if not access_token:
        return JSONResponse({"error": "Invalid access token."}, status_code=401)

    headers = build_headers(access_token)

    # Handle next_url for pagination
    if next_url:
        if not next_url.startswith("https://graph.microsoft.com"):
            return JSONResponse({"error": "Invalid next_url provided."}, status_code=400)
        url = next_url
    else:
        # Validate and prepare filters
        filters, error_response = await validate_and_prepare_filters(
            start_date, end_date, from_email, unread_only, search, top, orderby
        )
        if error_response:
            return error_response
        
        url = build_graph_url(filters)

    # Make API request
    response, error_response = await make_graph_request(url, headers, ait_id)
    if error_response:
        return error_response

    # Process response
    try:
        data = response.json()
        result, error_response = process_graph_response(data, {
            'start_date': start_date,
            'end_date': end_date,
            'from_email': from_email,
            'unread_only': unread_only,
            'search': search,
            'top': top
        })
        if error_response:
            return error_response

        return {
            **result,
            "filters_applied": {
                "start_date": start_date,
                "end_date": end_date,
                "from_email": from_email,
                "unread_only": unread_only,
                "search": search
            }
        }

    except ValueError as e:
        return JSONResponse({
            "error": "Failed to parse JSON response from Microsoft Graph API.",
            "details": str(e)
        }, status_code=500)
    except Exception as e:
        return JSONResponse({
            "error": "Unexpected error processing response.",
            "details": str(e)
        }, status_code=500)

async def sync_emails(
    ait_id: str = DEFAULT_USER_ID,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    from_email: Optional[str] = None,
    unread_only: Optional[bool] = False,
    search: Optional[str] = None,
    top: Optional[int] = Query(10, ge=1, le=MAX_TOP),
    orderby: Optional[str] = "receivedDateTime desc",
    next_url: Optional[str] = None
):
    # Get access token
    token_data = await get_token(ait_id)
    if not token_data:
        return JSONResponse({"error": "User not authenticated."}, status_code=401)

    access_token = token_data.get("access_token")
    if not access_token:
        return JSONResponse({"error": "Invalid access token."}, status_code=401)

    headers = build_headers(access_token)

    # Handle next_url for pagination
    if next_url:
        if not next_url.startswith("https://graph.microsoft.com"):
            return JSONResponse({"error": "Invalid next_url provided."}, status_code=400)
        url = next_url
    else:
        # Validate and prepare filters
        filters, error_response = await validate_and_prepare_filters(
            start_date, end_date, from_email, unread_only, search, top, orderby
        )
        if error_response:
            return error_response
        
        url = build_graph_url(filters)

    # Make API request
    response, error_response = await make_graph_request(url, headers, ait_id)
    if error_response:
        return error_response

    # Process response
    try:
        data = response.json()
        result, error_response = process_graph_response(data, {
            'start_date': start_date,
            'end_date': end_date,
            'from_email': from_email,
            'unread_only': unread_only,
            'search': search,
            'top': top
        }, b_sanitize=False)
        if error_response:
            return error_response

        # Store emails in MongoDB
        stored_count, skipped_count = await store_emails_in_mysql(result["messages"],ait_id )

        return {
            "success": True,
            "stored_emails": stored_count,
            "skipped_duplicates": skipped_count,
            "next_link": result.get("next_link"),
            "total_processed": len(result["messages"]),
            "filters_applied": {
                "start_date": start_date,
                "end_date": end_date,
                "from_email": from_email,
                "unread_only": unread_only,
                "search": search
            }
        }

    except ValueError as e:
        return JSONResponse({
            "error": "Failed to parse JSON response from Microsoft Graph API.",
            "details": str(e)
        }, status_code=500)
    except Exception as e:
        return JSONResponse({
            "error": "Unexpected error processing response.",
            "details": str(e)
        }, status_code=500)