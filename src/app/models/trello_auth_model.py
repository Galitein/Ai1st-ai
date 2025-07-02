from pydantic import BaseModel

class TrelloTokenPayload(BaseModel):
    ait_id : str
    token: str