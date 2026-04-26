from __future__ import annotations

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from bson import ObjectId
from fastapi import Header, HTTPException

from app.config import settings
from app.db import get_db
from app.serializers import serialize_document


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed_password.encode("utf-8"))


def create_token(user_id: str) -> str:
    payload = {
        "userId": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(days=7),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def parse_bearer_token(authorization: str | None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication token is required.")

    token = authorization[7:].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Authentication token is required.")
    return token


def get_current_user(authorization: str | None = Header(default=None)) -> dict:
    token = parse_bearer_token(authorization)

    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
        user_id = payload.get("userId", "")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid authentication token.")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired authentication token.") from None

    db = get_db()
    try:
        user = db.users.find_one({"_id": ObjectId(user_id)})
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid authentication token.") from None

    if not user:
        raise HTTPException(status_code=401, detail="Invalid authentication token.")

    user.pop("passwordHash", None)
    return serialize_document(user)
