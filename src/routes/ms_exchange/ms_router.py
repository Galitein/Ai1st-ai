import os
import re
import requests
import html2text
from typing import Optional
from dotenv import load_dotenv
from urllib.parse import quote
from datetime import datetime, timedelta
from msal import ConfidentialClientApplication
from fastapi import APIRouter, Request, Request, Query
from fastapi.responses import RedirectResponse, JSONResponse
from src.routes.ms_exchange.token_store import save_token, get_token, refresh_access_token

load_dotenv(override=True)

ms_router = APIRouter(prefix="/ms_auth")

AZURE_CLIENT_ID = os.getenv("AZURE_CLIENT_ID")
AZURE_SECRET_ID = os.getenv("AZURE_SECRET_VALUE")
TENANT_ID = os.getenv("TENANT_ID")
REDIRECT_URI = os.getenv("REDIRECT_URI")
AUTHORITY = f"https://login.microsoftonline.com/common"
AUTH_SCOPES = ["Mail.ReadWrite","Calendars.ReadWrite","Contacts.ReadWrite"]
TOKEN_SCOPES = ["Mail.ReadWrite","Calendars.ReadWrite","Contacts.ReadWrite"]
GRAPH_SCOPES = ["Mail.ReadWrite","Calendars.ReadWrite","Contacts.ReadWrite"]
user_id = "user1"

msal_app = ConfidentialClientApplication(
    client_id=AZURE_CLIENT_ID,
    client_credential=AZURE_SECRET_ID,
    authority=AUTHORITY
)

@ms_router.get("/login")
def login():
    auth_url = msal_app.get_authorization_request_url(
        scopes=AUTH_SCOPES,  # don't include offline_access here
        redirect_uri=REDIRECT_URI,
        state=user_id
    )
    return RedirectResponse(auth_url)

@ms_router.get("/azurecallback")
def callback(request: Request):
    code = request.query_params.get("code")
    state = request.query_params.get("state", user_id)  # Default user ID for now
    result = msal_app.acquire_token_by_authorization_code(
        code,
        scopes=GRAPH_SCOPES,  # include offline_access here
        redirect_uri=REDIRECT_URI
    )
    if "access_token" in result:
        save_token(state, result)
        return JSONResponse({"message": "Login successful!"})
    return JSONResponse({"error": result.get("error_description")})


