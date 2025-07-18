from typing import Optional
from pydantic import BaseModel, Field
from fastapi import Query

class EmailQueryParams(BaseModel):
    ait_id: str
    # start_date: Optional[str] = None
    # end_date: Optional[str] = None
    # from_email: Optional[str] = None
    # unread_only: Optional[bool] = False
    # search: Optional[str] = None
    # top: Optional[int] = Query(1000, ge=1, le=1500)
    # orderby: Optional[str] = "receivedDateTime desc"
    # next_url: Optional[str] = None

class EmailCBQuery(BaseModel):
    ait_id:str
    input_query: str

class SyncStatusResponse(BaseModel):
    processed: int = Field(..., description="The number of emails processed so far.")
    total: int = Field(..., description="The total number of emails to be synchronized.")
    status: str = Field(..., description="The current status of the synchronization process (e.g., running, completed, failed).")