from datetime import datetime

def twitch_user_schema(user, token):
    return {
        "twitch_user_id": user["id"],
        "login": user["login"],
        "display_name": user["display_name"],
        "email": user.get("email"),

        "access_token": token["access_token"],
        "refresh_token": token["refresh_token"],
        "scope": token.get("scope", []),
        "expires_in": token["expires_in"],

        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }