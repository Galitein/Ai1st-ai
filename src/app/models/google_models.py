from pydantic import BaseModel
from typing import List

class UploadFile(BaseModel):
    file_names: List[str]