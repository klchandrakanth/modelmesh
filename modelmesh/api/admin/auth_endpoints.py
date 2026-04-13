"""POST /admin/auth/login  and  POST /admin/auth/change-password"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from passlib.context import CryptContext
from pydantic import BaseModel

from modelmesh.api.admin.auth import create_token, require_jwt_any
from modelmesh.db.connection import get_db

router = APIRouter(prefix="/admin/auth", tags=["auth"])
_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
# Pre-computed dummy hash for constant-time verification when user not found
# Prevents timing attacks that could reveal valid usernames
_DUMMY_HASH: str = _pwd.hash("dummy-this-never-matches")


class LoginRequest(BaseModel):
    username: str
    password: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


@router.post("/login")
async def login(body: LoginRequest, db=Depends(get_db)):
    row = await db.fetchrow(
        "SELECT username, password_hash, must_change_pw FROM users WHERE username = $1",
        body.username,
    )
    # Use constant-time comparison even on missing user to prevent timing attacks
    stored_hash = row["password_hash"] if row else _DUMMY_HASH
    valid = _pwd.verify(body.password, stored_hash)
    if not row or not valid:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_token(row["username"], row["must_change_pw"])
    return {"access_token": token, "must_change_pw": row["must_change_pw"]}


@router.post("/change-password")
async def change_password(
    body: ChangePasswordRequest,
    payload: dict = Depends(require_jwt_any),
    db=Depends(get_db),
):
    username = payload["sub"]
    row = await db.fetchrow(
        "SELECT password_hash FROM users WHERE username = $1", username
    )
    if not row or not _pwd.verify(body.current_password, row["password_hash"]):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    new_hash = _pwd.hash(body.new_password)
    await db.execute(
        "UPDATE users SET password_hash = $1, must_change_pw = FALSE WHERE username = $2",
        new_hash,
        username,
    )
    return {"access_token": create_token(username, False)}
