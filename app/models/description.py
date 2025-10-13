from pydantic import BaseModel, Field
from typing import Optional, List

class DescriptionRequest(BaseModel):
    listing_id: int
    features: List[str]
    tone: str = Field(default="enthusiastic")
