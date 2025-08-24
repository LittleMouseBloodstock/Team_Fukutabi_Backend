# routers/detour_guide_router.py
#from fastapi import APIRouter, Depends, HTTPException
#from sqlalchemy.ext.asyncio import AsyncSession
#from typing import List
#from app.db.database import get_db
#from app.schemas.detour import DetourSuggestion, DetourSearchQuery
#from app.services.detour_places import search_detour_places
#from app.db import models

#router = APIRouter(prefix="/detour", tags=["detour-guide"])

#@router.post("/recommend", response_model=List[DetourSuggestion])
#async def recommend_detour_places(
#    query: DetourSearchQuery,
#    db: AsyncSession = Depends(get_db)
#):
#    try:
#        results = await search_detour_places(
#            lat=query.lat,
#            lng=query.lng,
#            mode=query.mode,
#            minutes=query.minutes,
#            detour_type=query.detour_type,
#            categories=query.categories,
#        )
#    except Exception as e:
#        raise HTTPException(status_code=500, detail=f"検索エラー: {str(e)}")

#    # DBに保存（任意）
#    for r in results:
#        suggestion = models.DetourSuggestion(
#            name=r["name"],
#            description=r.get("description"),
#            lat=r["lat"],
#            lng=r["lng"],
#            distance_km=r["distance_km"],
#            duration_min=r["duration_min"],
#            rating=r.get("rating"),
#            open_now=r.get("open_now"),
#            opening_hours=r.get("opening_hours"),
#            parking=r.get("parking"),
#            source=r["source"],
#            url=r.get("url"),
#            photo_url=r.get("photo_url"),
#        )
#        db.add(suggestion)
#    await db.commit()

#    return results
