from pydantic import BaseModel

class ChatResponse(BaseModel):
    model: str
    content: str
    prompt_tokens: int
    completion_tokens: int
    id: str
