from pydantic import BaseModel

class TrelloTokenPayload(BaseModel):
    user_id: str
    token: str