import os
import re
import logging
import aiomysql
import sqlparse
from dotenv import load_dotenv
from typing import Dict, List, Any, Optional
from sqlparse.tokens import Keyword, DML, DDL, Comment, Whitespace, Literal, Name

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv(override=True)

DB_HOST = os.getenv("DB_HOST")
DB_PORT = int(os.getenv("DB_PORT"))
DB_USER = os.getenv("DB_USER") 
DB_PASS = os.getenv("DB_PASS") 
DB_NAME = os.getenv("DB_NAME")

class AsyncMySQLDatabase:
    def __init__(self, host: str = DB_HOST,
                port: int = DB_PORT,
                user: str = DB_USER,
                password: str = DB_PASS,
                database: str = DB_NAME):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.database = database
        self.pool = None
    
    async def create_pool(self, minsize: int = 1, maxsize: int = 10):
        """Create connection pool"""
        try:
            self.pool = await aiomysql.create_pool(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                db=self.database,
                minsize=minsize,
                maxsize=maxsize,
                autocommit=True
            )
            logger.info("Database connection pool created successfully")
        except Exception as e:
            logger.error(f"Error creating connection pool: {e}")
            raise
    
    async def close_pool(self):
        """Close connection pool"""
        if self.pool:
            self.pool.close()
            await self.pool.wait_closed()
            logger.info("Database connection pool closed")
    
    async def execute_query(self, query: str, params: tuple = None) -> Optional[List[Dict[str, Any]]]:
        """Execute SELECT query and return results"""
        try:
            async with self.pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    await cursor.execute(query, params)
                    result = await cursor.fetchall()
                    return result
        except Exception as e:
            logger.error(f"Error executing query: {e}")
            raise e

    async def execute_non_query(self, query: str, params: tuple = None) -> bool:
        """Execute INSERT, UPDATE, DELETE queries and return status"""
        try:
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(query, params)
                    return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Error executing non-query: {e}")
            return False
    
    async def execute_many(self, query: str, params_list: List[tuple]) -> bool:
        """Execute multiple queries with different parameters"""
        try:
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.executemany(query, params_list)
                    return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Error executing many queries: {e}")
            return False
    
    # CRUD Operations
    
    async def insert(self, table: str, data: Dict[str, Any]) -> bool:
        columns = ', '.join([f"`{col}`" for col in data.keys()])  
        placeholders = ', '.join(['%s'] * len(data))
        query = f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"
        status = await self.execute_non_query(query, tuple(data.values()))
        logger.info(f"Insert into {table} status: {status}")
        return status
    
    async def insert_many(self, table: str, data_list: List[Dict[str, Any]]) -> bool:
        """Insert multiple records into table"""
        if not data_list:
            return False
        
        columns = ', '.join(data_list[0].keys())
        placeholders = ', '.join(['%s'] * len(data_list[0]))
        query = f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"
        
        params_list = [tuple(data.values()) for data in data_list]
        status = await self.execute_many(query, params_list)
        logger.info(f"Insert many into {table} status: {status}")
        return status
    
    async def select(self, table: str, columns: str = "*", where: str = None, 
                    params: tuple = None, order_by: str = None, limit: int = None) -> Optional[List[Dict[str, Any]]]:
        """Select records from table"""
        
        query = f"SELECT {columns} FROM {table}"
        
        if where:
            query += f" WHERE {where}"
        if order_by:
            query += f" ORDER BY {order_by}"
        if limit:
            query += f" LIMIT {limit}"
        
        result = await self.execute_query(query, params)
        if result is None:
            logger.info(f"Select from {table} failed")
            return None
        logger.info(f"Selected {len(result)} row(s) from {table}")
        return result
    
    async def select_one(self, table: str, columns: str = "*", where: str = None, 
                        params: tuple = None) -> Optional[Dict[str, Any]]:
        """Select one record from table"""
        result = await self.select(table, columns, where, params, limit=1)
        return result[0] if result else None
    
    async def update(self, table: str, data: Dict[str, Any], where: str, 
                    where_params: tuple = None) -> bool:
        """Update records in table"""
        set_clause = ', '.join([f"{k} = %s" for k in data.keys()])
        query = f"UPDATE {table} SET {set_clause} WHERE {where}"
        
        params = tuple(data.values()) + (where_params or ())
        status = await self.execute_non_query(query, params)
        logger.info(f"Update in {table} status: {status}")
        return status
    
    async def delete(self, table: str, where: str, params: tuple = None) -> bool:
        """Delete records from table"""
        query = f"DELETE FROM {table} WHERE {where}"
        
        status = await self.execute_non_query(query, params)
        logger.info(f"Delete from {table} status: {status}")
        return status
    
    async def table_exists(self, table_name: str) -> bool:
        """Check if table exists"""
        query = """
        SELECT COUNT(*) as count 
        FROM information_schema.tables 
        WHERE table_schema = %s AND table_name = %s
        """
        result = await self.execute_query(query, (self.database, table_name))
        if result and result[0]['count'] > 0:
            return True
        return False

def sanitize_and_validate_query(query: str) -> bool:

    if not isinstance(query, str) or not query.strip():
        return False

    query_stripped = query.strip()

    if ";" in query_stripped.rstrip(";"):
        return False

    if re.search(r"--|/\*|\*/", query_stripped):
        return False

    if re.search(r"\b(UNION|INTERSECT|EXCEPT)\b", query_stripped, re.IGNORECASE):
        return False

    parsed = sqlparse.parse(query_stripped)
    if not parsed or len(parsed) != 1:
        return False 

    statement = parsed[0]

    first_token = next((t for t in statement.tokens if not t.is_whitespace), None)
    if not first_token or first_token.ttype is not DML or first_token.value.upper() != "SELECT":
        return False

    dangerous_keywords = {
        "DROP", "DELETE", "INSERT", "UPDATE", "ALTER", "TRUNCATE", "MERGE", "EXEC",
        "CALL", "REPLACE", "GRANT", "REVOKE", "CREATE", "FUNCTION", "PROCEDURE", "DO"
    }

    for token in statement.flatten():
        val = token.value.upper()

        if token.ttype in {Whitespace, Comment, Literal.String.Single, Name, Literal.Number}:
            continue

        if token.ttype in {Keyword, DDL} and val in dangerous_keywords:
            return False

        if token.value == "(" and "SELECT" in token.parent.value.upper():
            inner = token.parent.value.upper()
            if re.search(r"\(\s*SELECT\s+", inner):
                return False

    return True
