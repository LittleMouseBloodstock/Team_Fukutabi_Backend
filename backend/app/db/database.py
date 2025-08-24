import os
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import declarative_base, sessionmaker, Session

load_dotenv()

DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_NAME = os.getenv("DB_NAME")
SSL_CA_PATH = os.getenv("SSL_CA_PATH")  # .envで設定

# DB URL を安全に構築
database_url = URL.create(
    drivername="mysql+pymysql",
    username=DB_USER,
    password=DB_PASSWORD,
    host=DB_HOST,
    port=int(DB_PORT),
    database=DB_NAME,
    query={"charset": "utf8mb4"},
)

# SSL 証明書の絶対パス解決
connect_args = {}
if SSL_CA_PATH:
    ca_abs = str(Path(SSL_CA_PATH).resolve())  # ← ここで絶対パスに変換！
    print(f"★ mysql ssl ca (resolved) => {ca_abs}  exists={Path(ca_abs).is_file()}")
    if not Path(ca_abs).is_file():
        raise FileNotFoundError(f"SSL_CA_PATH not found: {ca_abs}")
    connect_args = {"ssl": {"ca": ca_abs}}

engine = create_engine(
    database_url,
    pool_pre_ping=True,
    pool_recycle=1800,
    echo=False,
    connect_args=connect_args,
)

Base = declarative_base()
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, class_=Session)

def init_db() -> None:
    from app.db import models  # noqa: F401
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
