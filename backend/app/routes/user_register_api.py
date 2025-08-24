from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from app.db.database import get_db
from app.db import models
from app.schemas.user_register import UserCreate

router = APIRouter()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

@router.post("/register")
def register_user(user: UserCreate, db: Session = Depends(get_db)):
    # すでにメールアドレスが存在するかチェック
    db_user = db.query(models.User).filter(models.User.email == user.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="このメールアドレスはすでに登録されています")

    # パスワードをハッシュ化して保存
    hashed_pw = pwd_context.hash(user.password)
    new_user = models.User(
        email=user.email,
        hashed_password=hashed_pw,
        name=user.name,
        gender=user.gender,
        age_group=user.age_group,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return {"message": "登録が完了しました", "user_id": new_user.id}
