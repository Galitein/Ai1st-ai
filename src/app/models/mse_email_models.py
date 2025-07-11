from typing import Optional
from pydantic import BaseModel
from fastapi import Query

class EmailQueryParams(BaseModel):
    user_id: Optional[str]
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    from_email: Optional[str] = None
    unread_only: Optional[bool] = False
    search: Optional[str] = None
    top: Optional[int] = Query(10, ge=1, le=100)
    orderby: Optional[str] = "receivedDateTime desc"
    next_url: Optional[str] = None
