from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import datetime

class GuideCreate(BaseModel):
    destinationId: str
    style: Optional[str] = "friendly"
    voice: Optional[str] = None
    userId: Optional[str] = None

class GuideRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    id: str
    destinationId: str = Field(alias="destination_id")
    visitId: Optional[str] = Field(alias="visit_id", default=None) 
    guideText: str = Field(alias="guide_text")
    voice: Optional[str] = None
    style: Optional[str] = None
    audioUrl: str = Field(alias="audio_url")
    createdAt: Optional[datetime] = Field(alias="created_at", default=None)