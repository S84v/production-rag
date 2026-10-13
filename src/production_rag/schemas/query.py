from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    collection: str = Field(min_length=1, max_length=128)
    limit: int = Field(default=5, ge=1, le=20)
