import os
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from google.auth.exceptions import GoogleAuthError

def authenticate():
    try:
        creds = None
        TOKEN_FILE = 'src/app/utils/token.json'
        SCOPES = ['https://www.googleapis.com/auth/drive']
        CLIENT_FILE = 'src/app/utils/client_secret.json'

        if os.path.exists(TOKEN_FILE):
            creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

        if not creds or not creds.valid:
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_FILE, SCOPES)
            creds = flow.run_local_server(
                bind_addr='127.0.0.1', 
                port=9090, 
                access_type='offline', 
                prompt='consent',
                timeout_seconds=120
            )
            with open(TOKEN_FILE, 'w') as token:
                token.write(creds.to_json())

        response = {'status': True, 'message': 'Authentication successful'}
    except GoogleAuthError as e:
        response = {'status': False, 'message': f'Google authentication error: {e}'}
    except Exception as e:
        response = {'status': False, 'message': f'An unexpected error occurred: {e}'}

    return response