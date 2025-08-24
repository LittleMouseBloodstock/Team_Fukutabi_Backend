# app/config.py
from pydantic import BaseSettings, Field
from typing import Optional
import json

class Settings(BaseSettings):
    # Google / GCP
    gcp_sa_key_json: str = Field(default="", env="GCP_SA_KEY_JSON")
    google_maps_api_key: str = Field(default="", env="GOOGLE_MAPS_API_KEY")
    google_places_language: str = Field(default="ja", env="GOOGLE_PLACES_LANGUAGE")
    google_places_region: str = Field(default="jp", env="GOOGLE_PLACES_REGION")
    use_google_places: bool = Field(default=True, env="USE_GOOGLE_PLACES")

    # Gemini
    gemini_api_key: str = Field(default="", env="GEMINI_API_KEY")
    gemini_model: str = Field(default="gemini-1.5-pro", env="GEMINI_MODEL")

    # DBなど他があれば適宜
    ssl_ca_path: Optional[str] = Field(default=None, env="SSL_CA_PATH")

    class Config:
        case_sensitive = False

    def gcp_sa_info(self) -> dict:
        if not self.gcp_sa_key_json:
            raise RuntimeError("GCP_SA_KEY_JSON が未設定です")
        info = json.loads(self.gcp_sa_key_json)
        if "private_key" in info and "\\n" in info["private_key"]:
            info["private_key"] = info["private_key"].replace("\\n", "\n")
        return info

settings = Settings()
