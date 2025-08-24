# app/schemas/detour.py
from pydantic import BaseModel, Field, ConfigDict  # 修正8/21: v2対応のためConfigDictを導入
from typing import Literal, List, Optional
from enum import Enum

# モードとタイプ（既存）
class TravelMode(str, Enum):
    walk = "walk"
    drive = "drive"

class DetourType(str, Enum):
    food = "food"
    event = "event"
    spot = "spot"      #→ローカル名所8/22きたな
    souvenir = "souvenir"

# 🔍 検索クエリ（リクエスト用）
class DetourSearchQuery(BaseModel):
    lat: float
    lng: float
    minutes: int = Field(..., ge=1, le=120)
    mode: TravelMode
    detour_type: DetourType
    categories: Optional[List[str]] = None  # 例: ["ramen","cafe"]
    exclude_ids: Optional[List[str]] = None
    seed: Optional[int] = None
    radius_m: Optional[int] = Field(default=1200, ge=100, le=10000)
    local_only: bool = False   # 修正8/21: 「非チェーンのみ」抽出フラグ（外部API検索は行う）
    history_only: bool = False  # 追加8/21: DB履歴のみを返す（オフライン/キャッシュ用）
    keyword: Optional[str] = None   # ← 追加（イベント/名所の任意キーワード）

# 📍 検索結果スポット（レスポンス用）
class DetourSuggestion(BaseModel):
    id: Optional[str] = None              # UUIDベースに変更（DB主キー対応）
    name: str
    description: Optional[str] = None     # 一言ガイダンス（後で生成）
    lat: float
    lng: float
    distance_km: float
    duration_min: int
    eta_text: str                      # ← 追加（"徒歩約◯分・◯m" など表示用）
    source: Literal["google", "hotpepper", "connpass", "yolp", "local"]  # 修正8/21: Literalに拡張（local対応）
    detour_type: DetourType            # ← 追加（フロントのタブ/表示切替用）
    # 追加情報（任意）
    url: Optional[str] = None
    address: Optional[str] = None      # ← 追加（YOLP/connpass）
    rating: Optional[float] = None
    reviews_count: Optional[int] = None # ← 追加（Google等）
    open_now: Optional[bool] = None
    opening_hours: Optional[str] = None
    parking: Optional[str] = None         # "あり/なし/不明"
    photo_url: Optional[str] = None
    created_at: Optional[str] = None      # DBの登録日時（レスポンス用）
    categories: List[str] = Field(default_factory=list)  # ← 追加（検索語/分類の表示）

    # Pydantic v2: ORMオブジェクトからの属性取り出しを許可
    model_config = ConfigDict(from_attributes=True)  # 修正8/21

# 🕓 履歴アイテム
class DetourHistoryItem(BaseModel):
    id: int
    detour_type: DetourType
    name: str
    lat: float
    lng: float
    chosen_at: str
    note: Optional[str] = None

# 🧾 推薦レスポンス（一覧形式）
class RecommendResponse(BaseModel):
    spots: List[DetourSuggestion]  # 修正8/21
