from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, UniqueConstraint
from sqlalchemy.sql import func
from app.db.database import Base
import uuid

class DetourSuggestion(Base):
    __tablename__ = "detour_suggestions"

    id = Column(Integer, primary_key=True, index=True)
    detour_type = Column(String, nullable=False)  # food / event / souvenir
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)
    distance_km = Column(Float, nullable=False)
    duration_min = Column(Integer, nullable=False)
    rating = Column(Float, nullable=True)
    open_now = Column(Boolean, nullable=True)
    opening_hours = Column(Text, nullable=True)
    parking = Column(String, nullable=True)  # "あり" / "なし" / "不明"
    source = Column(String, nullable=False)  # google / hotpepper / connpass
    url = Column(String, nullable=True)
    photo_url = Column(String, nullable=True)
    chosen_at = Column(DateTime(timezone=True), server_default=func.now())
    note = Column(Text, nullable=True)

# 追加: 生成した説明文を保存するテーブル
class SpotSummary(Base):
    __tablename__ = "spot_summaries"
    __table_args__ = (UniqueConstraint("source", "source_id", name="uq_source_source_id"),)

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    source = Column(String(32), index=True)       # google / hotpepper / connpass / local
    source_id = Column(String(128), index=True)   # place_id 等

    name = Column(String(256))
    lat = Column(Float)
    lng = Column(Float)

    short_text_ja = Column(String(120), nullable=True)  # 50文字程度
    long_text_ja = Column(Text, nullable=True)          # 詳細説明

    provider = Column(String(64), default="gemini-1.5-flash")
    lang = Column(String(8), default="ja")
    tokens = Column(Integer, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())