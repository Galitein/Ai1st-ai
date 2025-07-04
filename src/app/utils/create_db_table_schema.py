import os
import json
import logging
from typing import Dict
from src.database.sql import AsyncMySQLDatabase  

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("create_db_tabe_schema.log"),
        logging.StreamHandler()
    ]
)

def truncate_example(value: str, word_limit: int = 25, char_limit: int = 100) -> str:
    if not value:
        return "None"
    if not isinstance(value, str):
        value = str(value)

    words = value.split()
    if len(words) > word_limit or len(value) > char_limit:
        truncated = ' '.join(words[:word_limit])
        if len(truncated) > char_limit:
            truncated = truncated[:char_limit]
        return truncated.rstrip() + "..."
    return value

async def get_or_create_schema_json(db: AsyncMySQLDatabase = AsyncMySQLDatabase(), 
                                    schema_file_path = "schema.json",
                                    table_name = "user_email_content") -> Dict[str, str]:
    if os.path.exists(schema_file_path):
        logging.info(f"Schema file '{schema_file_path}' found. Loading existing schema.")
        with open(schema_file_path, "r") as f:
            return json.load(f)

    logging.info("Schema file not found. Generating new schema.")
    await db.create_pool()
    logging.info("Database connection pool created.")

    col_query = f"""
        SELECT COLUMN_NAME, DATA_TYPE 
        FROM INFORMATION_SCHEMA.COLUMNS 
        WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
    """
    logging.info(f"Fetching column metadata for table '{table_name}'...")
    columns = await db.execute_query(col_query, (db.database, table_name))

    if not columns:
        logging.error(f"No columns found for table '{table_name}'.")
        raise Exception(f"Failed to fetch columns for table {table_name}")

    logging.info(f"Fetching example row from table '{table_name}'...")
    example_row = await db.select_one(table_name)

    schema = {}
    for col in columns:
        col_name = col['COLUMN_NAME']
        dtype = col['DATA_TYPE']
        example = example_row[col_name] if example_row and col_name in example_row else "None"
        example = truncate_example(example)
        schema[col_name] = f"Dtype = {dtype}, Example = {example}"

    schema = {table_name: schema}
    logging.info(f"Writing schema to '{schema_file_path}'...")
    with open(schema_file_path, "w") as f:
        json.dump(schema, f, indent=2)

    await db.close_pool()
    logging.info("Database connection pool closed.")
    logging.info(f"Schema generation for table '{table_name}' completed.")

    return schema
