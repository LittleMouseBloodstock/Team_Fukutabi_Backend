# app/services/detour_places.py

import os
import httpx
from typing import List, Optional
from app.schemas.detour import DetourSuggestion, TravelMode, DetourType

GOOGLE_PLACES_API_KEY = os.getenv("GOOGLE_PLACES_API_KEY")
BASE_URL = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"

def minutes_to_distance_km(minutes: int, mode: TravelMode) -> float:
    speed_kmh = 4.5 if mode == "walk" else 40.0
    return (minutes / 60) * speed_kmh

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

    # キーワード作成：カテゴリがあればカンマで結合、なければ detour_type に応じた初期値
    if categories:
        keyword = " ".join(categories)
    else:
        keyword_defaults = {
            "food": "レストラン",
            "event": "イベント会場",
            "souvenir": "お土産"
        }
        keyword = keyword_defaults.get(detour_type, "")

    params = {
        "location": f"{lat},{lng}",
        "radius": radius_m,
        "key": GOOGLE_PLACES_API_KEY,
        "language": "ja",
        "keyword": keyword
    }

    async with httpx.AsyncClient() as client:
        resp = await client.get(BASE_URL, params=params)
        data = resp.json()

    suggestions = []
    for place in data.get("results", []):
        suggestions.append(
            DetourSuggestion(
                name=place["name"],
                description=place.get("vicinity"),
                lat=place["geometry"]["location"]["lat"],
                lng=place["geometry"]["location"]["lng"],
                distance_km=radius_km,
                duration_min=minutes,
                rating=place.get("rating"),
                open_now=place.get("opening_hours", {}).get("open_now") if place.get("opening_hours") else None,
                source="google",
                url=f"https://www.google.com/maps/place/?q=place_id:{place['place_id']}",
                photo_url=f"https://maps.googleapis.com/maps/api/place/photo?maxwidth=400&photoreference={place['photos'][0]['photo_reference']}&key={GOOGLE_PLACES_API_KEY}" if place.get("photos") else None,
                parking=None,
                opening_hours=None
            )
        )

    return suggestions
