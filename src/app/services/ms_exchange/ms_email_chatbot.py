import logging
from src.app.utils.prompts.mse_email_prompts import GENERATE_SQL_QUERY_SYS, GENERATE_EMAIL_RESPONSE_SYS
from src.app.utils.call_llm import call_chatgpt
from src.app.utils.create_db_table_schema import get_or_create_schema_json
from src.database.sql import AsyncMySQLDatabase

db = AsyncMySQLDatabase()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("call_llm.log"),
        logging.StreamHandler()
    ]
)

schema_file_path = "src/app/services/ms_exchange/user_email_content_schema.json"
table_name = "user_email_content"

async def get_schema_data_with_keys():
    logging.info("Fetching or generating schema for table.")
    all_schema = await get_or_create_schema_json(schema_file_path=schema_file_path, table_name=table_name)

    result = ""
    count = 1
    for key in all_schema.keys():
        for col in all_schema[key].keys():
            result += f"{count}. Table Name is {key} and Column Name is {col} schema is {all_schema[key][col]}\n"
        count += 1
        result += "\n\n"
    
    logging.info("Schema formatting complete.")
    return result

async def get_mail_data(ait_id, input_query):
    logging.info(f"Generating SQL for input query with ait_id: {ait_id}")
    
    table_schema = await get_schema_data_with_keys()

    generate_query_sys_prompt = GENERATE_SQL_QUERY_SYS.format(table_schema=table_schema)
    generate_query_user_input = f"Here is the user query : {input_query}\nHere is ait_di : {ait_id}"
    
    response = await call_chatgpt(generate_query_sys_prompt, generate_query_user_input)
    logging.info("SQL generation from LLM completed.")

    if ait_id not in response["prompt"]:
        logging.warning("AIT ID not found in the generated SQL query.")
        return [], response["prompt"]

    logging.info("Executing generated SQL query.")
    await db.create_pool()
    exe_result = await db.execute_query(response["prompt"].strip())
    await db.close_pool()
    logging.info("SQL query execution complete.")

    return exe_result, response["prompt"]

async def main(ait_id, input_query):
    logging.info(f"Handling main workflow for ait_id: {ait_id}")
    
    exe_result, generated_query = await get_mail_data(ait_id, input_query)

    if not exe_result:
        logging.info("No data found for the given query.")
        return "Could not find any data related to this query"

    input_query_context = GENERATE_EMAIL_RESPONSE_SYS.format(
        user_input=input_query, 
        generated_query=generated_query, 
        result=exe_result
    )

    logging.info("Generating final email response using LLM.")
    response_context = await call_chatgpt("", input_query_context)
    logging.info("Email response generation complete.")

    return response_context
