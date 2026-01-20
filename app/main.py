from fastapi import FastAPI
from fastapi.responses import RedirectResponse
import secrets
from datetime import datetime

from app.twitch_auth import (
    get_login_url,
    exchange_code_for_token,
    get_user_info
)

from app.database import users_collection
from app.models import twitch_user_schema

app = FastAPI()

STATE_CACHE = set()


@app.get("/")
def root():
    return {"status": "Twitch OAuth running"}


@app.get("/auth/twitch/login")
def twitch_login():
    state = secrets.token_urlsafe(16)
    STATE_CACHE.add(state)

    return RedirectResponse(get_login_url(state))


@app.get("/auth/twitch/callback")
def twitch_callback(code: str, state: str):

    if state not in STATE_CACHE:
        return {"error": "Invalid OAuth state"}

    STATE_CACHE.remove(state)

    token = exchange_code_for_token(code)
    user = get_user_info(token["access_token"])

    users_collection.update_one(
        {"twitch_user_id": user["id"]},
        {
            "$set": {
                **twitch_user_schema(user, token),
                "updated_at": datetime.utcnow()
            }
        },
        upsert=True
    )

    return {
        "message": "Login successful",
        "twitch_user_id": user["id"],
        "login": user["login"]
    }