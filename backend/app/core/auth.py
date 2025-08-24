import os
from fastapi import Header, HTTPException

# --- 簡易APIキー保護（.env に ADMIN_API_KEY がある時だけ有効化）---
ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "").strip()

def maybe_require_admin(x_api_key: str = Header(default="")):
    """ADMIN_API_KEY が設定されている場合のみ、X-API-Key ヘッダをチェック"""
    if ADMIN_API_KEY and x_api_key != ADMIN_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
