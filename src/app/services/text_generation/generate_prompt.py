import os
import logging
import asyncio
from openai import AsyncOpenAI

from src.app.utils.prompts import meta_prompt
META_PROMPT = meta_prompt.META_PROMPT

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("generate_prompt.log"),
        logging.StreamHandler()
    ]
)

api_key = os.getenv("OPENAI_API_KEY")
client = AsyncOpenAI(api_key=api_key)


async def generate_system_prompt(ait_id: str, task_or_prompt: str):
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
                    "content": META_PROMPT,
                },
                {
                    "role": "user",
                    "content": "Task, Goal, or Current Prompt:\n" + task_or_prompt,
                },
            ],
        )

        # Extract the generated prompt
        prompt = completion.choices[0].message.content
        logging.info("Prompt successfully generated.")

        # Write the prompt to a file
        file_name = f"{ait_id}_system_prompt.py"
        file_path = os.path.join('src/app/utils/prompts', file_name)
        with open(file_path, 'w') as file:
            file.write(f'SYSTEM_PROMPT = """{prompt}"""\n')
        logging.info(f"Prompt written to file: {file_path}")

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