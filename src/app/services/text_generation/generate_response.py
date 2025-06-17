import os
import logging
import asyncio
from dotenv import load_dotenv
from openai import AsyncOpenAI

from src.app.utils.prompts import system_prompt
from src.app.services.text_processing.vector_search import ranksearch, load_index

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

async def generate_chat_completion(query: str):
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

        # Fetch context from the /search endpoint.
        logging.info("Fetching context from the /search endpoint.")
        index = load_index()
        if not index:
            return {'status': False, 'message': "Index not found or failed to load."}
    
        results = ranksearch(index, query)
        if not results.get('status'):
            return {'status': False, 'message': "Index not found or failed to load."}

        # Extract context data
        context_data = results
        context = context_data.get("results", [])
        logging.info("Context fetched and processed successfully.")

        # Combine the context list into a single string
        combined_context = " ".join(context)

        # Prepare the conversation history
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": combined_context},
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
        chat_response = response.choices[0].message.content.strip()
        logging.info("Chat completion generated successfully.")
        return {'status': True, 'message': chat_response}

    except Exception as e:
        # Handle exceptions and return an error message
        logging.error(f"An error occurred: {str(e)}")
        return {'status': False, 'message': f"An error occurred: {str(e)}"}