import os
import logging
from openai import AsyncOpenAI
from dotenv import load_dotenv
load_dotenv(override=True)

api_key = os.getenv("OPENAI_API_KEY")
client = AsyncOpenAI(api_key=api_key)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("call_llm.log"),
        logging.StreamHandler()
    ]
)

async def call_chatgpt(system_prompt:str, user_query:str):
    try:
        logging.info("Starting to generate system prompt.")
        
        # Ensure the API key is set
        if not api_key:
            logging.error("OpenAI API key is not set in the environment variables.")
            raise ValueError("OpenAI API key is not set in the environment variables.")

        # Call the OpenAI API to generate the prompt asynchronously
        logging.info("Calling OpenAI API to generate the prompt.")
        completion = await client.chat.completions.create(
            model="gpt-4.1",
            messages=[
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": user_query,
                },
            ],
        )

        prompt = completion.choices[0].message.content
        logging.info("Prompt successfully generated.")

        return {'status': True, 'prompt': prompt}

    except ValueError as ve:
        logging.error(f"ValueError occurred: {str(ve)}")
        return {'status': False, 'message': str(ve)}

    except FileNotFoundError as fnfe:
        logging.error(f"FileNotFoundError occurred: {str(fnfe)}")
        return {'status': False, 'message': f"File error: {str(fnfe)}"}

    except Exception as e:
        logging.error(f"An unexpected error occurred: {str(e)}")
        return {'status': False, 'message': f"An unexpected error occurred: {str(e)}"}