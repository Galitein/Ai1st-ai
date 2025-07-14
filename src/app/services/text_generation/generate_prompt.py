import os
import logging
from dotenv import load_dotenv
from datetime import datetime
from openai import AsyncOpenAI

from src.database.sql import AsyncMySQLDatabase
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

load_dotenv(override=True)
DB_HOST = os.getenv("DB_HOST")
DB_PORT = int(os.getenv("DB_PORT"))
DB_USER = os.getenv("DB_USER") 
DB_PASS = os.getenv("DB_PASS") 
DB_NAME = os.getenv("DB_NAME") 
api_key = os.getenv("OPENAI_API_KEY")

db = AsyncMySQLDatabase(
    host=DB_HOST,
    port=DB_PORT,
    user=DB_USER,
    password=DB_PASS,
    database=DB_NAME
)
client = AsyncOpenAI(api_key=api_key)


async def generate_system_prompt(ait_id: str, task_or_prompt: str):
    try:
        logging.info("Starting to generate system prompt.")
        
        # Ensure the API key is set
        if not api_key:
            logging.error("OpenAI API key is not set in the environment variables.")
            return {'status': False, 'message': "OpenAI API key is not set in the environment variables."}

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

        try:
            await db.create_pool()
        except Exception as e:
            return {"status": False, "message": f"Database connection failed: {str(e)}"}

        existing = await db.select_one(
            table="custom_gpts",
            columns="id",
            where="id = %s",
            params=(ait_id,)
        )

        if existing:
            # Update existing record
            update_status = await db.update(
                table="custom_gpts",
                data={
                    "sys": prompt,
                    "updated_at": datetime.utcnow()
                },
                where="id = %s",
                where_params=(ait_id,)
            )

            if not update_status:
                return {"status": False, "message": f"Failed to insert sys into custom_gpts table of {ait_id}"}

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
    finally:
        await db.close_pool()