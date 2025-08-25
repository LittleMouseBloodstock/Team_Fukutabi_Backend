# app/services/google_adc_bootstrap.py
"""
環境変数に格納したサービスアカウントJSONを、起動時に"鍵ファイル"として書き出し、
GOOGLE_APPLICATION_CREDENTIALS にそのパスを設定するブートストラップ。

優先順:
  1) GCP_SA_JSON_B64 / GOOGLE_APPLICATION_CREDENTIALS_JSON_B64  (Base64)
  2) GCP_SA_JSON     / GOOGLE_APPLICATION_CREDENTIALS_JSON      (プレーンJSON)
  3) 何も無ければ何もしない（既存 GOOGLE_APPLICATION_CREDENTIALS を尊重）

書き出し先は書き込み可能な場所を自動選択:
  - /home/site/wwwroot/secrets/gcp-sa.json  (Azure Linux App Serviceで一般的)
  - OSの一時ディレクトリ (tempfile.gettempdir())
"""

from __future__ import annotations
import os
import base64
import json
import tempfile
import pathlib
from typing import Optional, Tuple

_BOOTSTRAP_FLAG = "_GCP_ADC_BOOTSTRAPPED"


def _ensure_dir(path: str) -> None:
    pathlib.Path(path).parent.mkdir(parents=True, exist_ok=True)


def _is_writable(path: str) -> bool:
    try:
        _ensure_dir(path)
        with open(path, "a"):
            pass
        return True
    except Exception:
        return False


def _pick_target_path() -> str:
    # App Service でよく使う配置先
    candidate1 = "/home/site/wwwroot/secrets/gcp-sa.json"
    if _is_writable(candidate1):
        return candidate1
    # ダメなら一時フォルダ
    tmp = pathlib.Path(tempfile.gettempdir()) / "gcp-sa.json"
    _ensure_dir(str(tmp))
    return str(tmp)


def _load_from_env() -> Tuple[Optional[str], Optional[str]]:
    """環境変数からJSON本文を取得して返す (content, source_key)。見つからなければ (None, None)。"""
    # Base64 優先
    for key in ("GCP_SA_JSON_B64", "GOOGLE_APPLICATION_CREDENTIALS_JSON_B64"):
        val = os.getenv(key)
        if val:
            try:
                decoded = base64.b64decode(val).decode("utf-8", errors="strict")
                return decoded, key
            except Exception:
                # 誤ってプレーンを入れた場合などは、そのまま扱う
                return val, key

    # プレーンJSON
    for key in ("GCP_SA_JSON", "GOOGLE_APPLICATION_CREDENTIALS_JSON"):
        val = os.getenv(key)
        if val:
            return val, key

    return None, None


def _write_json_file(content: str, path: str) -> str:
    """できるだけJSONとして整形して書く。無理なら生文字列のまま書く。"""
    _ensure_dir(path)
    try:
        # 文字列だがJSONとして正規化できる場合
        obj = json.loads(content)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False)
            f.write("\n")
    except Exception:
        # JSONとして解釈できなければ、そのまま書く（貼り付け時のエスケープ崩れ救済）
        with open(path, "w", encoding="utf-8") as f:
            f.write(content if isinstance(content, str) else str(content))
            f.write("\n")

    # パーミッションは可能なら600へ
    try:
        os.chmod(path, 0o600)
    except Exception:
        pass

    return path


def ensure_adc() -> None:
    """環境変数から鍵を復元して GAC を設定。既に設定済みなら何もしない。"""
    # 再入防止
    if os.environ.get(_BOOTSTRAP_FLAG) == "1":
        return
    os.environ[_BOOTSTRAP_FLAG] = "1"

    # 既に GOOGLE_APPLICATION_CREDENTIALS があれば尊重（ローカルのファイル指定等）
    gac = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if gac:
        return

    content, _source = _load_from_env()
    if not content:
        # 何も無ければ、OSや他の仕組みで設定されている想定
        return

    target = _pick_target_path()
    path = _write_json_file(content, target)
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = path


# 互換API（以前の bootstrap() 呼び出しに対応）
def bootstrap() -> None:
    ensure_adc()
