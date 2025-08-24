# app/services/places.py
from dotenv import load_dotenv
load_dotenv() # .env ファイルから環境変数を読み込む
import os
import httpx

USE = os.getenv("USE_GOOGLE_PLACES", "false").lower() == "true"
KEY = os.getenv("GOOGLE_MAPS_API_KEY") or ""
REGION = os.getenv("GOOGLE_PLACES_REGION", "jp")
LANG = os.getenv("GOOGLE_PLACES_LANGUAGE", "ja")


def _need_key():
    if not KEY:
        raise RuntimeError("GOOGLE_MAPS_API_KEY is not set")

async def predictions(input: str, limit: int = 3):
    if not USE:
        return MOCK_PREDS[:limit]

    _need_key()
    url = "https://maps.googleapis.com/maps/api/place/autocomplete/json"
    params = {
        "input": input,
        "key": KEY,
        "components": f"country:{REGION}",
        "language": LANG,
        # "types": "geocode",  # 施設に限定したい場合は有効化
    }

    async with httpx.AsyncClient(timeout=10) as cli:
        r = await cli.get(url, params=params)
        r.raise_for_status()
        data = r.json()
        status = data.get("status")

        if status == "OK":
            out = []
            # 上限は念のため 3 に丸めておく
            topn = max(0, min(limit, 3))
            for p in data.get("predictions", [])[:topn]:
                out.append({
                    "description": p.get("description"),
                    "place_id": p.get("place_id"),
                    "structured_formatting": p.get("structured_formatting", {}),
                })
            return out

        if status == "ZERO_RESULTS":
            return []

        # それ以外はエラーメッセージを表に出す
        raise RuntimeError(f"Places Autocomplete error: {data.get('error_message', status)}")

async def details(place_id: str):
    if not USE:
        return MOCK_DETAIL

    _need_key()
    url = "https://maps.googleapis.com/maps/api/place/details/json"
    params = {
        "place_id": place_id,
        "key": KEY,
        "language": LANG,
        "fields": "place_id,name,formatted_address,geometry,types",
    }

    async with httpx.AsyncClient(timeout=10) as cli:
        r = await cli.get(url, params=params)
        r.raise_for_status()
        data = r.json()
        status = data.get("status")

        if status == "OK":
            return data.get("result")

        raise RuntimeError(f"Places Details error: {data.get('error_message', status)}")
