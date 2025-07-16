from pydantic import BaseModel
from typing import List

class AitIdInput(BaseModel):
    ait_id: str
    
class FileNamesInput(AitIdInput):
    document_collection: str
    file_names: List[str]

class QueryInput(AitIdInput):
    document_collection: str
    query: str
    limit: int
    similarity_threshold: float

class CreateIndexingInput(AitIdInput):
    documents: List

class TaskOrPromptInput(AitIdInput):
    task_or_prompt: str

class CreateUrlIndexingInput(AitIdInput):
    file_urls: List[str]
    document_collection: str

class CreateAitInput(BaseModel):
    file_names: List[str]
    task_or_prompt: str

class ChatInput(AitIdInput):
    query: str