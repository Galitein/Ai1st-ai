import os
import json
import logging
from dotenv import load_dotenv
from openai import AsyncOpenAI
from src.database.sql import AsyncMySQLDatabase

from src.app.services.text_processing.vector_search import search
from src.app.services.trello_service.trello_document_search import search_trello_documents
from src.app.utils.trello_utils import trello_system_prompt

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
        try:
            await db.create_pool()
            db_response = await db.select(table="custom_gpts", columns="*", where=f"id = '{ait_id}'", limit=1)
            await db.close_pool()
        except Exception as e:
            logging.error(f"Database connection error: {str(e)}")
            return {'status': False, 'message': f"Database connection error: {str(e)}"}

        if not db_response or "sys" not in db_response[0]:
            logging.error(f"SYS not found for ait id : {ait_id}")
            return {'status': False, 'message': "SYS not defined or invalid ait id"}
        else:
            system_prompt = db_response[0].get("sys", "")
            pre_context = db_response[0].get("pre", "")

        
        logging.info("SYS and PRE loaded successfully.")

        # Search in 'bib' collection
        extracted_bib = await search(
            ait_id=ait_id,
            query=query,
            document_collection="bib",
            limit=10,
            similarity_threshold=0.3
        )
        if not extracted_bib.get("status"):
            logging.error(f"No results found for the query in 'bib' collection: {extracted_bib.get('message', '')}")
            return {'status': False, 'message': "No results found for the query in 'bib' collection."}

        # Search in Trello log collection (fix collection name if needed)
        # trello_log_collection = "log_diary"  # <-- Change this if your collection is named differently
        extracted_log = await search(
            ait_id=ait_id,
            query=query,
            document_collection="log_diary",
            limit=20,
            similarity_threshold=0.5
        )
        if not extracted_log.get("status"):
            logging.error(f"No results found for the query in '{trello_log_collection}' collection: {extracted_log.get('message', '')}")
            return {'status': False, 'message': f"No results found for the query in '{trello_log_collection}' collection."}

        # Search Trello documents
        try:
            extract_trello_data = await search_trello_documents(query, ait_id)
            logging.info(f"Extracted Trello data: {extract_trello_data}")
        except Exception as e:
            logging.error(f"Error searching Trello documents: {str(e)}")
            extract_trello_data = {}

        trello_data_item = [v for k, v in extract_trello_data.items()]
        logging.info(f"Trello data items: {trello_data_item}")

        extracted_mse_email = await search(
            ait_id=ait_id,
            query=query,
            document_collection="log_mse_email",
            limit=8,
            similarity_threshold=0.3
            )

        bib_log_context_results = extracted_bib.get("results", []) + extracted_log.get("results", [])
        logging.info(f"Context results: {bib_log_context_results}")

        messages = [
            {"role": "system", "content": f"{system_prompt}\n\n# Trello Data Handling\n{trello_system_prompt()}"},
            {"role": "user", "content": json.dumps(bib_log_context_results, indent=2)},
            {"role": "user", "content": "---BEGIN PERSONAL CONTEXT (PRE)---\n" + json.dumps(pre_context, indent=2) + "\n---END PERSONAL CONTEXT---"},
            {"role": "user", "content": "---BEGIN TRELLO DATA---\n" + json.dumps(trello_data_item, indent=2) + "\n---END TRELLO DATA---"},
            {"role": "user", "content": "---BEGIN EMAIL DATA---\n" + json.dumps(extracted_mse_email, indent=2) + "\n---END EMAIL DATA---"},
            {"role": "user", "content": query}
        ]
        logging.info("Conversation history prepared.")

        # Call OpenAI's ChatCompletion API asynchronously
        logging.info("Calling OpenAI's ChatCompletion API.")
        response = await client.chat.completions.create(
            model="gpt-4.1",
            messages=messages,
            temperature=0.3,
            max_tokens=5000
        )

        # Extract and return the generated response
        chat_response = response.choices[0].message
        logging.info(chat_response)
        logging.info("Chat completion generated successfully.")
        return {'status': True, 'message': chat_response}

    except Exception as e:
        # Handle exceptions and return an error message
        logging.error(f"An error occurred: {str(e)}")
        return {'status': False, 'message': f"An error occurred: {str(e)}"}