@ms_router.get("/me/emails")
def get_emails(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    from_email: Optional[str] = None,
    unread_only: Optional[bool] = False,
    search: Optional[str] = None,
    top: Optional[int] = Query(10, ge=1, le=100),  
    orderby: Optional[str] = "receivedDateTime desc",
    next_url: Optional[str] = None
):
    """
    Get emails with proper filtering and edge case handling.
    At least one filter must be provided to prevent fetching all emails.
    """
    
    # TODO: remove this hard coded user with proper UID format
    token_data = get_token(user_id)
    if not token_data:
        return JSONResponse({"error": "User not authenticated."}, status_code=401)

    access_token = token_data.get("access_token")
    if not access_token:
        return JSONResponse({"error": "Invalid access token."}, status_code=401)

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Prefer": 'outlook.timezone="UTC"',
        "Content-Type": "application/json"
    }

    # If next_url is provided, use it directly (for pagination)
    if next_url:
        if not next_url.startswith("https://graph.microsoft.com"):
            return JSONResponse({"error": "Invalid next_url provided."}, status_code=400)
        url = next_url
    else:
        # CRITICAL: Ensure at least one filter is provided
        filters_provided = any([
            start_date, end_date, from_email, unread_only, search
        ])
        
        if not filters_provided:
            # Default to last 30 days if no filters provided
            end_date_default = datetime.utcnow()
            start_date_default = end_date_default - timedelta(days=30)
            start_date = start_date_default.strftime("%Y-%m-%d")
            end_date = end_date_default.strftime("%Y-%m-%d")

        # Validate date formats
        if start_date:
            try:
                datetime.strptime(start_date, "%Y-%m-%d")
            except ValueError:
                return JSONResponse({"error": "Invalid start_date format. Use YYYY-MM-DD."}, status_code=400)

        if end_date:
            try:
                datetime.strptime(end_date, "%Y-%m-%d")
            except ValueError:
                return JSONResponse({"error": "Invalid end_date format. Use YYYY-MM-DD."}, status_code=400)

        # Validate date range
        if start_date and end_date:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
            if start_dt > end_dt:
                return JSONResponse({"error": "start_date cannot be after end_date."}, status_code=400)
            
            # Limit date range to prevent complex queries
            if (end_dt - start_dt).days > 365:
                return JSONResponse({"error": "Date range cannot exceed 365 days."}, status_code=400)

        # Validate email format
        if from_email:
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_pattern, from_email):
                return JSONResponse({"error": "Invalid email format."}, status_code=400)

        # Validate search query
        if search:
            # Sanitize search query to prevent injection
            search = search.strip()
            if len(search) > 255:
                return JSONResponse({"error": "Search query too long (max 255 characters)."}, status_code=400)
            if not search:
                search = None

        # Validate orderby parameter
        valid_orderby = [
            "receivedDateTime desc", "receivedDateTime asc",
            "sentDateTime desc", "sentDateTime asc",
            "subject desc", "subject asc"
        ]
        if orderby and orderby not in valid_orderby:
            orderby = "receivedDateTime desc"  # Default fallback

        # Build query with proper combination of search and filters
        try:
            # Strategy: Combine search with filters intelligently
            
            if search:
                # When search is provided, we need to use a hybrid approach
                # Microsoft Graph $search doesn't support combining with $filter for dates
                # So we'll use $search and then apply additional filtering client-side
                
                search_terms = [search]
                if from_email:
                    search_terms.append(f"from:{from_email}")
                
                search_query = " ".join(search_terms)
                
                # Build base search URL
                url = f"https://graph.microsoft.com/v1.0/me/messages?$search=\"{quote(search_query)}\"&$top={min(top * 3, 300)}"
                # Use larger limit initially to account for client-side filtering
                
            elif from_email and not (start_date or end_date or unread_only):
                # Simple from filter using search (more reliable than $filter for email addresses)
                url = f"https://graph.microsoft.com/v1.0/me/messages?$search=\"from:{from_email}\"&$top={top}"
                
            else:
                # Use $filter for date and unread filters (no search involved)
                filters = []
                
                # Add date filters
                if start_date:
                    filters.append(f"receivedDateTime ge {start_date}T00:00:00Z")
                if end_date:
                    filters.append(f"receivedDateTime le {end_date}T23:59:59Z")
                
                # Add unread filter
                if unread_only:
                    filters.append("isRead eq false")
                
                # Add from_email filter (using $filter is less reliable but works for simple cases)
                if from_email:
                    filters.append(f"from/emailAddress/address eq '{from_email}'")
                
                # Build URL with filters
                if filters:
                    filter_query = " and ".join(filters)
                    url = f"https://graph.microsoft.com/v1.0/me/messages?$filter={quote(filter_query)}&$top={top}&$orderby={orderby}"
                else:
                    # Fallback: last 30 days if no filters (should not reach here due to earlier check)
                    default_filter = f"receivedDateTime ge {(datetime.utcnow() - timedelta(days=30)).strftime('%Y-%m-%d')}T00:00:00Z"
                    url = f"https://graph.microsoft.com/v1.0/me/messages?$filter={quote(default_filter)}&$top={top}&$orderby={orderby}"

        except Exception as e:
            return JSONResponse({"error": f"Failed to build query: {str(e)}"}, status_code=400)

    print(f"Query URL: {url}")

    # Make the API request with retry logic
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = requests.get(url, headers=headers, timeout=30)
            
            # Handle different response status codes
            if response.status_code == 200:
                break
            elif response.status_code == 401:
                # return JSONResponse({"error": "Authentication failed. Token may be expired."}, status_code=401)
                new_access_token = refresh_access_token(user_id) 
                headers = {
                    "Authorization": f"Bearer {new_access_token}",
                    "Prefer": 'outlook.timezone="UTC"',
                    "Content-Type": "application/json"
                }
                response = requests.get(url, headers=headers, timeout=30)

            elif response.status_code == 403:
                return JSONResponse({"error": "Insufficient permissions to access emails."}, status_code=403)
            elif response.status_code == 429:
                # Rate limited - wait and retry
                if attempt < max_retries - 1:
                    import time
                    time.sleep(2 ** attempt)  # Exponential backoff
                    continue
                return JSONResponse({"error": "Rate limit exceeded. Please try again later."}, status_code=429)
            elif response.status_code >= 500:
                # Server error - retry
                if attempt < max_retries - 1:
                    import time
                    time.sleep(1)
                    continue
                return JSONResponse({"error": "Microsoft Graph service temporarily unavailable."}, status_code=503)
            else:
                return JSONResponse({
                    "error": f"API request failed with status {response.status_code}",
                    "details": response.text[:500]  # Limit error details
                }, status_code=response.status_code)
                
        except requests.exceptions.Timeout:
            if attempt < max_retries - 1:
                continue
            return JSONResponse({"error": "Request timeout. Please try again."}, status_code=408)
        except requests.exceptions.RequestException as e:
            if attempt < max_retries - 1:
                continue
            return JSONResponse({"error": f"Network error: {str(e)}"}, status_code=500)

    # Parse response
    try:
        data = response.json()
        
        # Handle Microsoft Graph error responses
        if "error" in data:
            error_code = data["error"].get("code", "Unknown")
            error_message = data["error"].get("message", "Unknown error")
            
            # Handle specific Microsoft Graph errors
            if error_code == "InefficientFilter":
                # Simplify the query and try again with basic date filter
                fallback_date = (datetime.utcnow() - timedelta(days=7)).strftime("%Y-%m-%d")
                fallback_url = f"https://graph.microsoft.com/v1.0/me/messages?$filter=receivedDateTime ge {fallback_date}T00:00:00Z&$top={min(top, 25)}"
                
                try:
                    fallback_response = requests.get(fallback_url, headers=headers, timeout=30)
                    if fallback_response.status_code == 200:
                        fallback_data = fallback_response.json()
                        
                        # Apply client-side filtering for complex criteria
                        filtered_messages = []
                        for message in fallback_data.get("value", []):
                            # Apply date range filter
                            if start_date or end_date:
                                received_dt_str = message.get("receivedDateTime", "")
                                if received_dt_str:
                                    try:
                                        received_dt = datetime.fromisoformat(received_dt_str.replace('Z', '+00:00'))
                                        received_date = received_dt.date()
                                        
                                        if start_date:
                                            start_dt = datetime.strptime(start_date, "%Y-%m-%d").date()
                                            if received_date < start_dt:
                                                continue
                                        
                                        if end_date:
                                            end_dt = datetime.strptime(end_date, "%Y-%m-%d").date()
                                            if received_date > end_dt:
                                                continue
                                    except (ValueError, TypeError):
                                        continue
                            
                            # Apply from_email filter if specified
                            if from_email:
                                msg_from = message.get("from", {}).get("emailAddress", {}).get("address", "")
                                if msg_from.lower() != from_email.lower():
                                    continue
                            
                            # Apply unread filter if specified
                            if unread_only and message.get("isRead", True):
                                continue
                                
                            # Apply search filter if specified (basic text matching)
                            if search:
                                searchable_text = f"{message.get('subject', '')} {message.get('bodyPreview', '')}"
                                if search.lower() not in searchable_text.lower():
                                    continue
                            
                            filtered_messages.append(message)
                            
                            # Limit results
                            if len(filtered_messages) >= top:
                                break
                        
                        return {
                            "messages": filtered_messages,
                            "next_link": None,  # Don't provide next_link for fallback results
                            "warning": "Query was simplified due to complexity. Some advanced filtering was applied client-side."
                        }
                except:
                    pass
                
                return JSONResponse({
                    "error": "Query too complex. Please use simpler filters or smaller date ranges.",
                    "suggestion": "Try using fewer filters or a shorter date range (max 30 days)."
                }, status_code=400)
            
            elif error_code == "Forbidden":
                return JSONResponse({"error": "Access denied. Check application permissions."}, status_code=403)
            elif error_code == "TooManyRequests":
                return JSONResponse({"error": "Rate limit exceeded. Please wait before making another request."}, status_code=429)
            else:
                return JSONResponse({
                    "error": f"Microsoft Graph API error: {error_code}",
                    "message": error_message
                }, status_code=400)

        # Validate response structure
        if "value" not in data:
            return JSONResponse({"error": "Invalid response format from Microsoft Graph API."}, status_code=500)

        messages = data.get("value", [])
        
        # Apply client-side filtering when search was used with additional filters
        if search and (start_date or end_date or unread_only):
            filtered_messages = []
            
            for message in messages:
                # Apply date range filter
                if start_date or end_date:
                    received_dt_str = message.get("receivedDateTime", "")
                    if received_dt_str:
                        try:
                            # Parse the received date (format: 2025-06-24T10:30:00Z)
                            received_dt = datetime.fromisoformat(received_dt_str.replace('Z', '+00:00'))
                            received_date = received_dt.date()
                            
                            if start_date:
                                start_dt = datetime.strptime(start_date, "%Y-%m-%d").date()
                                if received_date < start_dt:
                                    continue
                            
                            if end_date:
                                end_dt = datetime.strptime(end_date, "%Y-%m-%d").date()
                                if received_date > end_dt:
                                    continue
                        except (ValueError, TypeError):
                            # Skip messages with invalid dates
                            continue
                
                # Apply unread filter
                if unread_only and message.get("isRead", True):
                    continue
                
                filtered_messages.append(message)
                
                # Limit results to requested top count
                if len(filtered_messages) >= top:
                    break
            
            messages = filtered_messages
        
        # Apply additional client-side filtering for from_email if needed (for edge cases)
        elif from_email and not search and not next_url:
            # Double-check from_email filtering (in case server-side filtering was incomplete)
            messages = [
                msg for msg in messages
                if msg.get("from", {}).get("emailAddress", {}).get("address", "").lower() == from_email.lower()
            ]

        # Sanitize message data
        sanitized_messages = []
        for message in messages:
            try:
                # Ensure required fields exist and are properly formatted
                sanitized_message = {
                    "id": message.get("id", ""),
                    "subject": message.get("subject", ""),
                    "from": message.get("from", {}),
                    "receivedDateTime": message.get("receivedDateTime", ""),
                    "content": html2text.html2text(message.get("body", {}).get("content","")).replace("\n","    "),  
                    "hasAttachments": message.get("hasAttachments", False)
                }
                sanitized_messages.append(sanitized_message)
            except Exception as e:
                # Skip malformed messages
                print(f"Skipping malformed message: {e}")
                continue

        return {
            "messages": sanitized_messages,
            "next_link": data.get("@odata.nextLink"),
            "total_count": len(sanitized_messages),
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