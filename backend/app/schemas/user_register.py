from typing import Literal
from pydantic import BaseModel, EmailStr

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    name: str
    gender: Literal["男性", "女性", "その他"]  # ← これも日本語化してOKです
    age_group: Literal["10代", "20代", "30代", "40代", "50代以上"]
