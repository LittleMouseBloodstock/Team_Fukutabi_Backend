# app/main.py
from dotenv import load_dotenv
import pathlib
import os

# backend/.env を明示的に読み込む
env_path = pathlib.Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

# .env の変数を取得
cred_path_raw = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

# backend/ をベースにする（.envとsecretは同じ階層）
base_dir = pathlib.Path(__file__).resolve().parent.parent
cred_path_abs = (base_dir / cred_path_raw).resolve() if cred_path_raw else None

if cred_path_raw:
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(cred_path_abs)
    print(f"★ cred_path (raw) >> {cred_path_raw}")
    print(f"★ cred_path (absolute) >> {cred_path_abs}")
    print(f"★ os.path.exists(cred_path) >> {os.path.exists(cred_path_abs)}")
else:
    print("⚠️ .envに GOOGLE_APPLICATION_CREDENTIALS が定義されていません")
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
# app/main.py どこかに追記（importは上へ）
from sqlalchemy import text, inspect
from app.db.database import engine

# ルーター
from app.routes.google_places_api import router as places_router          # ← AI/外部API系は async のままでOK
from app.routes.destination_api import router as destinations_router      # ← DB同期ルートは def に統一
from app.routes.visit_and_guide_api import router as visits_router
from app.routes.detours import router as detours_router

# ★ 追加：ルータをインポートきたな
from app.routers import detour_adapter
from app.routers import detour_guide

# ★ 追加：ユーザールーターからちゃん
from app.routes import user_register_api
from app.routes import user_login_api

# DB初期化（同期）
from app.db.database import init_db

app = FastAPI(title="SerendiGo API")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "http://0.0.0.0:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 3) DBテーブル作成（SQLiteの開発用）
#Base.metadata.create_all(bind=engine)(一旦コメントアウトbyきたな)

# 4) メディア配信（TTSのmp3 / フォールバックのtxt を返す用）
# app.mount("/media", StaticFiles(directory=os.getenv("MEDIA_ROOT", "./media")), name="media")
media_root = pathlib.Path(__file__).resolve().parent.parent / "media"
app.mount("/media", StaticFiles(directory=pathlib.Path(__file__).parent.parent / "media"), name="media")
# mps3 音声再生のテスト用エンドポイント ※実際の運用では不要、削除可能byからちゃん
from fastapi.responses import HTMLResponse
# メディア配信（ディレクトリが無いと起動エラーになるので作成しておくGPTおすすめbyきたな）
#MEDIA_ROOT = os.getenv("MEDIA_ROOT", "./media")
#os.makedirs(MEDIA_ROOT, exist_ok=True)
#app.mount("/media", StaticFiles(directory=MEDIA_ROOT), name="media")

# ルーター登録（重複なし）
app.include_router(places_router)
app.include_router(destinations_router)
app.include_router(visits_router)
app.include_router(detours_router)
app.include_router(user_login_api.router)

# ヘルスチェック
@app.get("/health")
def health():
    return {"status": "ok"}

# ★ 起動時：同期DBの create_all を1回実行（await しない）
@app.on_event("startup")
def on_startup():
    init_db()

# 音声再生のテスト用エンドポイント
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

@app.get("/__db_info")
def __db_info():
    with engine.connect() as conn:
        db = conn.execute(text("SELECT DATABASE()")).scalar()
        return {"database": db}

@app.get("/__db_tables")
def __db_tables():
    insp = inspect(engine)
    return {"tables": insp.get_table_names()}

# ★ 追加：ルータを登録きたな
app.include_router(detour_adapter.router)  # → /detour/search が生える
app.include_router(detour_guide.router)    # → /detour-guide/search が生える
app.include_router(user_register_api.router)  # ★ 追加：ユーザールーター登