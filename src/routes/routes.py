import os
import json
import logging

from typing import Literal, List, Optional
from dotenv import load_dotenv
from fastapi import (
    APIRouter, 
    HTTPException, 
    Request, 
    UploadFile, 
    File, 
    Form,
    Body,
    responses
)

load_dotenv()


from src.app.services.text_processing import (
    vector_search,
    delete_embeddings,
    create_embeddings,
    create_embedding_urls
)

from src.app.services.text_generation import (
    generate_prompt,
    generate_response
)

from src.app.models.input_models import (
    FileNamesInput,
    QueryInput,
    TaskOrPromptInput,
    ChatInput,
    CreateIndexingInput
)

router = APIRouter()

CREDENTIALS_PATH = os.getenv("CREDENTIALS_PATH", "credentials.json")

@router.get("/")
async def root():
    return {"message": "Welcome to the Uvicorn App"}

@router.post("/create_embeddings")
async def build_index(
    input_data: CreateIndexingInput
):
    """
    Creates embeddings for the provided documents and builds an index.
    """
    try:
        response = await create_embeddings.process_and_build_index(
            ait_id=input_data.ait_id, 
            documents=input_data.documents
        )
        if not response.get("status"):
            return responses.JSONResponse(
                status_code=400,
                content={
                    "status": False,
                    "message": response.get("message")
                }
            )
        return response
    except Exception as e:
        return responses.JSONResponse(
            status_code=500,
            content={
                "status": False,
                "message": f"Error creating embeddings: {str(e)}"
            }
        )

@router.post("/create_embeddings_urls")
async def build_index_urls(
    file_urls: List[str],
    ait_id: str,
    document_collection: str
    ):
    response = await create_embedding_urls.create_embedding_urls(
        ait_id=ait_id, 
        file_urls=file_urls,
        document_collection=document_collection
    )
    return response

@router.post("/search")
async def search_route(input_data: QueryInput):
    """
    Searches the index for the given query and returns ranked results.
    """
    response = await vector_search.search(
        ait_id=input_data.ait_id, 
        query=input_data.query, 
        document_collection=input_data.document_collection, 
        limit=input_data.limit, 
        similarity_threshold=input_data.similarity_threshold
    )  
    if not response.get('status'):
        return responses.JSONResponse(
            status_code=400,
            content={
                "status": False,
                "message": "No results found."
            }
        )
    return response

@router.post("/desc_sys_prompt")
async def prompt_generator(input_data: TaskOrPromptInput):
    """
    Generates a system prompt based on the provided task or existing prompt.
    """
    response = await generate_prompt.generate_system_prompt(input_data.ait_id, input_data.task_or_prompt)  # should be async
    if response.get('status') == 'failed':
        return responses.JSONResponse(
            status_code=400,
            content={
                "status": False,
                "message": response.get('message')
            }
        )
    return response

@router.post("/delete_embeddings")
async def delete_index(input_data: FileNamesInput):
    """
    Deletes all vectors and records for a specific file (all chunks) in Qdrant and SQLRecordManager.
    """
    try:
        delete_response = await delete_embeddings.delete_file_index(
            input_data.ait_id, 
            input_data.file_names,
            input_data.document_collection
        )
        if not delete_response.get("status"):
            return responses.JSONResponse(
                status_code=400,
                content={
                    "status": False,
                    "message": delete_response.get("message", "Failed to delete embeddings")
                }
            )
        return delete_response
    except Exception as e:
        return responses.JSONResponse(
            status_code=500,
            content={
                "status": False,
                "message": f"Error deleting embeddings: {str(e)}"
            }
        )

@router.post("/chat")
async def generate_query_response(input_data: ChatInput):
    """
    Generates a response based on the user's query using the system prompt.
    """
    response = await generate_response.generate_chat_completion(
        input_data.ait_id, 
        input_data.query
    )
    if not response.get('status'):
        return responses.JSONResponse(
            status_code=400,
            content={
                "status": False,
                "message": response.get('message')
            }
        )
    return response