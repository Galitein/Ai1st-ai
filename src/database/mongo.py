import os
import logging
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv()

class MongoDBClient:
    def __init__(self, uri=None, db_name=None):
        self.uri = uri or os.getenv("MONGO_URI", "mongodb://localhost:27017/")
        self.db_name = db_name or os.getenv("MONGO_DB", "ai1st_customgpt")
        self.client = AsyncIOMotorClient(self.uri)
        self.db = self.client[self.db_name]

    async def insert(self, collection_name: str, doc: dict):
        try:
            collection = self.db[collection_name]
            result = await collection.insert_one(doc)
            logging.info(f"Inserted document with ID: {result.inserted_id}")
            return {"status": True, "inserted_id": str(result.inserted_id)}
        except Exception as e:
            logging.error(f"Insert error: {e}")
            return {"status": False, "message": str(e)}

    async def find(self, collection_name: str, query: dict):
        try:
            collection = self.db[collection_name]
            cursor = collection.find(query)
            results = []
            async for document in cursor:
                results.append(document)
            return {"status": True, "results": results}
        except Exception as e:
            logging.error(f"Find error: {e}")
            return {"status": False, "message": str(e)}

    async def find_one(self, collection_name: str, query: dict):
        try:
            collection = self.db[collection_name]
            result = await collection.find_one(query)
            return {"status": True, "result": result}
        except Exception as e:
            logging.error(f"Find one error: {e}")
            return {"status": False, "message": str(e)}

    async def update(self, collection_name: str, query: dict, update_values: dict):
        try:
            collection = self.db[collection_name]
            result = await collection.update_many(query, {'$set': update_values})
            return {"status": True, "modified_count": result.modified_count}
        except Exception as e:
            logging.error(f"Update error: {e}")
            return {"status": False, "message": str(e)}

    async def delete(self, collection_name: str, query: dict):
        try:
            collection = self.db[collection_name]
            result = await collection.delete_many(query)
            return {"status": True, "deleted_count": result.deleted_count}
        except Exception as e:
            logging.error(f"Delete error: {e}")
            return {"status": False, "message": str(e)}