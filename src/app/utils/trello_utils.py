import json
import re
import httpx
import asyncio

async def get_trello_user_board(api_key, token):
    board_ids = []
    url = f"https://trello.com/1/members/me/boards?key={api_key}&token={token}"
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            response.raise_for_status()
            boards = response.json()
            # boards is likely a list of board objects
            for board in boards:
                board_id = board.get("id")
                if board_id:
                    board_ids.append(board_id)
    except Exception as e:
        print(f"Error fetching Trello user boards: {e}")
    return board_ids

async def get_trello_user(api_key, token):
    url = f"https://trello.com/1/members/me?key={api_key}&token={token}"
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            response.raise_for_status()
            trello_user = response.json()
            return trello_user
    except Exception as e:
        print(f"Error fetching Trello user: {e}")
        return None

async def get_trello_members(board_ids, api_key, token):
    trello_members = []
    try:
        for board_id in board_ids:
            url = f"https://trello.com/1/boards/{board_id}/members?key={api_key}&token={token}"
            async with httpx.AsyncClient() as client:
                response = await client.get(url)
                response.raise_for_status()
                trello_members.append(response.json())
    except Exception as e:
        print(f"Error fetching Trello board members: {e}")
    return trello_members

def read_metadata(filepath):
    try:
        with open(filepath, "r") as file:
            return file.read().strip()
    except Exception as e:
        print(f"Error reading metadata file: {e}")
        return ""

def trello_extract_entities_prompt(user_data, members_data, trello_log_metadata, query):

    return f"""
# Trello Query Information Extractor

You are an assistant that extracts structured information from Trello user queries.

## User Context
The user asking this query is:

{user_data}

## Trello Members Context
The members of the Trello board are:

{members_data}


If the query mentions "me", "my", or "I", interpret these as referring to the user above.

## Instructions
Given the following user query and Trello log metadata keys, extract the relevant entities and output a JSON object using only the provided keys from the metadata.

**Trello log metadata keys:**

{trello_log_metadata}


**User query:**

{query}


## Output Requirements
- Output only a valid JSON object, with no extra text or explanation. 
- Use only the keys provided in the Trello log metadata.
- Use the user's Trello identity (Rohan Harchandani, username: rohanharchandani, id: 68495242c5aa3b9cb5c6bdf9) for any references to "me", "my", or "I" in the query.
- Include only the metadata keys that are relevant to answering the user's specific query.

## Examples

### Example 1: Who is assigned to the card "Sample Card"?

{{
  "type": "addMemberToCard",
  "date": "2025-06-26T09:00:00.000Z",
  "data": {{
    "card": {{
      "id": "card123",
      "name": "Sample Card"
    }},
    "member": {{
      "id": "member_id_3",
      "fullName": "Member Three",
      "username": "memberthree"
    }}
  }}
}}


### Example 2: Who moved the card "Sample Card" to the backlog?

{{
  "type": "updateCard",
  "date": "2025-06-26T07:05:45.697Z",
  "data": {{
    "card": {{
      "id": "card123",
      "name": "Sample Card"
    }},
    "listBefore": {{
      "id": "list_todo",
      "name": "To Do"
    }},
    "listAfter": {{
      "id": "list_backlog",
      "name": "Backlog"
    }}
  }},
  "memberCreator": {{
    "fullName": "Member One",
    "username": "memberone"
  }}
}}


### Example 3: What cards are in the "Backlog" list?

{{
  "type": "createCard",
  "date": "2025-06-26T07:51:32.297Z",
  "data": {{
    "card": {{
      "id": "card123",
      "name": "Sample Card",
      "idShort": 22,
      "shortLink": "abc123"
    }},
    "list": {{
      "id": "list_backlog",
      "name": "Backlog"
    }},
    "board": {{
      "id": "board001",
      "name": "Project Board",
      "shortLink": "proj001"
    }}
  }},
  "memberCreator": {{
    "fullName": "Member One",
    "username": "memberone"
  }}
}}


### Example 4: Show all comments on the card "Sample Card".

{{
  "type": "commentCard",
  "date": "2025-06-26T08:00:00.000Z",
  "data": {{
    "card": {{
      "id": "card123",
      "name": "Sample Card"
    }},
    "text": "This is a comment on the card."
  }},
  "memberCreator": {{
    "fullName": "Member Two",
    "username": "membertwo"
  }}
}}


### Example 5: Who was removed from the card "Sample Card"?

{{
  "type": "removeMemberFromCard",
  "date": "2025-06-26T10:00:00.000Z",
  "data": {{
    "card": {{
      "id": "card123",
      "name": "Sample Card"
    }},
    "member": {{
      "id": "member_id_4",
      "fullName": "Member Four",
      "username": "memberfour"
    }}
  }},
  "memberCreator": {{
    "fullName": "Member One",
    "username": "memberone"
  }}
}}


### Example 6: What attachments are on the card "Sample Card"?
{{
  "type": "addAttachmentToCard",
  "date": "2025-06-26T06:36:39.249Z",
  "data": {{
    "card": {{
      "id": "card123",
      "name": "Sample Card"
    }},
    "attachment": {{
      "id": "attach001",
      "name": "SampleAttachment.pdf",
      "url": "https://trello.com/1/cards/card123/attachments/attach001/download/SampleAttachment.pdf"
    }}
  }}
}}


### Example 7: What checklist items were marked complete on "Sample Card"?
{{
  "type": "updateCheckItemStateOnCard",
  "date": "2025-06-26T11:00:00.000Z",
  "data": {{
    "card": {{
      "id": "card123",
      "name": "Sample Card"
    }},
    "checklist": {{
      "id": "checklist001",
      "name": "Sample Checklist"
    }},
    "checkItem": {{
      "id": "checkitem001",
      "name": "Sample Item",
      "state": "complete"
    }}
  }},
  "memberCreator": {{
    "fullName": "Member Two",
    "username": "membertwo"
  }}
}}


### Example 8: What lists are present on the "Project Board"?

{{
  "type": "updateList",
  "date": "2025-06-26T12:00:00.000Z",
  "data": {{
    "board": {{
      "id": "board001",
      "name": "Project Board"
    }},
    "list": {{
      "id": "list_backlog",
      "name": "Backlog"
    }}
  }},
  "memberCreator": {{
    "fullName": "Member One",
    "username": "memberone"
  }}
}}

"""

    
def extract_json_from_response(content):
    try:
        # Try to parse the whole content first
        return json.loads(content)
    except Exception:
        pass  # fallback to regex below

    try:
        # Try to find a JSON array first
        array_match = re.search(r'\[\s*{[\s\S]*}\s*\]', content)
        if array_match:
            json_str = array_match.group(0)
            return json.loads(json_str)
        # Otherwise, try to find all JSON objects and parse as a list
        objects = re.findall(r'\{[\s\S]*?\}', content)
        if len(objects) > 1:
            json_str = "[" + ",".join(objects) + "]"
            return json.loads(json_str)
        elif len(objects) == 1:
            return json.loads(objects[0])
        else:
            print("No JSON object found in response content.")
            return None
    except Exception as e:
        print(f"Error decoding JSON from response: {e}")
        return None


