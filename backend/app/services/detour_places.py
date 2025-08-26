# app/services/detour_places.py

import os
import httpx
from typing import List, Optional
from app.schemas.detour import DetourSuggestion, TravelMode, DetourType
from app.services.geo import haversine_km   # ← 実距離計算に使用

GOOGLE_PLACES_API_KEY = os.getenv("GOOGLE_PLACES_API_KEY") or os.getenv("GOOGLE_MAPS_API_KEY")  # ← 念のため両対応
BASE_URL = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"

def _speed_kmh(mode: TravelMode) -> float:
    # Enum/Literal どちらでも動くように文字列化して判定
    m = str(mode)
    return 4.5 if "walk" in m else 40.0

def minutes_to_distance_km(minutes: int, mode: TravelMode) -> float:
    return (minutes / 60) * _speed_kmh(mode)

def _eta_text(mode: TravelMode, distance_km: float) -> str:
    # 距離→分に換算（丸め）
    mins = max(1, round((distance_km / _speed_kmh(mode)) * 60))
    meters = round(distance_km * 1000)
    prefix = "徒歩約" if "walk" in str(mode) else "車で約"
    return f"{prefix}{mins}分・{meters}m"

def _photo_url(photo_ref: Optional[str], maxw: int = 400) -> Optional[str]:
    if not photo_ref or not GOOGLE_PLACES_API_KEY:
        return None
    # パラメータ名は photo_reference（photoreference ではない）
    return (
        "https://maps.googleapis.com/maps/api/place/photo"
        f"?maxwidth={maxw}&photo_reference={photo_ref}&key={GOOGLE_PLACES_API_KEY}"
    )

async def search_detour_places(
    lat: float,
    lng: float,
    mode: TravelMode,
    minutes: int,
    detour_type: DetourType,
    categories: Optional[List[str]] = None
) -> List[DetourSuggestion]:
    radius_km = minutes_to_distance_km(minutes, mode)
    radius_m = int(radius_km * 1000)

    # キーワード
    if categories and len(categories) > 0:
        keyword = " ".join(categories)
    else:
        keyword_defaults = {
            "food": "レストラン カフェ 飲食",
            "event": "イベント 会場 フェス 展示",
            "souvenir": "土産 みやげ 土産物店",
            "spot": "観光 名所 観光地"
        }
        keyword = keyword_defaults.get(str(detour_type), "")

    params = {
        "location": f"{lat},{lng}",
        "radius": radius_m,
        "key": GOOGLE_PLACES_API_KEY,
        "language": "ja",
        "keyword": keyword
    }

    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(BASE_URL, params=params)
        r.raise_for_status()
        data = r.json()

    suggestions: List[DetourSuggestion] = []
    for place in data.get("results", []):
        plat = place.get("geometry", {}).get("location", {}).get("lat")
        plng = place.get("geometry", {}).get("location", {}).get("lng")
        if plat is None or plng is None:
            continue

        # 実距離で上書き
        dist_km = haversine_km(lat, lng, plat, plng)
        eta = _eta_text(mode, dist_km)

        photo_ref = None
        photos = place.get("photos") or []
        if photos and isinstance(photos, list):
            photo_ref = (photos[0] or {}).get("photo_reference")

        suggestions.append(
            DetourSuggestion(
                id=None,  # ここは外部IDを使わないなら None（DB保存時にUUID付与）
                name=place.get("name", ""),
                description=place.get("vicinity"),
                lat=plat,
                lng=plng,
                distance_km=dist_km,            # ← 実距離
                duration_min=minutes,           # 検索条件そのまま
                eta_text=eta,                   # ← 必須フィールドを追加
                source="google",
                detour_type=detour_type,        # ← 必須フィールドを追加（呼び出し引数のまま）
                url=f"https://www.google.com/maps/place/?q=place_id:{place.get('place_id')}",
                address=place.get("formatted_address"),
                rating=place.get("rating"),
                reviews_count=place.get("user_ratings_total"),
                open_now=(place.get("opening_hours") or {}).get("open_now") if place.get("opening_hours") else None,
                opening_hours=None,             # 必要なら整形して入れる
                parking=None,
                photo_url=_photo_url(photo_ref) # ← 写真1枚（無ければ None）
            )
        )

    return suggestions
