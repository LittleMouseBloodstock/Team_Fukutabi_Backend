# app/services/gpt.py
import os
from typing import Optional, Dict, Any
from openai import OpenAI
from anyio import to_thread  # 同期APIを非ブロッキングで呼ぶため

# ---- 設定 ----
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY が設定されていません。.env を確認してください。")

MODEL_TEXT = os.getenv("OPENAI_TEXT_MODEL", "gpt-4o-mini")  # 必要なら .env で上書き可

client = OpenAI(api_key=OPENAI_API_KEY)

def _compose_prompt(
    name: str,
    address: str,
    lat: float | None,
    lng: float | None,
    style: str = "friendly",
    user: Optional[Dict[str, Any]] = None,
) -> str:
    tone = {
        "friendly": "親しみやすく、やさしい日本語で",
        "energetic": "元気でワクワクする語り口で",
        "calm": "落ち着いた語り口で",
    }.get(style, "親しみやすく、やさしい日本語で")

    audience = ""
    if user:
        age_group = user.get("age_group")
        gender = user.get("gender")
        audience = f"\n- 想定読者: 年齢={age_group}, 性別={gender}"

    return (
        "あなたは観光ガイドです。"
        f"{tone}、耳で聞いてわかりやすい400〜600字のナレーション原稿を作成してください。\n"
        "構成は【概要→見どころ→歴史や豆知識→楽しみ方→注意点】の順に、一続きの話し言葉で書いてください。\n"
        "※ 郵便番号・電話番号・座標など、読み上げに不要な数値情報は含めないでください。\n"
        f"- 場所名: {name}\n"
        f"- 参考情報（出力には含めない）: 住所={address}, 座標=({lat}, {lng})\n"
        f"{audience}"
)

# ---- visits.py から await で呼ばれるエントリ ----
async def generate_guide_text(
    name: str,
    address: str,
    lat: float | None,
    lng: float | None,
    style: str = "friendly",
    user: Optional[dict] = None,
) -> str:
    prompt = _compose_prompt(name=name, address=address, lat=lat, lng=lng, style=style, user=user)

    # デバッグ: 実際のプロンプトが使われているかを確認（必要なら削除OK）
    print("GPT: generate_guide_text CALLED")
    print("GPT PROMPT >>", prompt[:300].replace("\n", " "))

    def _call_openai():
        return client.chat.completions.create(
            model=MODEL_TEXT,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "あなたは旅先を案内する熟練の観光ガイドです。以下を厳守："
                        "1) 300〜400字のスピーチ台本。"
                        "2) 構成は【概要 → 見どころ → 歴史や豆知識 → 楽しみ方 → 注意点】の順で、一続きのナレーションにしてください（見出しは書かない）。"
                        "3) 作り話や推測の断定は禁止。事実ベースで固有名詞と数字を具体的に。"
                        "4) 書き言葉ではなく、話し言葉で自然に。"
                        "5) 誇張やフィクションは禁止。事実ベースで、具体的な地名・年号・施設名などを正確に伝えてください。"
                        "6) 郵便番号・電話番号・座標・緯度経度など、聞いて意味のない数値情報は含めないでください。"
                        "7) 難読地名や人名にはふりがなをつけてください。"
                        "8) 事実に基づき、読者が興味を持つような内容にする。"
                        ""
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.6,
        )

    # 同期APIをスレッドで実行してイベントループを塞がない
    resp = await to_thread.run_sync(_call_openai)

    text = (resp.choices[0].message.content or "").strip()
    print("GPT OK len=", len(text))
    return text