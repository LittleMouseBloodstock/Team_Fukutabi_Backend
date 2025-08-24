from fastapi import APIRouter, Depends, Query, HTTPException, Header
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from typing import List
import os
from app.db.database import get_db
from app.db import models
from app.schemas.destination_schema import DestinationCreate, DestinationRead
from app.services import google_places as svc
from fastapi.concurrency import run_in_threadpool #(byきたな)

router = APIRouter(prefix="/destinations", tags=["destinations"])

# --- 簡易APIキー保護（.env に ADMIN_API_KEY がある時だけ有効化）---
ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "").strip()

def maybe_require_admin(x_api_key: str = Header(default="")):
    """ADMIN_API_KEY が設定されている場合のみ、X-API-Key ヘッダをチェック"""
    if ADMIN_API_KEY and x_api_key != ADMIN_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")

# ---------------------------------------------------------------------
# A) 完全同期: CRUD（DBのみ触る）byきたな
# ---------------------------------------------------------------------
@router.post("/", response_model=DestinationRead, status_code=201)
def create_destination(payload: DestinationCreate, db: Session = Depends(get_db)):
    obj = models.Destination(
        place_id=payload.placeId,
        name=payload.name,
        address=payload.address,
        lat=payload.lat,
        lng=payload.lng,
    )
    db.add(obj)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        # 既に登録済みなら409を返す
        raise HTTPException(status_code=409, detail="Destination already exists (place_id)")
    db.refresh(obj)
    return DestinationRead(
        id=obj.id,
        placeId=obj.place_id,
        name=obj.name,
        address=obj.address,
        lat=obj.lat,
        lng=obj.lng,
    )
# ------------------ 保存済み一覧（ページング対応） -------------------

@router.get("/", response_model=List[DestinationRead])
def list_destinations(
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    rows = db.query(models.Destination).offset(skip).limit(limit).all()
    return [
        DestinationRead(
            id=r.id,
            placeId=r.place_id,
            name=r.name,
            address=r.address,
            lat=r.lat,
            lng=r.lng,
        )
        for r in rows
    ]
# ---------------------------------------------------------------------
# B) 混在: 外部API(await) + DBはthreadpoolに退避byきたな
# ---------------------------------------------------------------------

# --------------- UX簡略化：place_id だけで登録する -------------------
@router.post("/register", response_model=DestinationRead, status_code=201)
async def register_from_place_id(
    place_id: str = Query(..., description="Google Place ID"),
    db: Session = Depends(get_db),
):
    """
    place_id だけ受け取り、サーバー側で Places Details を取得して保存する。
    フロントは details 結果を組み立てる必要なし。
    """
    # 1) 外部APIは非同期で取得（byきたな）
    data = await svc.details(place_id)
    if not data or "geometry" not in data or "location" not in data["geometry"]:
        raise HTTPException(status_code=404, detail="Place details not found")
    # 2) DB処理は threadpool へ（イベントループを塞がないbyきたな）
    def _insert():
        obj = models.Destination(
            place_id=data["place_id"],
            name=data.get("name", ""),
            address=data.get("formatted_address", ""),
            lat=data["geometry"]["location"]["lat"],
            lng=data["geometry"]["location"]["lng"],
        )
        db.add(obj)
        try:
            db.commit()
            db.refresh(obj)
        except IntegrityError:
            db.rollback()
    #         raise #きたな追加
    #     db.refresh(obj) #きたな追加
    #     return obj #きたな追加

    # try:
    #     obj = await run_in_threadpool(_insert) #きたな追加
    # except IntegrityError:
    #     # 既に登録済み
    #     raise HTTPException(status_code=409, detail="Destination already exists (place_id)") #きたな変更
# 以下コードに変更（IntegrityErrorをキャッチして既存データを返すように）
            # ★ 既存のデータを探して返す
            obj = db.query(models.Destination).filter_by(place_id=place_id).first()
            if obj is None:
                raise HTTPException(status_code=500, detail="Failed to insert and retrieve destination")
        return obj

    obj = await run_in_threadpool(_insert)

    return DestinationRead(
        id=obj.id,
        placeId=obj.place_id,
        name=obj.name,
        address=obj.address,
        lat=obj.lat,
        lng=obj.lng,
    )


