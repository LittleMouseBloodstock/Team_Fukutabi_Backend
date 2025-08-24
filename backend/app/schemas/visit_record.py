from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Union
from datetime import datetime

class VisitCreate(BaseModel):
    # id(int) でも place_id(str) でも受ける
    destinationId: Union[int, str]
    # DB側がintでもstrでも来ても受けられるようUnionにしておく
    userId: Optional[Union[int, str]] = None

class VisitRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    # ← ここを str に
    id: str
    # ← UUID文字列なので str に
    destinationId: str = Field(alias="destination_id")
    # ← ユーザーIDの型が未定なら Union に
    userId: Optional[Union[int, str]] = Field(default=None, alias="user_id")
    createdAt: datetime = Field(alias="created_at")