# def build_log_text(log: dict) -> str:
#     """
#     Build a rich, human-readable string from a Trello log entry,
#     including all relevant nested keys from the 'data' section.
#     """
#     parts = []
#     data = log.get("data", {})

#     if log.get("type"):
#         parts.append(f"Action: {log['type']}")

#     if data.get("idCard"):
#         parts.append(f"Card ID: {data['idCard']}")

#     if data.get("text"):
#         parts.append(f"Text: {data['text']}")

#     if data.get("textData"):
#         parts.append(f"TextData: {data['textData']}")

#     card = data.get("card", {})
#     if card:
#         card_str = ", ".join([f"{k}: {v}" for k, v in card.items()])
#         parts.append(f"Card: {card_str}")

#     board = data.get("board", {})
#     if board:
#         board_str = ", ".join([f"{k}: {v}" for k, v in board.items()])
#         parts.append(f"Board: {board_str}")

#     lst = data.get("list", {})
#     if lst:
#         list_str = ", ".join([f"{k}: {v}" for k, v in lst.items()])
#         parts.append(f"List: {list_str}")

#     old = data.get("old", {})
#     if old:
#         old_str = ", ".join([f"{k}: {v}" for k, v in old.items()])
#         parts.append(f"Old: {old_str}")

#     list_before = data.get("listBefore", {})
#     if list_before:
#         before_str = ", ".join([f"{k}: {v}" for k, v in list_before.items()])
#         parts.append(f"ListBefore: {before_str}")
#     list_after = data.get("listAfter", {})
#     if list_after:
#         after_str = ", ".join([f"{k}: {v}" for k, v in list_after.items()])
#         parts.append(f"ListAfter: {after_str}")

