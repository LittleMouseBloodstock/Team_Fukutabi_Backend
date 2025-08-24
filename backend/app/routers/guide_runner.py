# app/routers/guide_runner.py
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from app.services.security import get_current_user

router = APIRouter(prefix="/guide", tags=["Guide Runner"])

class GuideRunIn(BaseModel):
    destination: str

class GuideRunOut(BaseModel):
    text: str
    audio_url: str

@router.post("/run", response_model=GuideRunOut)
async def run_guide(payload: GuideRunIn, current_user = Depends(get_current_user)):
    dest = payload.destination
    text = f"こんにちは！今日は「{dest}」をご案内します。詳細はTTS実装後に音声で再生できます。"
    audio_url = ""  # TTS導入後に差し替え
    return GuideRunOut(text=text, audio_url=audio_url)
