import os
import requests
import logging
from dotenv import load_dotenv
from openai import OpenAI
from src.app.utils.prompts import system_prompt

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

# Initialize OpenAI client
client = OpenAI(api_key=api_key)

def generate_chat_completion(query: str):
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

        # Fetch context from the /search endpoint
        logging.info("Fetching context from the /search endpoint.")
        context_response = requests.post(
            "http://127.0.0.1:8000/search",
            json={"query": query}
        )

        if context_response.status_code != 200:
            error_message = context_response.json().get('detail', 'Unknown error')
            logging.error(f"Failed to fetch context: {error_message}")
            return {
                'status': 'error',
                'message': f"Failed to fetch context: {error_message}"
            }

        # Extract context data
        context_data = context_response.json()
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

        # Call OpenAI's ChatCompletion API
        logging.info("Calling OpenAI's ChatCompletion API.")
        response = client.chat.completions.create(
            model="gpt-4.1",
            messages=messages,
            temperature=0.3,
            max_tokens=200,
            top_p=1,
            frequency_penalty=0,
            presence_penalty=0
        )

        # Extract and return the generated response
        chat_response = response.choices[0].message.content.strip()
        logging.info("Chat completion generated successfully.")
        return {'status': 'success', 'message': chat_response}

    except Exception as e:
        # Handle exceptions and return an error message
        logging.error(f"An error occurred: {str(e)}")
        return {
            'status': 'error',
            'message': f"An error occurred: {str(e)}"
        }