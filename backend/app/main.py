# app/main.py

# --- 1) GCP ADC を最優先でセット（ルータ import より前に必ず実行） ---
from app.services.google_adc_bootstrap import ensure_adc
ensure_adc()  # GCP_SA_JSON / *_B64 から鍵を書き出し、GOOGLE_APPLICATION_CREDENTIALS を設定

# --- 2) 以降は通常の起動処理 ---
import os
import pathlib
from dotenv import load_dotenv

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from sqlalchemy import text, inspect

from app.db.database import engine, init_db

# ----- ローカル開発用: backend/.env を読み込む（Azure には通常 .env は無い） -----
BASE_DIR = pathlib.Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"
load_dotenv(dotenv_path=ENV_PATH)

# .env に GOOGLE_APPLICATION_CREDENTIALS がある場合のみ、相対→絶対へ解決（ensure_adc の値は上書きしない）
gac = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
if gac:
    if not os.path.isabs(gac):
        gac_abs = (BASE_DIR / gac).resolve()
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(gac_abs)
        print(f"★ cred_path (raw) >> {gac}")
        print(f"★ cred_path (absolute) >> {gac_abs}")
        print(f"★ os.path.exists(cred_path) >> {os.path.exists(gac_abs)}")
else:
    print("⚠️ GOOGLE_APPLICATION_CREDENTIALS は未設定（Azure では ensure_adc() が設定する想定）")

# ----- ここからルータを import（ADC 初期化後！） -----
from app.routes.google_places_api import router as places_router
from app.routes.destination_api import router as destinations_router
from app.routes.visit_and_guide_api import router as visits_router
from app.routes.detours import router as detours_router

from app.routers import detour_adapter
from app.routers import detour_guide

from app.routes import user_register_api
from app.routes import user_login_api

# ----- アプリ本体 -----
app = FastAPI(title="SerendiGo API")

# CORS 設定（必要に応じて本番ドメインを追加）
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://0.0.0.0:3000",
        "https://app-002-gen10-step3-2-node-oshima9.azurewebsites.net"
        # "https://<your-frontend-domain>"  # ← 本番フロントを追加推奨
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# メディア配信（TTS mp3 など）
MEDIA_DIR = BASE_DIR / "media"
app.mount("/media", StaticFiles(directory=MEDIA_DIR), name="media")

# ルータ登録
app.include_router(places_router)
app.include_router(destinations_router)
app.include_router(visits_router)
app.include_router(detours_router)
app.include_router(detour_adapter.router)     # → /detour/...
app.include_router(detour_guide.router)       # → /detour-guide/...
app.include_router(user_login_api.router)
app.include_router(user_register_api.router)

# ヘルスチェック（簡易）
@app.get("/health")
def health():
    return {"status": "ok"}

# ADC/鍵ファイルの可視化ヘルス（起動検証用）
@app.get("/healthz")
def healthz():
    p = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    return {"gac": p, "exists": (os.path.exists(p) if p else False)}

# DB 情報（デバッグ）
@app.get("/__db_info")
def __db_info():
    with engine.connect() as conn:
        db = conn.execute(text("SELECT DATABASE()")).scalar()
        return {"database": db}

@app.get("/__db_tables")
def __db_tables():
    insp = inspect(engine)
    return {"tables": insp.get_table_names()}

# 音声再生のテスト用（任意）
@app.get("/test-audio", response_class=HTMLResponse)
async def test_audio():
    return """
    <html>
        <head><title>音声再生テスト</title></head>
        <body>
            <h1>音声再生テストページ</h1>
            <audio controls>
                <source src="/media/guides/8bbc2851-783b-41e1-90e8-1767a842bcdc.mp3" type="audio/mpeg">
                ブラウザがaudioタグに対応していません。
            </audio>
        </body>
    </html>
    """

# 起動時フック
@app.on_event("startup")
def on_startup():
    # SQLite 等のローカル開発用テーブル作成
    init_db()
