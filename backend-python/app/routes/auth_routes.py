from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request

from app.auth import create_token, get_current_user, hash_password, verify_password
from app.db import get_db

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _create_auth_response(user: dict) -> dict:
    token = create_token(str(user["_id"]))
    return {
        "token": token,
        "user": {
            "id": str(user["_id"]),
            "fullName": user.get("fullName", ""),
            "email": user.get("email", ""),
        },
    }


@router.post("/signup")
async def signup(request: Request) -> dict:
    body = await request.json()
    full_name = str(body.get("fullName", "")).strip()
    email = str(body.get("email", "")).strip().lower()
    password = str(body.get("password", ""))

    if not full_name or not email or not password:
        raise HTTPException(status_code=400, detail="Full name, email, and password are required.")

    if len(password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters long.")

    db = get_db()
    existing_user = db.users.find_one({"email": email})
    if existing_user:
        raise HTTPException(status_code=409, detail="An account with this email already exists.")

    now = datetime.now(timezone.utc)
    user_doc = {
        "fullName": full_name,
        "email": email,
        "passwordHash": hash_password(password),
        "createdAt": now,
        "updatedAt": now,
    }
    result = db.users.insert_one(user_doc)
    user_doc["_id"] = result.inserted_id

    return _create_auth_response(user_doc)


@router.post("/login")
async def login(request: Request) -> dict:
    body = await request.json()
    email = str(body.get("email", "")).strip().lower()
    password = str(body.get("password", ""))

    if not email or not password:
        raise HTTPException(status_code=400, detail="Email and password are required.")

    db = get_db()
    user = db.users.find_one({"email": email})
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    if not verify_password(password, user.get("passwordHash", "")):
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    return _create_auth_response(user)


@router.get("/me")
def get_me(current_user: dict = Depends(get_current_user)) -> dict:
    return {"user": current_user}
