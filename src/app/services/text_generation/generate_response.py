import os
import json
import logging
from dotenv import load_dotenv
from openai import AsyncOpenAI
from src.database.sql import AsyncMySQLDatabase

from src.app.services.text_processing.vector_search import search
from src.app.services.trello_service.trello_document_search import search_trello_documents

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("generate_response.log"),
        logging.StreamHandler()
    ]
)

# Load environment variables
load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")

# Initialize OpenAI async client
client = AsyncOpenAI(api_key=api_key)

db = AsyncMySQLDatabase()


async def generate_chat_completion(ait_id:str, query:str):
    """
    Generate a chat completion using OpenAI's API.

    Args:
        query (str): The user's query.

    Returns:
        dict: A dictionary containing the status and the generated response.
    """
    try:
        logging.info("Starting chat completion generation.")

        await db.create_pool()
        response = await db.select(table = "custom_gpts", columns="sys", where = f"id = '{ait_id}'", limit=1)
        await db.close_pool()

        if not response or "sys" not in response[0]:
            logging.error(f"SYS not found for ait id : {ait_id}")
            raise Exception("SYS not defined or invalid ait id")
        else:
            prompt = response[0].get("sys", "")
        
        logging.info("System prompt loaded successfully.")

        extracted_bib = await search(
            ait_id=ait_id,
            query=query,
            document_collection="bib",
            limit=3,
            similarity_threshold=0.1
        )
        if not extracted_bib.get("status"):
            logging.error("No results found for the query.")
            return {'status': False, 'message': "No results found for the query."}
        
        extracted_log = await search(
            ait_id=ait_id,
            query=query,
            document_collection="log",
            limit=8,
            similarity_threshold=0.5
        )
        if not extracted_log.get("status"):
            logging.error("No results found for the query.")
            return {'status': False, 'message': "No results found for the query."}
        
        extract_trello_data = await search_trello_documents(query, ait_id)

        context_results = extracted_bib.get("results", []) + extracted_log.get("results", []) + extract_trello_data
        context_text = "\n\n".join(
                f"File: {r.get('file_name', '')}\nContent: {r.get('page_content', '')}"
                for r in context_results
            )
        # context_text = 
        # print(f"Context text: {context_text}")
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": context_text},
            {"role": "user", "content": query}
        ]
        logging.info("Conversation history prepared.")

        # Call OpenAI's ChatCompletion API asynchronously
        logging.info("Calling OpenAI's ChatCompletion API.")
        response = await client.chat.completions.create(
            model="gpt-4.1",
            messages=messages,
            temperature=0.3,
            max_tokens=200
        )

        # Extract and return the generated response
        chat_response = response.choices[0].message
        logging.info("Chat completion generated successfully.")
        return {'status': True, 'message': chat_response}

    except Exception as e:
        # Handle exceptions and return an error message
        logging.error(f"An error occurred: {str(e)}")
        return {'status': False, 'message': f"An error occurred: {str(e)}"}