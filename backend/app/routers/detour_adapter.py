# app/routers/detour_adapter.py
from fastapi import APIRouter, Query, Depends
from typing import List, Dict, Any
import math

# 既存の実ルータ関数を呼ぶ
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.routes.detours import search_detours_core
from app.schemas.detour import DetourSearchQuery, DetourType  # ← 追加

router = APIRouter(prefix="/detour", tags=["Detour (Compat)"])

def cat_to_detour_type(category: str) -> DetourType:         # ← 戻り値型もEnum
    c = (category or "").lower()
    if c in ("gourmet", "food"): return DetourType.food
    if c == "event": return DetourType.event
    if c in ("local", "local_spot", "attraction", "sight"):
        return DetourType.spot   # ← ここを追加

    return DetourType.souvenir

def eta_text(distance_km: float, mode: str) -> str:
    speed_kmh = 4.5 if mode == "walk" else 20.0  # ざっくり
    minutes = max(1, math.ceil((distance_km / speed_kmh) * 60))
    meters = int(distance_km * 1000)
    return f"{'徒歩' if mode=='walk' else '車'}約{minutes}分・{meters}m"

@router.get("/search", response_model=List[Dict[str, Any]])
async def search_detour_compat(
    mode: str = Query("walk", pattern="^(walk|drive)$"),
    duration: int = Query(15, ge=1, le=120),
    category: str = Query("local"),
    # 既定の座標（東京駅）。将来はフロントから渡すか、位置サービスで補完。
    lat: float = Query(35.681236),
    lng: float = Query(139.767125),
    keyword: str | None = Query(None),  # ★追加
    local_only: bool = Query(False),          # ← 追加（UIから受け取れる）
    db: Session = Depends(get_db),  # ← 追加：DBを受け取る
):
    
        # 🔑 ここで必ず detour_type を定義
    detour_type: DetourType = cat_to_detour_type(category)    # ← 型も Enum
    # 旧categoryが「local系」なら既定で非チェーンオン
    local_only_flag = local_only or ((category or "").lower() in {"local","local_spot","attraction","sight"})

    # 互換: 既存のクエリ名(duration/category) → 本番モデル(minutes/detour_type) に詰め替え
    q = DetourSearchQuery(
        lat=lat,
        lng=lng,
        mode=mode,             # "walk" | "drive"
        minutes=duration,
        detour_type=detour_type,
        exclude_ids=[],
        seed=None,
        radius_m=None,
        keyword=keyword,                 # ★ここで詰める
        local_only=local_only_flag,           # ← 渡す
        history_only=False,
    )
    # コアを直呼び（HTTP層/Dependsに依存しないので安全）
    items = await search_detours_core(q, db)
    
    out = []
    for i, it in enumerate(items, start=1):
        dkm = getattr(it, "distance_km", None) or 0.5
        out.append({
            "id": i,
            "name": it.name,
            "category": category,
            "eta_text": eta_text(dkm, mode),
            "description": getattr(it, "description", "") or getattr(it, "note", "") or "",
        })
    return out
