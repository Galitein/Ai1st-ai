import os
import asyncio
import httpx
from dotenv import load_dotenv
from src.app.services.trello_service.trello_utils import get_trello_api_key, get_trello_token
load_dotenv()

from langchain_core.documents import Document

def build_log_text(log):
    """
    Build a rich, human-readable string from a Trello log entry,
    including all relevant nested keys from the 'data' section.
    """
    parts = []
    data = log.get("data", {})

    # Top-level action type
    if log.get("type"):
        parts.append(f"Action: {log['type']}")

    # idCard
    if data.get("idCard"):
        parts.append(f"Card ID: {data['idCard']}")

    # text (comment or description)
    if data.get("text"):
        parts.append(f"Text: {data['text']}")

    # textData (e.g., emoji)
    if data.get("textData"):
        parts.append(f"TextData: {data['textData']}")

    # card details
    card = data.get("card", {})
    if card:
        card_str = ", ".join([f"{k}: {v}" for k, v in card.items()])
        parts.append(f"Card: {card_str}")

    # board details
    board = data.get("board", {})
    if board:
        board_str = ", ".join([f"{k}: {v}" for k, v in board.items()])
        parts.append(f"Board: {board_str}")

    # list details
    lst = data.get("list", {})
    if lst:
        list_str = ", ".join([f"{k}: {v}" for k, v in lst.items()])
        parts.append(f"List: {list_str}")

    # old (previous values for update actions)
    old = data.get("old", {})
    if old:
        old_str = ", ".join([f"{k}: {v}" for k, v in old.items()])
        parts.append(f"Old: {old_str}")

    # listBefore and listAfter
    list_before = data.get("listBefore", {})
    if list_before:
        before_str = ", ".join([f"{k}: {v}" for k, v in list_before.items()])
        parts.append(f"ListBefore: {before_str}")
    list_after = data.get("listAfter", {})
    if list_after:
        after_str = ", ".join([f"{k}: {v}" for k, v in list_after.items()])
        parts.append(f"ListAfter: {after_str}")

    # checklist
    checklist = data.get("checklist", {})
    if checklist:
        checklist_str = ", ".join([f"{k}: {v}" for k, v in checklist.items()])
        parts.append(f"Checklist: {checklist_str}")

    # attachment
    attachment = data.get("attachment", {})
    if attachment:
        attachment_str = ", ".join([f"{k}: {v}" for k, v in attachment.items()])
        parts.append(f"Attachment: {attachment_str}")

    # desc (card description)
    if data.get("desc"):
        parts.append(f"Description: {data['desc']}")

    # pos (card/list position)
    if data.get("pos"):
        parts.append(f"Position: {data['pos']}")

    # dueComplete
    if data.get("dueComplete") is not None:
        parts.append(f"DueComplete: {data['dueComplete']}")

    # dateCompleted
    if data.get("dateCompleted"):
        parts.append(f"DateCompleted: {data['dateCompleted']}")

    # idList
    if data.get("idList"):
        parts.append(f"List ID: {data['idList']}")

    # idMember
    if data.get("idMember"):
        parts.append(f"Member ID: {data['idMember']}")

    # name (card/list/board/checklist/member)
    if data.get("name"):
        parts.append(f"Name: {data['name']}")

    # member details (for addMemberToCard, etc.)
    member = data.get("member", {})
    if member:
        member_str = ", ".join([f"{k}: {v}" for k, v in member.items()])
        parts.append(f"Member: {member_str}")

    # memberCreator (who performed the action)
    member_creator = log.get("memberCreator", {})
    if member_creator.get("fullName"):
        parts.append(f"By: {member_creator['fullName']}")
    if member_creator.get("username"):
        parts.append(f"Username: {member_creator['username']}")

    # date (when the action occurred)
    if log.get("date"):
        parts.append(f"Date: {log['date']}")

    return " | ".join(parts)

def build_user_text(user_data):
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

def build_card_text(card_data):
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

def build_member_text(member_data):
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
    # Add more fields if your member data includes them
    return " | ".join(parts)

async def load_trello_log(ait_id, document_collection, trello_board_documents,trello_api, user_token):
    """
    Converts Trello logs to a list of Document objects for embedding.
    Each chunk gets the log's id as source_id.
    """
    documents = []
    try:
        for board_id in trello_board_documents:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"https://trello.com/1/boards/{board_id}/actions?key={trello_api}&token={user_token}")
                response.raise_for_status()
                logs = response.json()
                if asyncio.iscoroutine(logs):
                    logs = await logs
                for log in logs:
                    text = build_log_text(log)
                    # print(text)
                    documents.append(
                        Document(
                            page_content=text.strip(),
                            metadata={
                                "ait_id": ait_id,
                                "type": document_collection,
                                "source_id": log.get("id"),
                                "card_id": log.get("data", {}).get("idCard"),
                                "card_name": log.get("data", {}).get("card", {}).get("name"),
                                "board_id": log.get("data", {}).get("board", {}).get("id"),
                                "board_name": log.get("data", {}).get("board", {}).get("name"),
                                "list_id": log.get("data", {}).get("list", {}).get("id"),
                                "list_name": log.get("data", {}).get("list", {}).get("name"),
                                "member_creator": log.get("memberCreator", {}).get("fullName"),
                                "date": log.get("date"),
                            }
                        )
                        )
    except Exception as e:
        print(f"Error loading Trello logs: {e}")
    return documents

