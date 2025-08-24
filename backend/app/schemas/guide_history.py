from pydantic import BaseModel, Field
from typing import List, Optional, Literal
from datetime import datetime

GuideType = Literal["talk", "detour"]

class GuideSessionCreate(BaseModel):
    guide_type: GuideType
    title: str
    subtitle: Optional[str] = None
    description: Optional[str] = None
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    duration_min: Optional[int] = None
    spots_count: int = 0

class GuideSessionRead(BaseModel):
    id: int
    guide_type: GuideType
    title: str
    subtitle: Optional[str] = None
    description: Optional[str] = None
    started_at: datetime
    ended_at: Optional[datetime] = None
    duration_min: Optional[int] = None
    spots_count: int

    class Config:
        from_attributes = True

class HistorySummary(BaseModel):
    travel_guides: int = Field(0)
    detours: int = Field(0)
    hours: int = Field(0)

class DayGroup(BaseModel):
    date: str
    items: List[GuideSessionRead]

class GuideHistoryResponse(BaseModel):
    summary: HistorySummary
    days: List[DayGroup]
