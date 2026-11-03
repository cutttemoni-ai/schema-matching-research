from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class Column(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    id: str
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=1000)
    data_type: Literal["string", "integer", "number", "date", "boolean", "unknown"]


class Recommendation(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    source_id: str
    target_id: str | None
    status: Literal["matched", "no_match", "needs_review"]
    reason: str = Field(min_length=1, max_length=500)


class MatchResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    mappings: list[Recommendation]
