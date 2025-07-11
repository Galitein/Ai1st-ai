import os
import asyncio
import httpx
import logging
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

from src.app.services.trello_service import trello_auth 

async def load_trello_log(ait_id, document_collection, trello_board_documents, trello_api, user_token):
    """
    Converts Trello logs to a list of Document objects for embedding.
    Each chunk gets the log's id as source_id.
    """
    documents = []
    try:
        for board_id in trello_board_documents:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"https://trello.com/1/boards/{board_id}/actions?limit=1000&key={trello_api}&token={user_token}")
                response.raise_for_status()
                logs = response.json()
                logging.info(f"Loaded {len(logs)} logs for board {board_id}")
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
        return {"status": True, "data": documents}
    except Exception as e:
        logging.error(f"Error loading Trello logs: {e}")
        return {"status": False, "message": str(e)}

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
        return {"status": True, "data": documents}
    except Exception as e:
        logging.error(f"Error loading Trello user: {e}")
        return {"status": False, "message": str(e)}

async def load_trello_card(ait_id, document_collection, trello_board_documents, trello_api, user_token):
    """
    Converts Trello cards to a list of Document objects for embedding.
    Each chunk gets the card's id as source_id.
    """
    documents = []
    try:
        for board_id in trello_board_documents:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"https://trello.com/1/boards/{board_id}/cards?limit=1000&key={trello_api}&token={user_token}")
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
        logging.info(f"length of board cards {len(documents)}")
        return {"status": True, "data": documents}
    except Exception as e:
        logging.error(f"Error loading Trello cards: {e}")
        return {"status": False, "message": str(e)}

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
        logging.info(f"length of board members {len(documents)}")
        return {"status": True, "data": documents}
    except Exception as e:
        logging.error(f"Error loading Trello members: {e}")
        return {"status": False, "message": str(e)}

async def load_trello_boards(trello_api, user_token):
    try:
        board_id = await get_trello_user_board(trello_api, user_token)
        logging.info(f"Board ids {board_id}")
        return {"status": True, "data": board_id}
    except Exception as e:
        logging.error(f"Error loading Trello boards: {e}")
        return {"status": False, "message": str(e)}

async def load_trello_documents(ait_id, logger=None):
    try:
        trello_api = os.getenv("TRELLO_API_KEY")
        user_token = await trello_auth.get_token(ait_id)
        if not user_token:
            raise ValueError("User token not found. Please authenticate first.")
        board_result = await load_trello_boards(
            trello_api=trello_api,
            user_token=user_token
        )
        if not board_result["status"]:
            return {"status": False, "message": board_result["message"]}
        trello_board_documents = board_result["data"]

        user_result = await load_trello_user(
            ait_id=ait_id,
            document_collection="trello_user",
            trello_api=trello_api,
            user_token=user_token
        )
        if not user_result["status"]:
            return {"status": False, "message": user_result["message"]}
        trello_user_documents = user_result["data"]
        logging.info(f"Loaded {len(trello_user_documents)} Trello user documents.")

        card_result = await load_trello_card(
            ait_id=ait_id,
            document_collection="trello_card",
            trello_board_documents=trello_board_documents,
            trello_api=trello_api,
            user_token=user_token
        )
        if not card_result["status"]:
            return {"status": False, "message": card_result["message"]}
        trello_card_documents = card_result["data"]
        logging.info(f"Loaded {len(trello_card_documents)} Trello card documents.")

        log_result = await load_trello_log(
            ait_id=ait_id,
            document_collection="trello_log",
            trello_board_documents=trello_board_documents,
            trello_api=trello_api,
            user_token=user_token
        )
        if not log_result["status"]:
            return {"status": False, "message": log_result["message"]}
        trello_log_documents = log_result["data"]
        logging.info(f"Loaded {len(trello_log_documents)} Trello log documents.")

        member_result = await load_trello_member(
            ait_id=ait_id,
            document_collection="trello_member",
            trello_board_documents=trello_board_documents,
            trello_api=trello_api,
            user_token=user_token
        )
        if not member_result["status"]:
            return {"status": False, "message": member_result["message"]}
        trello_member_documents = member_result["data"]
        logging.info(f"Loaded {len(trello_member_documents)} Trello member documents.")

        trello_documents = trello_user_documents + trello_card_documents + trello_log_documents + trello_member_documents
        logging.info(f"Total Trello documents loaded: {len(trello_documents)}")
        return {"status": True, "data": trello_documents}
    except Exception as e:
        logging.error(f"Error loading Trello documents: {e}")
        return {"status": False, "message": str(e)}