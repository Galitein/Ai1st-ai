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
    documents: List[str]

class TaskOrPromptInput(AitIdInput):
    task_or_prompt: str

class FileListOutput(BaseModel):
    folder_id: str

class CreateAitInput(BaseModel):
    file_names: List[str]
    task_or_prompt: str

class ChatInput(AitIdInput):
    query: str