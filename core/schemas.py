from __future__ import annotations
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, Literal


class UserCreate(BaseModel):
    email: str


class UserOut(BaseModel):
    id: int
    email: str
    created_at: datetime

    class Config:
        from_attributes = True


class ObjectCreate(BaseModel):
    user_id: int
    provider: str
    provider_type: Literal["message", "file", "task", "event"]
    provider_id: str
    title: Optional[str] = None
    body: Optional[str] = None
    metadata_json: Optional[dict] = Field(default_factory=dict)


class ObjectOut(BaseModel):
    id: int
    user_id: int
    provider: str
    provider_type: str
    provider_id: str
    title: Optional[str]
    body: Optional[str]
    metadata_json: Optional[dict]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SearchQuery(BaseModel):
    user_id: int
    query: str
    top_k: int = 5
    provider: Optional[str] = None
    provider_type: Optional[str] = None

