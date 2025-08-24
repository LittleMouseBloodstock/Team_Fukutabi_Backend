# 寄り道ガイド専用の Nearby 検索モジュール（既存 places.py は触らない）
from dotenv import load_dotenv
load_dotenv()

import os
import httpx
from typing import List, Optional
from .geo import haversine_km

# 既存の env 名に合わせる（GOOGLE_MAPS_API_KEY を使う）
GOOGLE_API = os.getenv("GOOGLE_MAPS_API_KEY") or ""
REGION = os.getenv("GOOGLE_PLACES_REGION", "jp")
LANG = os.getenv("GOOGLE_PLACES_LANGUAGE", "ja")

def _photo_url(ref: str, maxw: int = 800) -> str:
    return (f"https://maps.googleapis.com/maps/api/place/photo"
            f"?maxwidth={maxw}&photo_reference={ref}&key={GOOGLE_API}")

# detour_type ごとのタイプ定義（必要に応じて拡張）
TYPE_MAP = {
    "food": {"types": ["restaurant","cafe","bakery"], "keyword": None},
    "souvenir": {"types": ["souvenir_store","department_store","shopping_mall"], "keyword": None},
    "spot": {  # ← 追加
        "types": [
            "tourist_attraction","national_park","museum","art_gallery",
            "aquarium","zoo","amusement_park","campground","hiking_area","library",
            "church","place_of_worship"
        ],
        "keyword": None
    }
}

async def google_nearby(
    lat: float,
    lng: float,
    radius_m: int,
    detour_type: str,
    categories: Optional[List[str]] = None,
) -> List[dict]:
    """Google Places Nearby Search（寄り道ガイド用）。"""
    if not GOOGLE_API:
        return []

    base_params = {
        "location": f"{lat},{lng}",
        "radius": radius_m,
        "key": GOOGLE_API,
        "language": LANG,
        # "region": REGION,  # Nearby Searchはregion指定非対応、languageは可
    }

    conf = TYPE_MAP.get(detour_type, {})
    results: List[dict] = []

    async with httpx.AsyncClient(timeout=10) as client:
        if categories:  # キーワード優先
            params = dict(base_params)
            params["keyword"] = " ".join(categories)
            resp = await client.get("https://maps.googleapis.com/maps/api/place/nearbysearch/json", params=params)
            data = resp.json()
            batches = [data.get("results", [])]
        else:
            batches = []
            for t in conf.get("types", [None]):
                params = dict(base_params)
                if t:
                    params["type"] = t
                resp = await client.get("https://maps.googleapis.com/maps/api/place/nearbysearch/json", params=params)
                data = resp.json()
                batches.append(data.get("results", []))

    for batch in batches:
        for r in batch:
            try:
                plat = float(r["geometry"]["location"]["lat"])
                plng = float(r["geometry"]["location"]["lng"])
            except Exception:
                continue  # 座標が無ければ捨てる
            
            results.append({
                "name": r.get("name"),
                "lat": plat,
                "lng": plng,
                "rating": r.get("rating"),
                "open_now": r.get("opening_hours", {}).get("open_now") if r.get("opening_hours") else None,
                "opening_hours": None,  # 詳細までは取らない（必要時に details 追撃）
                "parking": None,
                "url": f"https://www.google.com/maps/place/?q=place_id:{r.get('place_id')}",
                "photo_url": _photo_url(r["photos"][0]["photo_reference"]) if r.get("photos") else None,
                "source": "google",
            })

    # 重複除去＋距離付与＋ソート
    uniq, seen = [], set()
    for x in results:
        key = (x["name"], round(x["lat"], 5), round(x["lng"], 5))
        if key in seen:
            continue
        seen.add(key)
        x["distance_km"] = haversine_km(lat, lng, x["lat"], x["lng"])
        uniq.append(x)

    uniq.sort(key=lambda x: (x["distance_km"], -(x.get("rating") or 0)))
    return uniq
