from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Float, DateTime, func, UniqueConstraint, ForeignKey, Text, Integer
import uuid, datetime as dt
from sqlalchemy import Column, Integer, String #からちゃん追加
#from sqlalchemy.ext.declarative import declarative_base #からちゃん追加
#Base = declarative_base() #からちゃん追加
from app.db.database import Base   # ← ここが超重要：再定義せず共通Baseを使う

# ✅ DetourSuggestion / SpotSummary は “本家” に集約
from app.models.detour_suggestion import DetourSuggestion, SpotSummary

class Destination(Base):
    __tablename__ = "destinations"
    __table_args__ = (UniqueConstraint("place_id", name="uq_dest_place_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    place_id: Mapped[str] = mapped_column(String(128), index=True)
    name: Mapped[str] = mapped_column(String(256))
    address: Mapped[str] = mapped_column(String(512))
    lat: Mapped[float] = mapped_column(Float)
    lng: Mapped[float] = mapped_column(Float)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Guides へのリレーション（1:N）
    guides: Mapped[list["Guide"]] = relationship(
        "Guide", back_populates="destination", cascade="all, delete-orphan"
    )

class VisitHistory(Base):
    __tablename__ = "visit_histories"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    # ユーザー未ログインでも使えるよう nullable True
    user_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    destination_id: Mapped[str] = mapped_column(String(36), ForeignKey("destinations.id"), index=True, nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    destination = relationship("Destination", back_populates="visits")
    guides: Mapped[list["Guide"]] = relationship("Guide", back_populates="visit", cascade="all, delete-orphan")

# Destination にリレーションを追加（クラス内に追記）
# guides は既にある想定。無ければ合わせて追加してください
Destination.visits = relationship("VisitHistory", back_populates="destination", cascade="all, delete-orphan")


class Guide(Base):
    __tablename__ = "guides"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    destination_id: Mapped[str] = mapped_column(String(36), ForeignKey("destinations.id"), index=True, nullable=False)
    visit_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("visit_histories.id"), index=True, nullable=True)
    guide_text: Mapped[str] = mapped_column(Text, nullable=False)
    voice: Mapped[str | None] = mapped_column(String(64), nullable=True)
    style: Mapped[str | None] = mapped_column(String(64), nullable=True)
    audio_url: Mapped[str] = mapped_column(String(512), nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    
    # Destination テーブルとのリレーション
    destination = relationship("Destination", back_populates="guides")
    visit = relationship("VisitHistory", back_populates="guides")

#models.DetourSuggestion の対応
#class DetourSuggestion(Base):
    #__tablename__ = "detour_suggestions"

    #id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    #name: Mapped[str] = mapped_column(String(256))
    #description: Mapped[str | None] = mapped_column(String(512), nullable=True)
    #lat: Mapped[float] = mapped_column(Float)
    #lng: Mapped[float] = mapped_column(Float)
    #distance_km: Mapped[float] = mapped_column(Float)
    #duration_min: Mapped[int] = mapped_column()
    #rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    #open_now: Mapped[bool | None] = mapped_column(nullable=True)
    #opening_hours: Mapped[str | None] = mapped_column(String(256), nullable=True)
    #parking: Mapped[str | None] = mapped_column(String(64), nullable=True)
    #source: Mapped[str] = mapped_column(String(32))  # e.g. 'google'
    #url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    #photo_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    #created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False)
    hashed_password = Column(String(255), nullable=False) 
    name = Column(String(255)) 
    gender = Column(String(10)) 
    age_group = Column(String(50))  

from app.models import detour_history  # ← これでテーブルがBaseに登録される
