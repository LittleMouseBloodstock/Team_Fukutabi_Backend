from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from typing import Optional, Union
import traceback
from typing import List
from sqlalchemy import func
from app.schemas.destination_schema import DestinationBrief
from app.db.database import get_db
from app.db import models
from app.schemas.visit_record import VisitCreate, VisitRead
from app.schemas.guide_content import GuideRead
from app.services import gpt, tts

router = APIRouter(prefix="/visits", tags=["visits"])

def _get_destination_by_any(db: Session, destination_id: Union[int, str]) -> Optional[models.Destination]:
    if isinstance(destination_id, int):
        return db.query(models.Destination).filter(models.Destination.id == destination_id).first()
    return db.query(models.Destination).filter(models.Destination.place_id == destination_id).first()

@router.post("/", response_model=dict, status_code=201)
async def create_visit(payload: VisitCreate, db: Session = Depends(get_db)):
    print("DEBUG /visits payload.userId =", payload.userId)  # デバッグ用
    # 1) 目的地取得
    dest = _get_destination_by_any(db, payload.destinationId)
    if not dest:
        raise HTTPException(status_code=404, detail="Destination not found")

    # 2) Visit 作成（userId は int|None）
    try:
        visit = models.VisitHistory(destination_id=dest.id, user_id=str(payload.userId) if payload.userId is not None else None)
        db.add(visit)
        db.commit()
        db.refresh(visit)
    except IntegrityError as e:
        db.rollback()
        print("Visit commit IntegrityError:", repr(e))
        traceback.print_exc()
        raise HTTPException(status_code=400, detail="Invalid visit values (FK/NOT NULL/unique)")  # 具体化
    except Exception as e:
        db.rollback()
        print("Visit commit error:", repr(e))
        traceback.print_exc()
        raise

    # 3) 任意: ユーザープロファイル
    user_profile: Optional[dict] = None
    if payload.userId and hasattr(models, "User"):
        u = db.get(models.User, payload.userId)
        if u:
            user_profile = {
                "age": getattr(u, "age", None),
                "gender": getattr(u, "gender", None),
            }

    # 4) ガイド生成（失敗しても必ずフォールバック）
    try:
        text = await gpt.generate_guide_text(
            name=dest.name, address=dest.address, lat=dest.lat, lng=dest.lng,
            style="friendly", user=user_profile
        )
    except Exception as e:
        print("GPT guide error (fallback to plain text):", repr(e))
        text = f"{dest.name}（{dest.address}）のご案内です。見どころ、歴史、アクセスをやさしく紹介します。"

    try:
        _, audio_url = await tts.synthesize_to_mp3(text, voice=None)
    except Exception as e:
        print("TTS error (fallback to placeholder):", repr(e))
        audio_url = "/media/guides/README.txt"

    # 5) ガイド保存（voice が NOT NULL だと None で落ちるので空文字にする）
    try:
        guide = models.Guide(
            destination_id=dest.id,
            visit_id=visit.id,
            guide_text=text,
            voice="",                 # ← None で NOT NULL だと落ちる対策
            style="friendly",
            audio_url=audio_url or "",# ← 念のため
        )
        db.add(guide)
        db.commit()
        db.refresh(guide)
    except IntegrityError as e:
        db.rollback()
        print("Guide commit IntegrityError:", repr(e))
        traceback.print_exc()
        raise HTTPException(status_code=400, detail="Invalid guide values (FK/NOT NULL/length)")
    except Exception as e:
        db.rollback()
        print("Guide commit error:", repr(e))
        traceback.print_exc()
        raise

    # 6) レスポンス作成（validate 失敗の中身を出す）
    try:
        visit_out = VisitRead.model_validate(visit)
    except Exception as e:
        print("VisitRead validate error:", repr(e))
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Visit serialization failed")

    try:
        guide_out = GuideRead.model_validate(guide)
    except Exception as e:
        print("GuideRead validate error:", repr(e))
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Guide serialization failed")

    return {"visit": visit_out, "guide": guide_out}

# 7) 最近の訪問先一覧（placeId と name のみ）取得
@router.get("/recent", response_model=List[DestinationBrief])
def get_recent_destinations(user_id: str, limit: int = 5, db: Session = Depends(get_db)):
    """
    ユーザーの最近の訪問先を、目的地ごとに重複排除して新しい順で返す。
    MySQL でも動くように subquery + join で DISTINCT 相当を実現。
    """
    # 各 destination_id の最新 visit を求める
    sub = (
        db.query(
            models.VisitHistory.destination_id.label("dest_id"),
            func.max(models.VisitHistory.created_at).label("latest")
        )
        .filter(models.VisitHistory.user_id == str(user_id))
        .group_by(models.VisitHistory.destination_id)
        .subquery()
    )

    # 最新 visit と Destination を結合して新しい順に
    rows = (
        db.query(models.Destination.place_id, models.Destination.name)
        .join(sub, sub.c.dest_id == models.Destination.id)
        .order_by(sub.c.latest.desc())
        .limit(limit)
        .all()
    )

    return [DestinationBrief(placeId=pl_id, name=name) for pl_id, name in rows]