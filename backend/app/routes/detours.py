# backend/app/routes/detours.py
from fastapi import APIRouter, Query, Depends, HTTPException
from typing import List, Optional
import math, uuid, re, unicodedata  # 追加8/21: チェーン判定のため re を使用
from datetime import datetime  # 追加8/21: created_at統一のため
from sqlalchemy import select, desc
from sqlalchemy.orm import Session
from app.schemas.detour import (
    DetourSearchQuery,
    DetourSuggestion,
    DetourHistoryItem,
    TravelMode,   # 追加8/21: Query型を厳密化
    DetourType,   # 追加8/21: Query型を厳密化
)
from app.services.geo import minutes_to_radius_km, haversine_km
from app.services.places_nearby import google_nearby
from app.services.events import reverse_geocode_city, connpass_events
from app.db.database import get_db                  # ← 同期Sessionを返す
from app.models.detour_history import DetourHistory
from app.models.detour_suggestion import SpotSummary  # ← 追加：説明キャッシュ用8/23

router = APIRouter(prefix="/detour", tags=["Detour"])  # 修正8/21: prefix/tagsを明示

# 追加8/21: 簡易チェーン判定（必要に応じて拡張）
_CHAIN_RE = re.compile(
    r"(マクドナルド|吉野家|スターバックス|ドトール|すき家|CoCo壱|サイゼ|ガスト|松屋|ミスタードーナツ|ケンタッキー|"
    r"セブン-?イレブン|ファミリーマート|ローソン|コメダ|モスバーガー|バーガーキング|はま寿司|スシロー|くら寿司|かっぱ寿司|"
    r"リンガーハット|王将|ココス|ビックカメラ|ヤマダ電機|ケーズデンキ|イオン|ユニクロ|無印良品)"
)

# 法人表記・全角/半角のゆらぎを除去して表示名を正規化
_CORP_RE = re.compile(
    r"(株式会社|（株）|\(株\)|㈱|有限会社|（有）|\(有\)|㈲|合同会社|合名会社|合資会社|"
    r"一般社団法人|一般財団法人|公益社団法人|公益財団法人)"
)

def _is_chain(name: str) -> bool:  # 追加8/21
    return bool(_CHAIN_RE.search(name or ""))

def _eta_text(mode: str, minutes: int, meters: int) -> str:
    return f"徒歩約{minutes}分・{meters}m" if mode == "walk" else f"車で約{minutes}分・{meters}m"

def _clean_shop_name(name: str) -> str:
    if not name:
        return name
    # 全角→半角などを揃える
    s = unicodedata.normalize("NFKC", name)
    # 法人表記の除去
    s = re.sub(_CORP_RE, "", s)
    # 連続スペースを1つに・前後の装飾/空白を除去
    s = re.sub(r"\s{2,}", " ", s).strip(" 　・,.-")
    return s or name

