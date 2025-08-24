from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.db import models
from app.schemas.guide_content import GuideCreate, GuideRead
from app.services import gpt, tts

router = APIRouter(prefix="/guides", tags=["guides"])

@router.post("/", response_model=GuideRead, status_code=201)
async def create_guide(payload: GuideCreate, db: Session = Depends(get_db)):
    dest = db.get(models.Destination, payload.destinationId)
    if not dest:
        raise HTTPException(404, "Destination not found")

    user_profile = None
    if payload.userId:
        user = db.get(models.User, payload.userId)  # ← あなたのUserモデルに合わせて
        if user:
            user_profile = {
                "age": getattr(user, "age", None),
                "gender": getattr(user, "gender", None),
                "interests": getattr(user, "interests", None),  # "神社,グルメ" など
            }

    text = await gpt.generate_guide_text(
        name=dest.name,
        address=dest.address,
        lat=dest.lat,
        lng=dest.lng,
        style=payload.style or "friendly",
        user=user_profile,   # ★ パーソナライズ情報を渡す
    )

    _, audio_url = await tts.synthesize_to_mp3(text, payload.voice)

    obj = models.Guide(
        destination_id=dest.id,
        guide_text=text,
        voice=payload.voice,
        style=payload.style,
        audio_url=audio_url,
    )
    db.add(obj); db.commit(); db.refresh(obj)

    return GuideRead(
        id=obj.id, destinationId=obj.destination_id, guideText=obj.guide_text,
        voice=obj.voice, style=obj.style, audioUrl=obj.audio_url,
        createdAt=obj.created_at
    )