async def load_trello_user(ait_id, document_collection, trello_api, user_token):
    """
    Converts Trello user to a list of Document objects for embedding.
    Each chunk gets the user's id as source_id.
    """
    documents = []
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"https://trello.com/1/members/me?key={trello_api}&token={user_token}")
            response.raise_for_status()
            user_response = response.json()
            if asyncio.iscoroutine(user_response):
                user_response = await user_response
            text = build_user_text(user_response)
            # print(text)
            documents.append(
                Document(
                    page_content=text.strip(),
                    metadata={
                        "ait_id": ait_id,
                        "type": document_collection,
                        "source_id": user_response.get("id"),
                        "full_name": user_response.get("fullName"),
                        "username": user_response.get("username"),
                        "email": user_response.get("email"),
                        "bio": user_response.get("bio"),
                        "url": user_response.get("url"),
                    }
                )
            )
    except Exception as e:
        print(f"Error loading Trello user: {e}")
    return documents

async def load_trello_card(ait_id, document_collection, trello_board_documents, trello_api, user_token):
    """
    Converts Trello cards to a list of Document objects for embedding.
    Each chunk gets the card's id as source_id.
    """
    documents = []
    try:
        for board_id in trello_board_documents:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"https://trello.com/1/boards/{board_id}/cards?key={trello_api}&token={user_token}")
                response.raise_for_status()
                cards_response = response.json()
                if asyncio.iscoroutine(cards_response):
                    cards_response = await cards_response
                for card in cards_response:
                    text = build_card_text(card)
                    # print(text)
                    documents.append(
                        Document(
                            page_content=text.strip(),
                            metadata={
                                "ait_id": ait_id,
                                "type": document_collection,
                                "source_id": card.get("id"),
                                "card_id": card.get("id"),
                                "card_name": card.get("name"),
                                "board_id": card.get("idBoard"),
                                "list_id": card.get("idList"),
                                "date_last_activity": card.get("dateLastActivity"),
                                "due": card.get("due"),
                                "due_complete": card.get("dueComplete"),
                                "short_url": card.get("shortUrl"),
                            }
                        )
                    )
        print(f"length of board cards {len(documents)}")
    except Exception as e:
        print(f"Error loading Trello cards: {e}")
    return documents

async def load_trello_member(ait_id, document_collection, trello_board_documents, trello_api, user_token):
    """
    Converts Trello members to a list of Document objects for embedding.
    Each chunk gets the member's id as source_id.
    """
    documents = []
    try:
        for board_id in trello_board_documents:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"https://trello.com/1/boards/{board_id}/members?key={trello_api}&token={user_token}")
                response.raise_for_status()
                members_response = response.json()
                if asyncio.iscoroutine(members_response):
                    members_response = await members_response
                for member in members_response:
                    text = build_member_text(member)
                    # print(text)
                    documents.append(
                        Document(
                            page_content=text.strip(),
                            metadata={
                                "ait_id": ait_id,
                                "type": document_collection,
                                "source_id": member.get("id"),
                                "members_name": member.get("fullName"),
                                "members_username": member.get("username")
                            }
                        )
                    )
        print(f"length of board members {len(documents)}")
    except Exception as e:
        print(f"Error loading Trello members: {e}")
    return documents

async def load_trello_boards(trello_api, user_token):
    try:
        board_id = []
        async with httpx.AsyncClient() as client:
            response = await client.get(f"https://trello.com/1/members/me/boards?key={trello_api}&token={user_token}")
            response.raise_for_status()
            boards = response.json()
            for board in boards:
                board_url = board.get("shortLink")
                board_id.append(board_url)
        print(f"Board ids {board_id}")
        return board_id
    except Exception as e:
        return e        

async def load_trello_documents(ait_id, logger=None):
    trello_api = await get_trello_api_key()
    user_token = await get_trello_token(ait_it=ait_id)
    trello_board_documents = await load_trello_boards(
        trello_api = trello_api,
        user_token=user_token
    )
    trello_user_documents = await load_trello_user(
        ait_id=ait_id,
        document_collection="trello_user",
        trello_api=trello_api,
        user_token=user_token
    )
    print(f"Loaded {len(trello_user_documents)} Trello user documents.")
    trello_card_documents = await load_trello_card(
        ait_id=ait_id,
        document_collection="trello_card",
        trello_board_documents=trello_board_documents,
        trello_api=trello_api,
        user_token=user_token
    )
    print(f"Loaded {len(trello_card_documents)} Trello card documents.")
    trello_log_documents = await load_trello_log(
        ait_id=ait_id,
        document_collection="trello_log",
        trello_board_documents=trello_board_documents,
        trello_api=trello_api,
        user_token=user_token
    )
    print(f"Loaded {len(trello_log_documents)} Trello log documents.")
    trello_member_documents = await load_trello_member(
        ait_id=ait_id,
        document_collection="trello_member",
        trello_board_documents=trello_board_documents,
        trello_api=trello_api,
        user_token=user_token
    )
    print(f"Loaded {len(trello_member_documents)} Trello member documents.")
    
    trello_documents = trello_user_documents + trello_card_documents + trello_log_documents + trello_member_documents
    
    print(f"Total Trello documents loaded: {len(trello_user_documents) + len(trello_card_documents) + len(trello_log_documents) + len(trello_member_documents)}")
    return trello_documents