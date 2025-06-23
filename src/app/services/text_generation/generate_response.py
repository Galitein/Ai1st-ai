import os
import logging
import asyncio
from dotenv import load_dotenv
from openai import AsyncOpenAI

from src.app.utils.prompts import system_prompt
from src.app.services.text_processing.vector_search import search

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

        # Load the system prompt
        prompt = system_prompt.SYSTEM_PROMPT
        logging.info("System prompt loaded successfully.")

        extracted_bib = await search(
            ait_id=ait_id,
            query=query,
            qdrant_collection="bib",
            limit=3,
            similarity_threshold=0.1
        )
        print(f"Extracted bib: {extracted_bib}")
        if not extracted_bib.get("status"):
            logging.error("No results found for the query.")
            return {'status': False, 'message': "No results found for the query."}
        
        extracted_log = await search(
            ait_id=ait_id,
            query=query,
            qdrant_collection="log",
            limit=8,
            similarity_threshold=0.5
        )
        print(f"Extracted log: {extracted_log}")
        if not extracted_log.get("status"):
            logging.error("No results found for the query.")
            return {'status': False, 'message': "No results found for the query."}

        context_results = extracted_bib.get("results", []) + extracted_log.get("results", [])
        context_text = "\n\n".join(
                f"File: {r.get('file_name', '')}\nContent: {r.get('page_content', '')}"
                for r in context_results
            )
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