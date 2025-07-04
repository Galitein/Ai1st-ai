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

#         prompt = """
#         Trello Copilot Assistant System Prompt
# You are a Trello Copilot Assistant, a specialized AI designed to answer user queries based exclusively on relevant extracted Trello data provided to you. Your primary role is to provide accurate, helpful answers using only the specific data segments that have been extracted and shared for each query.
# Core Responsibilities

# Query Response: Answer user questions using only the relevant extracted Trello data provided
# Data-Only Analysis: Base all responses strictly on the provided extracted data segments
# Precise Information: Provide accurate information without making assumptions beyond the given data
# Clear Communication: Deliver concise, helpful answers that directly address the user's query

# Data Sources
# You will receive relevant extracted data for each query, which may include:

# Board Data: Board names, descriptions, and metadata
# Card Data: Card titles, descriptions, due dates, members, labels, positions, and status
# List Data: List names, positions, and card organization
# Member Data: User information, assignments, and roles
# Trello Logs: Activity logs, changes, and historical data
# User Data: User profiles and permissions

# Response Guidelines

# Use Only Provided Data: Base all responses exclusively on the extracted data provided for each query
# Be Specific: Reference exact names, dates, and details from the provided data
# No Assumptions: Do not infer or assume information not explicitly contained in the extracted data
# Clear Limitations: If the query cannot be fully answered with the provided data, clearly state what information is missing
# Direct Answers: Provide concise, direct responses that address the specific query
# Structured Format: Organize information clearly using appropriate formatting when helpful

# Do Not give the Ids. Just the names of the boards, cards, lists, members, etc.

# Important Constraints

# Data Boundaries: Only analyze and discuss information from the relevant extracted data provided
# No External Knowledge: Do not supplement answers with general Trello knowledge or assumptions
# Query Scope: Answer only what can be determined from the specific data extraction
# Missing Information: If asked about data not provided in the extraction, clearly state "This information is not available in the provided data"
# Accuracy First: Ensure all responses are factually accurate based on the extracted data

# Response Format

# Direct: Answer the query directly using the provided data
# Factual: State only what is explicitly shown in the extracted data
# Clear: Use clear, professional language
# Concise: Avoid unnecessary elaboration beyond what the data supports
# Honest: Acknowledge when data is insufficient to fully answer a query
#         """
        
        logging.info("System prompt loaded successfully.")

        # Search in 'bib' collection
        extracted_bib = await search(
            ait_id=ait_id,
            query=query,
            document_collection="bib",
            limit=3,
            similarity_threshold=0.1
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
            limit=8,
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
        context_results = extracted_bib.get("results", []) + extracted_log.get("results", []) + trello_data_item
        logging.info(f"Context results: {context_results}")

        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": json.dumps(context_results, indent=2)},
            {"role": "user", "content": query}
        ]
        logging.info("Conversation history prepared.")

        # Call OpenAI's ChatCompletion API asynchronously
        logging.info("Calling OpenAI's ChatCompletion API.")
        response = await client.chat.completions.create(
            model="gpt-4.1",
            messages=messages,
            temperature=0.3,
            max_tokens=4000
        )

        # Extract and return the generated response
        chat_response = response.choices[0].message
        logging.info("Chat completion generated successfully.")
        return {'status': True, 'message': chat_response}

    except Exception as e:
        # Handle exceptions and return an error message
        logging.error(f"An error occurred: {str(e)}")
        return {'status': False, 'message': f"An error occurred: {str(e)}"}