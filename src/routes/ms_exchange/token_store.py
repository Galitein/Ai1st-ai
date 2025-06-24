import json
from pathlib import Path

TOKEN_FILE = Path("tokens.json")

def save_token(user_id, token_data):
    tokens = load_tokens()
    tokens[user_id] = token_data
    with open(TOKEN_FILE, "w") as f:
        json.dump(tokens, f, indent=4)

def load_tokens():
    if TOKEN_FILE.exists():
        with open(TOKEN_FILE, "r") as f:
            return json.load(f)
    return {}

def get_token(user_id):
    return load_tokens().get(user_id)
