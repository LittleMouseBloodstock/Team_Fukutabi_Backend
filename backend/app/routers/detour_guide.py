from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from app.db.database import get_db
#from app.services.detour_places import search_places
# 代わりに、実在する検索関数を使う
from app.routes.detours import search_detours as core_search
from app.schemas.detour import DetourSuggestion, TravelMode
from app.models.detour_history import DetourHistory
from app.services.security import get_current_user
from datetime import datetime

router = APIRouter(prefix="/detour-guide", tags=["Detour Guide"])

@router.get("/search", response_model=List[DetourSuggestion])
async def search_detour_guide(
    lat: float = Query(...),
    lng: float = Query(...),
    mode: TravelMode = Query("walk"),
    minutes: int = Query(15, ge=1, le=120),
    keyword: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    # 互換のコア検索を呼ぶ（引数はあるものだけ渡す）
    # search_detours のシグネチャに合わせて調整
    items = await core_search(
        lat=lat,
        lng=lng,
        mode=mode,
        minutes=minutes,
        detour_type=None,   # keyword を detour_type にマップするならここで変換
        categories=None
    )

    # DetourHistory 登録（元のまま）
    for r in items:
        history = DetourHistory(
            user_id=current_user.id,
            name=r.name,
            lat=r.lat,
            lng=r.lng,
            chosen_at=datetime.utcnow(),
            note=getattr(r, "description", None)
        )
        db.add(history)
    await db.commit()

    return items