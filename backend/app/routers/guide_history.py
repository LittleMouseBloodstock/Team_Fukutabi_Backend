# app/routers/guide_history.py
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from datetime import datetime
from typing import List, Optional
from app.db.database import get_db
from app.services.security import get_current_user
from app.models.detour_history import DetourHistory  # 既存

from pydantic import BaseModel, Field

class Item(BaseModel):
    id: int
    guide_type: str  # "detour"
    title: str
    subtitle: Optional[str] = None
    description: Optional[str] = None
    started_at: datetime
    duration_min: Optional[int] = None
    spots_count: int = 1

class DayGroup(BaseModel):
    date: str
    items: List[Item]

class Summary(BaseModel):
    travel_guides: int = Field(0)
    detours: int = Field(0)
    hours: int = Field(0)

class HistoryResponse(BaseModel):
    summary: Summary
    days: List[DayGroup]

router = APIRouter(prefix="/guide-history", tags=["Guide History"])

@router.get("/", response_model=HistoryResponse)
def get_history(
    month: Optional[str] = Query(None, description="YYYY-MM"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    # 月範囲
    if month:
        y, m = [int(x) for x in month.split("-")]
        start = datetime(y, m, 1)
    else:
        now = datetime.utcnow()
        start = datetime(now.year, now.month, 1)
    next_start = datetime(start.year + (start.month // 12), ((start.month % 12) + 1), 1)

    # 既存DetourHistoryベースで集計
    q = (
        select(DetourHistory)
        .where(DetourHistory.chosen_at >= start, DetourHistory.chosen_at < next_start)
        .order_by(DetourHistory.chosen_at.desc())
    )
    rows = db.execute(q).scalars().all()

    # サマリ（今は寄り道のみ）
    detours = len(rows)
    hours = 0  # DetourHistoryにdurationが無い想定のため0。拡張時に合算OK。

    # 日別グループ
    groups = {}
    for r in rows:
        date_key = r.chosen_at.strftime("%Y-%m-%d")
        groups.setdefault(date_key, []).append(
            Item(
                id=r.id,
                guide_type="detour",
                title=r.name or "寄り道",
                subtitle="寄り道ガイド",
                description=r.note,
                started_at=r.chosen_at,
                duration_min=None,
                spots_count=1,
            )
        )

    day_list = [DayGroup(date=k, items=v) for k, v in sorted(groups.items(), reverse=True)]
    return HistoryResponse(summary=Summary(travel_guides=0, detours=detours, hours=hours), days=day_list)
