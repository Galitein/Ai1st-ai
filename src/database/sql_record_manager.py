import os
from dotenv import load_dotenv
import sqlite3
from langchain.indexes import SQLRecordManager

load_dotenv()

SQL_DB_PATH = os.getenv("SQLITE_DB_PATH", "file_tracking.db") 

def sql_record_manager(namespace:str, sqlite_db_path=None):
    if sqlite_db_path is None:
        sqlite_db_path = SQL_DB_PATH
    record_manager = SQLRecordManager(
        namespace=namespace, 
        db_url="sqlite:////opt/sqlite3/ai1st_customgpt.db"
    )
    record_manager.create_schema()
    return record_manager

def get_all_source_ids(namespace):
    """
    Returns a list of all source_ids for the given namespace.
    """
    conn = sqlite3.connect(SQL_DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT group_id FROM upsertion_record WHERE namespace = ?", (namespace,)
    )
    rows = cursor.fetchall()
    column_names = [description[0] for description in cursor.description]
    conn.close()

    return [row[0] for row in rows]

def delete_source_ids(namespace, group_ids):
    """
    Delete records from upsertion_record table for the given namespace and list of group_ids.
    """
    conn = sqlite3.connect(SQL_DB_PATH)
    cursor = conn.cursor()
    for gid in group_ids:
        cursor.execute(
            "DELETE FROM upsertion_record WHERE namespace = ? AND group_id = ?",
            (namespace, gid)
        )
    conn.commit()
    conn.close()