#     checklist = data.get("checklist", {})
#     if checklist:
#         checklist_str = ", ".join([f"{k}: {v}" for k, v in checklist.items()])
#         parts.append(f"Checklist: {checklist_str}")

#     attachment = data.get("attachment", {})
#     if attachment:
#         attachment_str = ", ".join([f"{k}: {v}" for k, v in attachment.items()])
#         parts.append(f"Attachment: {attachment_str}")

#     if data.get("desc"):
#         parts.append(f"Description: {data['desc']}")

#     if data.get("pos"):
#         parts.append(f"Position: {data['pos']}")

#     if data.get("dueComplete") is not None:
#         parts.append(f"DueComplete: {data['dueComplete']}")

#     if data.get("dateCompleted"):
#         parts.append(f"DateCompleted: {data['dateCompleted']}")

#     if data.get("idList"):
#         parts.append(f"List ID: {data['idList']}")

#     if data.get("idMember"):
#         parts.append(f"Member ID: {data['idMember']}")

#     if data.get("name"):
#         parts.append(f"Name: {data['name']}")

#     member = data.get("member", {})
#     if member:
#         member_str = ", ".join([f"{k}: {v}" for k, v in member.items()])
#         parts.append(f"Member: {member_str}")

#     member_creator = log.get("memberCreator", {})
#     if member_creator.get("fullName"):
#         parts.append(f"By: {member_creator['fullName']}")
#     if member_creator.get("username"):
#         parts.append(f"Username: {member_creator['username']}")

#     if log.get("date"):
#         parts.append(f"Date: {log['date']}")

#     return " | ".join(parts)

def flatten_dict(d, parent_key='', sep='.'):
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        elif isinstance(v, list):
            if v and isinstance(v[0], dict):
                for idx, item in enumerate(v):
                    items.extend(flatten_dict(item, f"{new_key}[{idx}]", sep=sep).items())
            else:
                items.append((new_key, v))
        else:
            items.append((new_key, v))
    return dict(items)

def build_log_text(log: dict) -> str:
    """
    Build a rich, human-readable string from a Trello log entry,
    including all nested keys and values.
    """
    flat = flatten_dict(log)
    return " | ".join([f"{k}: {v}" for k, v in flat.items()])

def build_user_text(user_data: dict) -> str:
    """
    Build a rich, human-readable string from a Trello user data.
    """
    parts = []
    if user_data.get("id"):
        parts.append(f"User ID: {user_data['id']}")
    if user_data.get("fullName"):
        parts.append(f"Full Name: {user_data['fullName']}")
    if user_data.get("username"):
        parts.append(f"Username: {user_data['username']}")
    if user_data.get("email"):
        parts.append(f"Email: {user_data['email']}")
    if user_data.get("bio"):
        parts.append(f"Bio: {user_data['bio']}")
    if user_data.get("url"):
        parts.append(f"Profile URL: {user_data['url']}")

    return " | ".join(parts)

def build_card_text(card_data: dict) -> str:
    """
    Build a concise, human-readable string from a Trello card entry,
    including only essential fields for semantic search.
    """
    parts = []
    parts.append(f"Card Name: {card_data.get('name', '')}")
    parts.append(f"Card ID: {card_data.get('id', '')}")
    parts.append(f"Board ID: {card_data.get('idBoard', '')}")
    parts.append(f"List ID: {card_data.get('idList', '')}")
    parts.append(f"Description: {card_data.get('desc', '')}")
    parts.append(f"Members: {', '.join(card_data.get('idMembers', []))}")
    parts.append(f"Labels: {', '.join(card_data.get('idLabels', []))}")
    parts.append(f"Checklist IDs: {', '.join(card_data.get('idChecklists', []))}")
    parts.append(f"Attachment Cover ID: {card_data.get('idAttachmentCover', '')}")
    parts.append(f"Due: {card_data.get('due', '')}")
    parts.append(f"Due Complete: {card_data.get('dueComplete', False)}")
    parts.append(f"Date Last Activity: {card_data.get('dateLastActivity', '')}")
    parts.append(f"Short URL: {card_data.get('shortUrl', '')}")
    return " | ".join(parts)

def build_member_text(member_data: dict) -> str:
    """
    Build a human-readable string from a Trello member entry.
    """
    parts = []
    if member_data.get("id"):
        parts.append(f"Member ID: {member_data['id']}")
    if member_data.get("fullName"):
        parts.append(f"Full Name: {member_data['fullName']}")
    if member_data.get("username"):
        parts.append(f"Username: {member_data['username']}")
    return " | ".join(parts)
