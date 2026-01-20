from datetime import datetime, timedelta
from twitch_auth import refresh_access_token
from database import users_collection


def token_expired(user: dict) -> bool:
    expires_at = user["updated_at"] + timedelta(
        seconds=user["expires_in"]
    )
    return datetime.utcnow() > expires_at - timedelta(minutes=5)


def get_valid_access_token(user: dict) -> str:
    if token_expired(user):
        new_tokens = refresh_access_token(user["refresh_token"])

        users_collection.update_one(
            {"_id": user["_id"]},
            {"$set": {
                "access_token": new_tokens["access_token"],
                "refresh_token": new_tokens["refresh_token"],
                "expires_in": new_tokens["expires_in"],
                "updated_at": datetime.utcnow()
            }}
        )

        return new_tokens["access_token"]

    return user["access_token"]