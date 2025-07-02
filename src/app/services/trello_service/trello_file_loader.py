import os
import asyncio
import httpx
from dotenv import load_dotenv
from typing import List, Dict, Any, Optional

load_dotenv()
from langchain_core.documents import Document

from src.app.utils.trello_utils import (
    build_log_text,
    build_user_text,
    build_card_text,
    build_member_text,
    get_trello_user_board,
    get_trello_user,
    get_trello_members,
)

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
        user_response = await get_trello_user(trello_api, user_token)
        if user_response:
            text = build_user_text(user_response)
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
        members_lists = await get_trello_members(trello_board_documents, trello_api, user_token)
        for members_response in members_lists:
            for member in members_response:
                text = build_member_text(member)
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
        board_id = await get_trello_user_board(trello_api, user_token)
        print(f"Board ids {board_id}")
        return board_id
    except Exception as e:
        return e        

async def load_trello_documents(ait_id, logger=None):
    trello_api = os.getenv("TRELLO_API_KEY")
    user_token = os.getenv("TRELLO_USER_TOKEN")
    trello_board_documents = await load_trello_boards(
        trello_api=trello_api,
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