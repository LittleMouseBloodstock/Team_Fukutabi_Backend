from fastapi import APIRouter, HTTPException, Query
from app.services import google_places as svc

router = APIRouter(prefix="/places", tags=["places"])

@router.get("/predictions")
async def predictions(input: str = Query(..., min_length=1), limit: int = 3):
    try:
        items = await svc.predictions(input, limit)
        return {"items": items}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/details")
async def details(place_id: str):
    try:
        return await svc.details(place_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))