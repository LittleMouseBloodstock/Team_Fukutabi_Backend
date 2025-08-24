# app/services/security.py
from fastapi import Depends
from typing import Optional

class CurrentUser:
    def __init__(self, user_id: int):
        self.id = user_id

# 本来はJWT検証など。暫定で常に user_id=1 を返す。
async def get_current_user() -> CurrentUser:
    return CurrentUser(user_id=1)


