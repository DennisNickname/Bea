from __future__ import annotations

import json
import os
import time
import urllib.parse
import urllib.request

STRAVA_AUTHORIZE_URL = "https://www.strava.com/oauth/authorize"
STRAVA_TOKEN_URL = "https://www.strava.com/oauth/token"
STRAVA_ACTIVITIES_URL = "https://www.strava.com/api/v3/athlete/activities"

ENDURANCE_TYPES = {
    "AlpineSki",
    "Canoeing",
    "Crossfit",
    "EBikeRide",
    "Elliptical",
    "GravelRide",
    "Hike",
    "IceSkate",
    "InlineSkate",
    "Kayaking",
    "Kitesurf",
    "MountainBikeRide",
    "NordicSki",
    "Ride",
    "RockClimbing",
    "RollerSki",
    "Rowing",
    "Run",
    "Sail",
    "Skateboard",
    "Snowboard",
    "Snowshoe",
    "Soccer",
    "StairStepper",
    "StandUpPaddling",
    "Surfing",
    "Swim",
    "TrailRun",
    "Velomobile",
    "VirtualRide",
    "VirtualRun",
    "Walk",
    "Windsurf",
}

STRENGTH_TYPES = {"WeightTraining", "Workout", "Yoga"}


def strava_client_id() -> str:
    return os.getenv("STRAVA_CLIENT_ID", "").strip()


def strava_client_secret() -> str:
    return os.getenv("STRAVA_CLIENT_SECRET", "").strip()


def strava_is_configured() -> bool:
    return bool(strava_client_id() and strava_client_secret())


def strava_authorization_url(redirect_uri: str, oauth_state: str) -> str:
    params = {
        "client_id": strava_client_id(),
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "approval_prompt": "auto",
        "scope": "read,activity:read_all",
        "state": oauth_state,
    }
    return f"{STRAVA_AUTHORIZE_URL}?{urllib.parse.urlencode(params)}"


def post_form(url: str, payload: dict) -> dict:
    data = urllib.parse.urlencode(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=12) as response:
        return json.loads(response.read().decode("utf-8"))


def exchange_strava_code(code: str) -> dict:
    return post_form(
        STRAVA_TOKEN_URL,
        {
            "client_id": strava_client_id(),
            "client_secret": strava_client_secret(),
            "code": code,
            "grant_type": "authorization_code",
        },
    )


def refresh_strava_token(refresh_token: str) -> dict:
    return post_form(
        STRAVA_TOKEN_URL,
        {
            "client_id": strava_client_id(),
            "client_secret": strava_client_secret(),
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        },
    )


def strava_access_token(connection: dict) -> tuple[str, dict | None]:
    expires_at = int(connection.get("expires_at") or 0)
    if expires_at > int(time.time()) + 90:
        return str(connection["access_token"]), None

    refreshed = refresh_strava_token(str(connection["refresh_token"]))
    return str(refreshed["access_token"]), refreshed


def fetch_strava_activities(access_token: str, per_page: int = 20) -> list[dict]:
    params = urllib.parse.urlencode({"per_page": per_page, "page": 1})
    request = urllib.request.Request(
        f"{STRAVA_ACTIVITIES_URL}?{params}",
        headers={"Authorization": f"Bearer {access_token}"},
        method="GET",
    )
    with urllib.request.urlopen(request, timeout=12) as response:
        return json.loads(response.read().decode("utf-8"))


def strava_activity_payload(activity: dict, member_id: str) -> dict:
    activity_type = activity.get("type") or activity.get("sport_type") or "Run"
    sport_type = "strength" if activity_type in STRENGTH_TYPES else "endurance"
    if activity_type not in ENDURANCE_TYPES and activity_type not in STRENGTH_TYPES:
        sport_type = "endurance"

    moving_time = max(60, int(activity.get("moving_time") or activity.get("elapsed_time") or 60))
    duration = max(1, round(moving_time / 60))
    distance = float(activity.get("distance") or 0)
    kilometers = round(distance / 1000, 2)
    amount = f"{kilometers} km" if kilometers else activity_type

    return {
        "member_id": member_id,
        "sport_type": sport_type,
        "title": activity.get("name") or activity_type,
        "amount": amount,
        "duration": duration,
        "effort": 3,
        "external_source": "strava",
        "external_id": str(activity.get("id")),
        "external_url": f"https://www.strava.com/activities/{activity.get('id')}",
    }