# =========================
# コア検索（純粋関数）
# =========================
async def search_detours_core(query: DetourSearchQuery, db: Session) -> List[DetourSuggestion]:  # 修正8/21
    """
    history_only=True -> DB履歴のみを返す。
    local_only=True  -> 外部API検索は行い、結果からチェーン店舗を除外する。
    """  # 修正8/21

    # 検索コアの冒頭で mode を文字列化
    mode_str = query.mode.value if hasattr(query.mode, "value") else str(query.mode)

    # 半径の決定（優先: query.radius_m、なければ minutes→km から算出）
    if query.radius_m is not None:
        radius_m = int(query.radius_m)
        radius_km_from_param = radius_m / 1000.0
    else:
        radius_km_from_param = None
    # minutes 由来の半径
    radius_km_from_minutes = minutes_to_radius_km(query.minutes, query.mode)

    # イベントは minutes ベースを優先（= 広い方を採用）
    if (getattr(query.detour_type, "value", str(query.detour_type)) == "event"):
        radius_km = max(radius_km_from_minutes, radius_km_from_param or 0)
    else:
        radius_km = radius_km_from_param if radius_km_from_param is not None else radius_km_from_minutes
    radius_m = int(radius_km * 1000)
    # -------------------------
    # history_only: DB（履歴）だけで返す
    # -------------------------
    if query.history_only:  # 追加8/21
        rows = (
            db.execute(
                select(DetourHistory).order_by(desc(DetourHistory.id)).limit(100)
            ).scalars().all()
        )
        suggestions: List[DetourSuggestion] = []
        for r in rows:
            d_km = haversine_km(query.lat, query.lng, r.lat, r.lng)
            if radius_km <= 0 or d_km <= radius_km * 1.5:
                duration_min = (
                    math.ceil((d_km / radius_km) * query.minutes) if radius_km > 0 else query.minutes
                )
                meters = int(d_km * 1000)
                suggestions.append(
                    DetourSuggestion(
                        id=str(uuid.uuid4()),
                        name=_clean_shop_name(r.name),
                        description=r.note,
                        lat=r.lat,
                        lng=r.lng,
                        distance_km=d_km,
                        duration_min=duration_min,
                        rating=None,
                        open_now=None,
                        opening_hours=None,
                        parking=None,
                        source="local",  # DB由来は "local"
                        url=None,
                        photo_url=None,
                        created_at=(r.chosen_at or datetime.utcnow()).isoformat(),
                        eta_text=_eta_text(mode_str, duration_min, meters),  # ★追加: 必須
                        detour_type=query.detour_type,                      # ★追加: 必須
                    )
                )
        suggestions.sort(key=lambda x: x.distance_km)
        return suggestions[:3]

    # -------------------------
    # 外部API検索（通常モード）
    # -------------------------
    items: List[dict] = []

    # detour_type 分岐：spot/food/souvenir は google_nearby、event は connpass 等
    dt = query.detour_type.value if hasattr(query.detour_type, "value") else str(query.detour_type)

    if dt in ("spot", "food", "souvenir"):
        g = await google_nearby(
            query.lat, query.lng, radius_m,
            detour_type=dt,
            categories=query.categories,
        )
        items.extend(g)

    elif dt == "event":
        evs = await connpass_events(
            lat=query.lat,
            lng=query.lng,
            minutes=query.minutes,
            keyword=getattr(query, "keyword", None),
            categories=getattr(query, "categories", None),
            local_only=getattr(query, "local_only", False),
            mode=mode_str,
        )
        out = []
        for e in evs:
            if e.get("lat") and e.get("lng"):
                d = haversine_km(query.lat, query.lng, float(e["lat"]), float(e["lng"]))
                if radius_km <= 0 or d <= radius_km * 1.5:
                    e["distance_km"] = d
                    e["duration_min"] = math.ceil(query.minutes * (d / radius_km)) if radius_km > 0 else query.minutes
                    e["open_now"] = None
                    e["rating"] = None
                    e["parking"] = None
                    e["photo_url"] = None
                    e["opening_hours"] = e.get("opening_hours")
                    e["source"] = e.get("source") or "yolp"  # ← connpass → yolp に変更
                    out.append(e)
        items.extend(out)  # ← ここ必須！

    # 距離/分の補完
    for x in items:
        if "distance_km" not in x:
            x["distance_km"] = haversine_km(query.lat, query.lng, x["lat"], x["lng"])
        if "duration_min" not in x:
            x["duration_min"] = math.ceil((x["distance_km"] / radius_km) * query.minutes) if radius_km > 0 else query.minutes

    # local_only=True のときはチェーンを除外（＝ローカル店舗優先）
    if query.local_only:
        items = [x for x in items if not _is_chain(_clean_shop_name(x.get("name", "")))]

    # ソートとトップ3選定
    items.sort(key=lambda x: (x["distance_km"], -(x.get("rating") or 0)))
    top3 = items[:3]

    # DetourSuggestion に整形
    results: List[DetourSuggestion] = []
    now_iso = datetime.utcnow().isoformat()

    for x in top3:
        meters = int(x["distance_km"] * 1000)

        # --- ここから：説明キャッシュの取得/生成 -------------------------
        src = (x.get("source") or "google")
        sid = _detect_source_id(x)

        # 1) 既存の短文があれば使う
        desc = None
        row = _summary_get(db, src, sid)
        if row and row.short_text_ja:
            desc = row.short_text_ja
        else:
            # 2) なければ同期で最小生成（3件だけなので待ち時間は軽め）
            #    address / category が無ければ None でOK
            g = await gemini_summarize_place(
                name=x.get("name", ""),
                address=x.get("address") or x.get("vicinity"),
                category=x.get("category")
            )
            if not g.get("error"):
                desc_short = (g.get("short") or "").strip()
                if desc_short:
                    desc = desc_short
                    _summary_upsert(
                        db,
                        source=src, source_id=sid,
                        name=x.get("name", ""),
                        lat=float(x["lat"]), lng=float(x["lng"]),
                        short_text=g.get("short"), long_text=g.get("long"),
                        provider="gemini-1.5-flash", lang="ja", tokens=g.get("tokens")
                    )
        # 生成・取得ともに無ければ簡易フォールバック
        if not desc:
            desc = x.get("description") or f"{x.get('name','このスポット')}は周辺で立ち寄りやすい場所です。"

        results.append(
            DetourSuggestion(
                id=str(uuid.uuid4()),
                name=_clean_shop_name(x["name"]),  # ついでに表示名も正規化
                description=desc,  # ← 生成 or 取得した短文を反映
                lat=float(x["lat"]),
                lng=float(x["lng"]),
                distance_km=x["distance_km"],
                duration_min=x["duration_min"],
                rating=x.get("rating"),
                open_now=x.get("open_now"),
                opening_hours=x.get("opening_hours"),
                parking=x.get("parking"),
                source=x.get("source") or "google",
                url=x.get("url"),
                photo_url=x.get("photo_url"),
                created_at=now_iso,
                eta_text=_eta_text(mode_str, x["duration_min"], meters),  # ★順序修正
                detour_type=query.detour_type,
            )
        )
    return results

