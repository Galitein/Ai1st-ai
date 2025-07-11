import sys
sys.path.append(".")

import os
import logging
from dotenv import load_dotenv

load_dotenv()

from openai import AsyncOpenAI

from src.app.utils.trello_utils import (
    get_trello_user_board,
    get_trello_user,
    get_trello_members,
    read_metadata,
    trello_extract_entities_prompt,
    extract_json_from_response,
    build_log_text
)

# from 

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TRELLO_API_KEY = os.getenv("TRELLO_API_KEY") #Later fetch from the Database
TRELLO_TOKEN = os.getenv("TRELLO_TOKEN") #Later fetch from the Database
METADATA_FILE_PATH = os.getenv("METADATA_FILE_PATH")

async def trello_query_entities(
    query,
    api_key=TRELLO_API_KEY,
    token=TRELLO_TOKEN,
    openai_api_key=OPENAI_API_KEY,
    metadata_file_path=METADATA_FILE_PATH,
    temperature=0
    ):
    try:
        board_ids = await get_trello_user_board(api_key=api_key, token=token)
        trello_user_data = await get_trello_user(api_key=api_key, token=token)
        trello_board_member_data = await get_trello_members(board_ids=board_ids, api_key=api_key, token=token)
        trello_log_metadata = read_metadata(filepath=metadata_file_path)
        trello_extract_prompt = trello_extract_entities_prompt(
            user_data=[], 
            members_data=trello_board_member_data, 
            trello_log_metadata=trello_log_metadata,
            query=query
        )
        client = AsyncOpenAI(api_key=openai_api_key)
        response = await client.chat.completions.create(
            model="gpt-4.1",
            messages=[
                {"role": "user", "content": trello_extract_prompt}
            ],
            max_tokens=2068,
            temperature=0.3
        )
        content = response.choices[0].message.content
        logging.info(content)
        extracted = extract_json_from_response(content)
        if isinstance(extracted, list):
            result = "\n".join(build_log_text(item) for item in extracted)
        elif isinstance(extracted, dict):
            result = build_log_text(extracted)
        else:
            logging.warning("No valid JSON object or list found.")
            result = None
        return {"status": True, "data": result}
    except Exception as e:
        logging.error(f"Error in trello_query_entities: {e}")
        return {"status": False, "message": str(e)}

# if __name__ == "__main__":
#     import asyncio
#     enitity = asyncio.run(trello_query_entities(query = "What task has been assigned to Kaushal in doing?"))
#     print("....................",enitity)