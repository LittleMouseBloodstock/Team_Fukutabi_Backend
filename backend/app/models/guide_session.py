from sqlalchemy import Column, Integer, String, Enum, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from app.db.session import Base

class GuideType(str, enum.Enum):
    TALK = "talk"       # おしゃべり旅ガイド
    DETOUR = "detour"   # 寄り道ガイド

class GuideSession(Base):
    __tablename__ = "guide_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    guide_type = Column(Enum(GuideType), nullable=False)
    title = Column(String(200), nullable=False)        # 例: "浅草観光ガイド"
    subtitle = Column(String(200), nullable=True)      # 例: "おしゃべり旅ガイド"
    description = Column(Text, nullable=True)          # リスト要約文

    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    ended_at = Column(DateTime, nullable=True)
    duration_min = Column(Integer, nullable=True)      # 所要時間（分）

    spots_count = Column(Integer, default=0, nullable=False)  # 提案/訪問スポット数など

    user = relationship("User", back_populates="guide_sessions")