# --- summaries helper (append-only) ------------------------------------
def _summary_get(db: Session, source: str, source_id: str):
    return db.execute(
        select(SpotSummary).where(
            SpotSummary.source == source,
            SpotSummary.source_id == source_id
        )
    ).scalar_one_or_none()

def _summary_upsert(
    db: Session, *, source: str, source_id: str, name: str, lat: float, lng: float,
    short_text: str | None, long_text: str | None, provider: str = "gemini-1.5-flash", lang: str = "ja",
    tokens: int | None = None
):
    row = _summary_get(db, source, source_id)
    if row is None:
        row = SpotSummary(
            source=source, source_id=source_id, name=name, lat=lat, lng=lng,
            short_text_ja=short_text, long_text_ja=long_text, provider=provider, lang=lang, tokens=tokens
        )
        db.add(row)
    else:
        # 既存が空なら更新（上書きしすぎない運用）
        row.short_text_ja = short_text or row.short_text_ja
        row.long_text_ja  = long_text  or row.long_text_ja
        row.provider = provider
        row.lang = lang
        row.tokens = tokens if tokens is not None else row.tokens
    db.commit()
    return row

def _detect_source_id(x: dict) -> str:
    # 外部APIの形の違いを吸収：place_id / id / なければ座標ハッシュでフォールバック
    sid = x.get("place_id") or x.get("id")
    if sid:
        return str(sid)
    return f"{x.get('lat'):.6f},{x.get('lng'):.6f}"

# =========================
# ルーター（公開API）
# =========================
@router.get("/search", response_model=List[DetourSuggestion])
async def search_detours(
    lat: float = Query(...),
    lng: float = Query(...),
    mode: TravelMode = Query(...),  # 修正8/21: 型をLiteralに
    minutes: int = Query(..., ge=1, le=120),
    detour_type: DetourType = Query(...),  # 修正8/21: 型をLiteralに
    categories: Optional[List[str]] = Query(None),
    exclude_ids: Optional[List[str]] = Query(None),
    seed: Optional[int] = Query(None),
    radius_m: Optional[int] = Query(None, ge=100, le=10000),
    local_only: bool = Query(False),    # 修正8/21: 非チェーンのみ抽出
    history_only: bool = Query(False),  # 追加8/21: DB履歴のみ
    db: Session = Depends(get_db),
):
    query = DetourSearchQuery(
        lat=lat,
        lng=lng,
        minutes=minutes,
        mode=mode,
        detour_type=detour_type,
        categories=categories,
        exclude_ids=exclude_ids,
        seed=seed,
        radius_m=radius_m if radius_m is not None else None,
        local_only=local_only,
        history_only=history_only,
    )
    return await search_detours_core(query, db)

