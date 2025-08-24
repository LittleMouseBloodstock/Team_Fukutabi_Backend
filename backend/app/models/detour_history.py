from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Integer, String, Float, DateTime
from datetime import datetime
from app.db.database import Base  # あなたの構成に合わせてmodels側のBaseを使用

class DetourHistory(Base):
    __tablename__ = "detour_history"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    detour_type: Mapped[str] = mapped_column(String(20), index=True)
    name: Mapped[str] = mapped_column(String(200))
    lat: Mapped[float] = mapped_column(Float)
    lng: Mapped[float] = mapped_column(Float)
    chosen_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    note: Mapped[str | None] = mapped_column(String(300), nullable=True)
