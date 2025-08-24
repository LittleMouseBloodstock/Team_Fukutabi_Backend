# app/services/google_adc_bootstrap.py
"""
環境変数に格納したサービスアカウントJSONを、起動時に"鍵ファイル"として書き出し、
GOOGLE_APPLICATION_CREDENTIALS にそのパスを設定するブートストラップ。

これにより、既存コード（ファイルパス前提のADC）がそのまま動作する。
- 参照する環境変数の優先順:
    1) GCP_SA_JSON_B64  : Base64エンコード済みのJSON本文
    2) GCP_SA_JSON      : プレーンなJSON本文
    3) 何も無ければ何もしない（既に GOOGLE_APPLICATION_CREDENTIALS が設定されている想定）

書き出し先は、書き込み可能な順に試行:
    - /home/site/wwwroot/secrets/gcp-sa.json   (App Service Linuxで一般的)
    - OSの一時ディレクトリ
"""

import os
import base64
import json
import tempfile

BOOTSTRAP_FLAG = "_GCP_ADC_BOOTSTRAPPED"

def _ensure_dir(p: str) -> None:
    d = os.path.dirname(p)
    if not os.path.exists(d):
        os.makedirs(d, exist_ok=True)

def _writable(path: str) -> bool:
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
    if _writable(candidate1):
        return candidate1
    # だめなら一時フォルダ
    tmp = os.path.join(tempfile.gettempdir(), "gcp-sa.json")
    _ensure_dir(tmp)
    return tmp

def _load_json_from_env() -> str | None:
    b64 = os.environ.get("GCP_SA_JSON_B64") or os.environ.get("GOOGLE_APPLICATION_CREDENTIALS_JSON_B64")
    raw = os.environ.get("GCP_SA_JSON") or os.environ.get("GOOGLE_APPLICATION_CREDENTIALS_JSON")
    if b64:
        try:
            return base64.b64decode(b64).decode("utf-8")
        except Exception:
            # フォールバックでそのまま返す（誤ってプレーンを入れた場合でも動かす）
            return b64
    if raw:
        return raw
    return None

def _write_json_file(content: str, path: str) -> str:
    with open(path, "w", encoding="utf-8") as f:
        # JSONの妥当性チェックついでに整形してから書く
        obj = json.loads(content)
        json.dump(obj, f, ensure_ascii=False)
        f.write("\n")
    # パーミッション（可能なら）を絞る
    try:
        os.chmod(path, 0o600)
    except Exception:
        pass
    return path

def bootstrap() -> None:
    # 多重実行防止
    if os.environ.get(BOOTSTRAP_FLAG) == "1":
        return
    os.environ[BOOTSTRAP_FLAG] = "1"

    # 既にファイルパスが設定されているなら何もしない
    if os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
        return

    content = _load_json_from_env()
    if not content:
        # 何もなければ黙って終了（ローカル等で従来のファイル方式を使っている想定）
        return

    target = _pick_target_path()
    path = _write_json_file(content, target)
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = path

# 即時実行（インポートした瞬間に有効化）
bootstrap()