@router.post("/choose", response_model=DetourHistoryItem)  # 追加8/21
async def choose_detour(  # 追加8/21
    detour: DetourSuggestion,
    detour_type: DetourType = Query(...),
    db: Session = Depends(get_db),
):
    rec = DetourHistory(
        detour_type=detour_type,
        name=detour.name,
        lat=detour.lat,
        lng=detour.lng,
        note=detour.description,
    )
    db.add(rec)
    db.commit()           # 同期Sessionのため await 不要
    db.refresh(rec)
    return DetourHistoryItem(
        id=rec.id,
        detour_type=rec.detour_type,
        name=rec.name,
        lat=rec.lat,
        lng=rec.lng,
        chosen_at=rec.chosen_at.isoformat(),
        note=rec.note,
    )

# --- Step2: Gemini mini summarizer (append-only) -----------------------
# --- Gemini mini summarizer (hardened) -----------------------------
import os, json, httpx, re

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

_GEMINI_SYSTEM = (
    "あなたは観光&グルメ案内のプロ編集者です。"
    "以下の店舗の魅力を日本語で簡潔に要約してください。誇張は避け、事実ベースで。"
    "出力は必ずJSONのみ。コードブロックや```は使わない。前置きの文章も不要。\n"
    "{\n"
    '  "short": "50文字以内の短い説明",\n'
    '  "long": "120〜200文字の詳しい説明"\n'
    "}\n"
)

def _gemini_place_prompt(name: str, address: str | None, category: str | None) -> str:
    return (
        f"店舗名: {name}\n"
        f"住所: {address or '不明'}\n"
        f"カテゴリ: {category or '不明'}\n\n"
        "注意:\n"
        "- 「〜です。」調で。\n"
        "- 固有名詞の誤りを避ける。\n"
        "- 営業時間や価格は推測で断言しない。\n"
        "- 宣伝過多の表現や記号装飾は避ける。\n"
        "- 出力はJSON本文のみ。コードフェンスや語りは一切不要。\n"
    )

def _extract_json_block(text: str) -> str | None:
    # ```json 〜 ``` を剥がす／先頭末尾のゴミを除いて { ... } を抽出
    text = text.strip()
    # コードフェンス除去
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    # 最初の { から最後の } までを貪欲に取得
    m = re.search(r"\{.*\}", text, re.DOTALL)
    return m.group(0) if m else None

def _truncate(s: str, n: int) -> str:
    s = s.replace("\n", " ").strip()
    return s[:n]

async def gemini_summarize_place(name: str, address: str | None = None, category: str | None = None) -> dict:
    if not GEMINI_API_KEY:
        return {"short": None, "long": None, "tokens": None, "error": "GEMINI_API_KEY not set"}

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    payload = {
        "contents": [{
            "role": "user",
            "parts": [{"text": _GEMINI_SYSTEM + "\n\n" + _gemini_place_prompt(name, address, category)}]
        }],
        "generationConfig": {"temperature": 0.5, "maxOutputTokens": 256}
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(url, json=payload)
            r.raise_for_status()
            data = r.json()

        raw = data["candidates"][0]["content"]["parts"][0]["text"]
        raw = raw.strip()

        # JSON抽出を頑強に
        json_str = _extract_json_block(raw) or raw
        short = long_ = None
        try:
            obj = json.loads(json_str)
            short = (obj.get("short") or "").strip() or None
            long_ = (obj.get("long") or "").strip() or None
        except Exception:
            # JSONパースできない場合はヒューリスティックで短文作成
            short = _truncate(raw, 50) or None
            long_  = _truncate(raw, 200) or None

        tokens = (data.get("usageMetadata") or {}).get("totalTokenCount")
        # カード用 short は念のため50字に丸める
        if short:
            short = _truncate(short, 50)
        return {"short": short, "long": long_, "tokens": tokens, "error": None}

    except httpx.HTTPError as e:
        return {"short": None, "long": None, "tokens": None, "error": f"HTTPError: {e}"}
    except Exception as e:
        return {"short": None, "long": None, "tokens": None, "error": f"Error: {e}"}
