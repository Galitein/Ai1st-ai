from pydantic import BaseModel
from typing import List

class FileNamesInput(BaseModel):
    document_collection: str
    ait_id: str
    file_names: List[str]

class QueryInput(BaseModel):
    document_collection: str
    ait_id:str
    query: str
    limit: int
    similarity_threshold: float

class TaskOrPromptInput(BaseModel):
    ait_id: str
    task_or_prompt: str

class FileListOutput(BaseModel):
    folder_id: str

class CreateAitInput(BaseModel):
    file_names: List[str]
    task_or_prompt: str

class ChatInput(BaseModel):
    ait_id: str
    query: str