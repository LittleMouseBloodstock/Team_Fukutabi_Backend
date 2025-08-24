# backend/app/services/events.py
from dotenv import load_dotenv
load_dotenv()

print(f"[WIRE] events.py loaded: {__file__}")  # ★どのファイルが実際に使われているか表示

import os
import httpx
import datetime as dt
import re
import unicodedata  # ★ 追加
from typing import List, Dict, Optional, Union
from .geo import haversine_km, minutes_to_radius_km

# ==== 設定 ====
YOLP_APP_ID = os.getenv("YOLP_APP_ID")

# チェーン除外（必要に応じて拡張）
_CHAIN = r"(すき家|マクドナルド|吉野家|ガスト|コメダ|スタバ|ドトール|セブンイレブン|ローソン|ファミリーマート|サイゼリヤ|丸亀製麺|びっくりドンキー|ココイチ|はま寿司|スシロー|ユニクロ)"
def _is_chain(name: str) -> bool:
    return bool(re.search(_CHAIN, name or ""))

# 既存の上の方（_CHAIN のすぐ下あたり）に追加
_CORP = re.compile(
    r"(株式会社|有限会社|合同会社|合名会社|合資会社"
    r"|本社|支店|営業所|センター|事務所|工場|ディーラー"
    r"|（株）|\(株\)|㈱|㍿"      # ←「（株）」「(株)」「㈱」「㍿」をカバー
    r"|（有）|\(有\)|㈲)"        # ← 有限会社の略記もついでに
)

# 小売ジャンルを弾く（衣料/アパレル/SCなど）
_GENRE_DROP = re.compile(r"(衣料|服|アパレル|靴|鞄|百貨店|スーパー|ショッピングセンター|ショッピングモール|量販店|家電|ホームセンター|ドラッグストア)")
# “フェス” は “フェスタ”に誤反応しないように (?!タ) を入れる

_EVENT_PAT = re.compile(
    r"(イベント|祭り?|花火|マルシェ|フリマ|学園祭|文化祭|盆踊り|縁日|ライトアップ|イルミネーション|収穫祭|新酒|納涼|音楽祭|ビアガーデン|夏祭り|冬祭り|フェス(?!タ))"
)


# 季節ワード（ヒット率を底上げ）
_SEASON = {
    1:["新年","初詣","冬祭り"],
    2:["雪","バレンタイン"],
    3:["桜","春祭り","フェス"],
    4:["花見","マルシェ"],
    5:["GW","祭"],
    6:["初夏","ホタル"],
    7:["夏祭り","花火"],
    8:["花火","フェス", "ビアガーデン", "盆踊り", "キャンプ"],
    9:["秋祭り","収穫祭"],
    10:["紅葉","ハロウィン","マルシェ"],
    11:["新酒","ライトアップ"],
    12:["イルミネーション","クリスマス","年末"],
}

def _seed_keywords(keyword: Optional[str], categories: Optional[List[str]]) -> List[str]:
    seeds: List[str] = []
    if keyword:
        seeds.append(keyword)
    if categories:
        seeds.extend([c for c in categories if c])
    # 汎用イベント語
    seeds += ["イベント","祭","祭り","花火","フェス","マルシェ","フリマ"]
    # 季節語
    seeds += _SEASON.get(dt.date.today().month, [])
    # 重複除去
    uniq: List[str] = []
    seen = set()
    for s in seeds:
        if s and s not in seen:
            seen.add(s)
            uniq.append(s)
    return uniq[:8]

# ==== 逆ジオコーディング（残置・任意利用） ====
async def reverse_geocode_city(lat: float, lng: float) -> Optional[str]:
    """Nominatimで市区町村名を取得（必要ならキーワードに追加して使える）"""
    url = "https://nominatim.openstreetmap.org/reverse"
    params = {"format": "jsonv2", "lat": lat, "lon": lng}
    headers = {"User-Agent": "SerendiGo/1.0"}
    async with httpx.AsyncClient(timeout=10, headers=headers) as client:
        r = await client.get(url, params=params)
        j = r.json()
    addr = j.get("address", {})
    return addr.get("city") or addr.get("town") or addr.get("village") or addr.get("municipality")

