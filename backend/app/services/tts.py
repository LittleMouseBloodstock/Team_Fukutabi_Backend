from dotenv import load_dotenv
load_dotenv()

import os
import uuid
import pathlib
import re
from typing import Tuple

from anyio import to_thread  # ← 追加（非同期で同期APIを呼ぶ）
from google.cloud import texttospeech  # ← 追加

# GOOGLE_APPLICATION_CREDENTIALS を環境変数に設定（パス補正付き）
cred_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

# 🔽 ここを追加！
print("★ cred_path (raw) >>", cred_path)

if cred_path and not os.path.isabs(cred_path):
    cred_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", cred_path))

# 🔽 絶対パスに変換後の確認も追加！
print("★ cred_path (absolute) >>", cred_path)
print("★ os.path.exists(cred_path) >>", os.path.exists(cred_path))

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = cred_path

def clean_guide_text_for_tts(text: str) -> str:
    """
    TTS用にガイドテキストを整形する（改行/句読点/見出し/座標除去など）
    """
    text = re.sub(r'^#+\s*', '', text, flags=re.MULTILINE)  # 見出し削除
    text = re.sub(r'。', '。 ', text)  # 句点後にスペース
    text = re.sub(r'、', '、 ', text)
    text = re.sub(r'\n+', '\n', text)  # 連続改行の整理
    text = re.sub(r'[0-9０-９]{3}-[0-9０-９]{4}', '郵便番号', text)  # 郵便番号除去

    # 座標の潰し方は小数全潰しだと副作用が出るので、行ベースで緯度/経度を潰す例
    text = re.sub(r'(?im)^.*(緯度|経度|座標).*\n?', '', text)

    text = re.sub(r'\s+', ' ', text)  # 余分なスペースを削除
    return text.strip()


MEDIA_DIR = os.getenv("MEDIA_ROOT", "./media")
GUIDE_DIR = pathlib.Path(MEDIA_DIR) / "guides"
GUIDE_DIR.mkdir(parents=True, exist_ok=True)


def _select_google_voice(voice: str | None) -> str:
    """
    簡易マッピング:
      - None / "female" → 女性声
      - "male" → 男性声
      - 具体ID（例: "ja-JP-Neural2-C"）が来たらそれを尊重
    ※ 利用可能な音色はGCPプロジェクト/地域で異なる可能性があります
    """
    if voice is None:
        return "ja-JP-Neural2-C"  # 女性寄り
    v = (voice or "").lower()
    if v in {"female", "woman", "f"}:
        return "ja-JP-Neural2-C"
    if v in {"male", "man", "m"}:
        return "ja-JP-Neural2-D"
    # 具体指定をそのまま使用（例: "ja-JP-Wavenet-C", "ja-JP-Neural2-B" など）
    return voice


def _build_ssml_from_text(text: str) -> str:
    """
    必要に応じてSSML化（間や速さ調整など）。
    読み誤りがある固有名詞は将来的に <sub alias="はかた">博多</sub> のように置換可能。
    """
    safe = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    ssml = f"""<speak>
  <prosody rate="medium" pitch="+0st">
    {safe}
  </prosody>
</speak>"""
    return ssml


async def synthesize_to_mp3(text: str, voice: str | None = None) -> Tuple[str, str]:
    """
    テキストをMP3に変換して保存（Google Cloud Text-to-Speech版）。
    戻り値: (local_file_path, public_url)
    - 失敗時は .txt を保存して必ずURLを返す（既存互換）
    """
    filename = f"{uuid.uuid4()}.mp3"
    out_path = GUIDE_DIR / filename
    url = f"/media/guides/{filename}"

    cleaned_text = clean_guide_text_for_tts(text)

    def _call_gcp_tts():
        client = texttospeech.TextToSpeechClient()

        # SSMLで渡す（自然さ向上・調整しやすい）
        input_ = texttospeech.SynthesisInput(ssml=_build_ssml_from_text(cleaned_text))

        # 音色選択
        voice_name = _select_google_voice(voice)
        voice_params = texttospeech.VoiceSelectionParams(
            language_code="ja-JP",
            name=voice_name,  # 例: "ja-JP-Neural2-C"
        )

        # MP3で出力
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3,
            speaking_rate=1.0,     # 0.25〜4.0
            pitch=0.0,             # -20.0〜20.0 semitones
            volume_gain_db=0.0,    # -96.0〜16.0 dB
        )

        response = client.synthesize_speech(
            input=input_,
            voice=voice_params,
            audio_config=audio_config,
        )
        return response.audio_content

    try:
        audio_content = await to_thread.run_sync(_call_gcp_tts)
        with open(out_path, "wb") as f:
            f.write(audio_content)
        return str(out_path), url

    except Exception as e:
        # フォールバック：txt保存（既存挙動と同じ）
        print("TTS ERROR (GCP):", repr(e))
        fallback = f"{uuid.uuid4()}.txt"
        out_txt = GUIDE_DIR / fallback
        url_txt = f"/media/guides/{fallback}"
        try:
            out_txt.write_text(text, encoding="utf-8")
        except Exception:
            pass
        return str(out_txt), url_txt