# ==== メイン: イベント検索（YOLPローカルサーチで“イベント系POI”を拾う） ====
async def connpass_events(  # ← 既存の関数名を維持（中身はYOLP）
    lat: float,
    lng: float,
    minutes: int,
    keyword: Optional[str] = None,
    categories: Optional[List[str]] = None,
    local_only: bool = False,
    mode: Union[str, None] = None,   # ★追加

) -> List[Dict]:
    """
    近傍の“イベント系スポット/催事名のPOI”をYOLPで検索して返す。
    ※ 開催日時は取得できない前提（施設・催事名ベース）
    戻り値: {id,name,description,lat,lng,url,address,categories,source="yolp"} の配列
    """
    if not YOLP_APP_ID:
        print("[YOLP] APP_ID missing -> return []")  # ★ログ

    # ★徒歩/車で半径を切替（modeが未指定ならwalk扱い）
    mode_str = (mode.value if hasattr(mode, "value") else mode) or "walk"
    try:
        radius_km = minutes_to_radius_km(minutes, mode_str)
    except Exception:
        radius_km = minutes_to_radius_km(minutes, "walk")

    queries = _seed_keywords(keyword, categories)
    print(f"[YOLP] queries={queries} radius_km={radius_km:.2f} lat={lat} lng={lng} mode={mode_str}")  # ★ログ

    base = "https://map.yahooapis.jp/search/local/V1/localSearch"

    items: List[Dict] = []
    async with httpx.AsyncClient(timeout=10) as client:
        for q in queries:
            params = {
                "appid": YOLP_APP_ID,
                "lat": lat,
                "lon": lng,
                "dist": max(0.5, min(radius_km, 20.0)),  # km, 0.5〜20に丸め
                "query": q,
                "sort": "dist",
                "results": 50,
                "output": "json",          # ★ これが超重要（デフォはXML）
            }
            try:
                r = await client.get(base, params=params)
                r.raise_for_status()
                data = r.json()
            except Exception as ex:
                print(f"[YOLP] request error q={q} ex={ex!r}")
                continue


            feats = data.get("Feature") or []
            print(f"[YOLP] q={q} hits={len(feats)}")  # ログ

            for f in feats:
                # 置き換え：正規化してからフィルタ判定
                name_raw = (f.get("Name") or "").strip()
                name = unicodedata.normalize("NFKC", name_raw)  # ㈱/（ ）等を半角の(株)等に正規化
                if not name:
                    continue

                # 1) 会社・業務系ワードを除外
                if _CORP.search(name) or _is_chain(name):
                    # print(f"[YOLP] drop(corp): {name}")
                    continue
                if local_only and _is_chain(name):
                    # print(f"[YOLP] drop(chain): {name}")
                    continue

                # 2) 座標抽出
                coords = (f.get("Geometry") or {}).get("Coordinates") or ""
                if "," not in coords:
                    continue
                lng2_s, lat2_s = coords.split(",", 1)
                try:
                    lat2 = float(lat2_s)
                    lng2 = float(lng2_s)
                except ValueError:
                    # 念のため
                    parts = coords.split(",")
                    if len(parts) != 2:
                        continue
                    lng2 = float(parts[0]); lat2 = float(parts[1])

                d_km = haversine_km(lat, lng, lat2, lng2)
                if d_km > radius_km + 0.2:
                    continue

                # 3) ジャンル名や説明文を抽出してイベント語判定に使う
                prop = f.get("Property") or {}
                genres_raw = prop.get("Genre") or []
                genre_names: List[str] = []
                if isinstance(genres_raw, list):
                    for g in genres_raw:
                        if isinstance(g, dict):
                            n = (g.get("Name") or "").strip()
                            if n: genre_names.append(n)
                        else:
                            n = str(g).strip()
                            if n: genre_names.append(n)
                elif isinstance(genres_raw, dict):
                    n = (genres_raw.get("Name") or "").strip()
                    if n: genre_names.append(n)

                # CatchCopy/Lead などの短文もイベント語検出に使う
                catch = (prop.get("CatchCopy") or "")
                lead  = (prop.get("Lead") or "")

                # イベント語を “単語っぽく” 判定（フェスタは除外）
                haystack = " ".join([name, " ".join(genre_names), catch, lead])
                if not _EVENT_PAT.search(haystack):
                    continue


                # 5) 合格：アイテム化
                items.append({
                    "id": f.get("Id") or f"{round(lat2,6)},{round(lng2,6)}:{name}",
                    "name": name,
                    "description": catch or "",
                    "lat": lat2,
                    "lng": lng2,
                    "address": prop.get("Address"),
                    "url": (prop.get("Detail") or {}).get("PcUrl"),
                    "categories": [q] + (genre_names[:3] if genre_names else []),  # ← ジャンル名も混ぜる
                    "source": "yolp",
                })

    # 重複除去の直前あたりに追加
    if not items:
        # 救済：会社ワードだけ除外して、イベント語チェックは緩める
        for f in feats:
            name = (f.get("Name") or "").strip()
            if not name or _CORP.search(name) or (local_only and _is_chain(name)):
                continue
            coords = (f.get("Geometry") or {}).get("Coordinates") or ""
            if "," not in coords:
                continue
            lng2_s, lat2_s = coords.split(",", 1)
            try:
                lat2 = float(lat2_s); lng2 = float(lng2_s)
            except ValueError:
                parts = coords.split(",")
                if len(parts) != 2:
                    continue
                lng2 = float(parts[0]); lat2 = float(parts[1])

            d_km = haversine_km(lat, lng, lat2, lng2)
            if d_km > radius_km + 0.2:
                continue

            prop = f.get("Property") or {}
            items.append({
                "id": f.get("Id") or f"{round(lat2,6)},{round(lng2,6)}:{name}",
                "name": name,
                "description": (prop.get("CatchCopy") or ""),
                "lat": lat2,
                "lng": lng2,
                "address": prop.get("Address"),
                "url": (prop.get("Detail") or {}).get("PcUrl"),
                "categories": [q],
                "source": "yolp",
            })

            
    # 重複除去（座標+名称）
    seen = set()
    uniq: List[Dict] = []
    for it in sorted(items, key=lambda x: (x["name"], x["lat"], x["lng"])):
        k = (round(it["lat"], 6), round(it["lng"], 6), it["name"])
        if k in seen:
            continue
        seen.add(k)
        uniq.append(it)
    return uniq[:50]
