from __future__ import annotations

import copy
import json
import os
from datetime import date
from pathlib import Path
from uuid import uuid4

PROJECT_ROOT = Path(__file__).resolve().parent.parent
STATE_PATH = Path(os.getenv("BEA_STATE_PATH", PROJECT_ROOT / "data" / "bea_state.json"))

AREAS = ("endurance", "strength", "nutrition", "team")

AREA_LABELS = {
    "endurance": "Ausdauer",
    "strength": "Kraft",
    "nutrition": "Nahrung",
    "team": "Teamgeist",
}

DEFAULT_STATE = {
    "members": [
        {
            "id": "bea",
            "name": "Bea",
            "focus": "Kraft & Routine",
            "xp": {"endurance": 360, "strength": 520, "nutrition": 310, "team": 260},
            "streak": 6,
        },
        {
            "id": "mara",
            "name": "Mara",
            "focus": "Laufen",
            "xp": {"endurance": 610, "strength": 240, "nutrition": 220, "team": 330},
            "streak": 4,
        },
        {
            "id": "jonas",
            "name": "Jonas",
            "focus": "Ganzkoerper",
            "xp": {"endurance": 280, "strength": 470, "nutrition": 180, "team": 210},
            "streak": 3,
        },
        {
            "id": "nina",
            "name": "Nina",
            "focus": "Ernaehrung",
            "xp": {"endurance": 190, "strength": 210, "nutrition": 540, "team": 390},
            "streak": 8,
        },
    ],
    "sport_entries": [
        {
            "id": "sport-1",
            "member_id": "bea",
            "sport_type": "strength",
            "title": "Beintraining",
            "amount": "4 Saetze",
            "duration": 45,
            "effort": 4,
            "xp": 82,
            "created_at": "2026-06-04",
        },
        {
            "id": "sport-2",
            "member_id": "mara",
            "sport_type": "endurance",
            "title": "Lockerer Lauf",
            "amount": "6 km",
            "duration": 38,
            "effort": 3,
            "xp": 68,
            "created_at": "2026-06-04",
        },
    ],
    "nutrition_entries": [
        {
            "id": "meal-1",
            "member_id": "nina",
            "meal": "Protein Bowl",
            "protein": 34,
            "calories": 620,
            "water": 0.7,
            "xp": 47,
            "created_at": "2026-06-04",
        }
    ],
    "assignments": [
        {
            "id": "assign-1",
            "from_member": "bea",
            "to_member": "jonas",
            "category": "strength",
            "title": "3x12 Kniebeugen",
            "details": "Saubere Tiefe, ruhiges Tempo.",
            "due": "Freitag",
            "xp": 55,
            "status": "open",
            "created_at": "2026-06-04",
        }
    ],
    "motivations": [
        {
            "id": "motivation-1",
            "from_member": "mara",
            "to_member": "bea",
            "message": "Stark drangeblieben, heute zaehlt die Routine.",
            "created_at": "2026-06-04",
        }
    ],
    "challenges": [
        {
            "id": "team-100",
            "title": "Team 100 Minuten Ausdauer",
            "category": "endurance",
            "goal": 100,
            "unit": "Minuten",
            "xp": 120,
            "participants": {"bea": 30, "mara": 38, "jonas": 15, "nina": 12},
            "completed": [],
        },
        {
            "id": "protein-week",
            "title": "Protein Woche",
            "category": "nutrition",
            "goal": 7,
            "unit": "Tage",
            "xp": 90,
            "participants": {"bea": 3, "mara": 2, "jonas": 1, "nina": 5},
            "completed": [],
        },
        {
            "id": "push-pull",
            "title": "Kraftzirkel",
            "category": "strength",
            "goal": 5,
            "unit": "Einheiten",
            "xp": 110,
            "participants": {"bea": 2, "mara": 1, "jonas": 3, "nina": 1},
            "completed": [],
        },
    ],
    "settings": {
        "location_label": "Berlin",
        "latitude": 52.52,
        "longitude": 13.405,
    },
    "integrations": {
        "strava": {
            "connections": {},
            "pending": {},
            "last_sync": {},
        }
    },
    "photo_access": {},
    "photos": [],
}


def load_state() -> dict:
    if not STATE_PATH.exists():
        return copy.deepcopy(DEFAULT_STATE)

    with STATE_PATH.open("r", encoding="utf-8") as handle:
        loaded = json.load(handle)

    state = copy.deepcopy(DEFAULT_STATE)
    state.update(loaded)
    return state


def save_state(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with STATE_PATH.open("w", encoding="utf-8") as handle:
        json.dump(state, handle, ensure_ascii=False, indent=2)


def update_settings(state: dict, payload: dict) -> dict:
    label = str(payload.get("location_label") or "Berlin").strip()
    try:
        latitude = float(payload.get("latitude"))
        longitude = float(payload.get("longitude"))
    except (TypeError, ValueError) as exc:
        raise ValueError("Bitte gueltige Koordinaten eintragen.") from exc

    if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
        raise ValueError("Koordinaten liegen ausserhalb des gueltigen Bereichs.")

    settings = state.setdefault("settings", {})
    settings["location_label"] = label
    settings["latitude"] = round(latitude, 6)
    settings["longitude"] = round(longitude, 6)
    return settings


def today() -> str:
    return date.today().isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:10]}"


def members_by_id(state: dict) -> dict[str, dict]:
    return {member["id"]: member for member in state["members"]}


def member_name(state: dict, member_id: str) -> str:
    return members_by_id(state).get(member_id, {}).get("name", "Unbekannt")


def total_xp(member: dict) -> int:
    return sum(int(member.get("xp", {}).get(area, 0)) for area in AREAS)


def level_for_xp(xp: int) -> dict[str, int]:
    level = max(1, xp // 250 + 1)
    current_floor = (level - 1) * 250
    progress = min(100, int(((xp - current_floor) / 250) * 100))
    return {"level": level, "progress": progress, "next_xp": level * 250}


def leaderboard(state: dict) -> list[dict]:
    return sorted(state["members"], key=total_xp, reverse=True)


def team_totals(state: dict) -> dict[str, int]:
    totals = {area: 0 for area in AREAS}
    for member in state["members"]:
        for area in AREAS:
            totals[area] += int(member.get("xp", {}).get(area, 0))
    return totals


def award_xp(state: dict, member_id: str, area: str, xp: int) -> None:
    if area not in AREAS:
        return

    member = members_by_id(state).get(member_id)
    if not member:
        return

    member.setdefault("xp", {})
    member["xp"][area] = int(member["xp"].get(area, 0)) + max(0, int(xp))


def add_sport_entry(state: dict, payload: dict) -> dict:
    sport_type = payload.get("sport_type")
    if sport_type not in ("endurance", "strength"):
        raise ValueError("Sportart muss Ausdauer oder Kraft sein.")

    member_id = str(payload.get("member_id", ""))
    if member_id not in members_by_id(state):
        raise ValueError("Mitglied wurde nicht gefunden.")

    duration = max(1, int(payload.get("duration") or 1))
    effort = min(5, max(1, int(payload.get("effort") or 3)))
    title = str(payload.get("title") or "").strip()
    if not title:
        raise ValueError("Bitte eine Uebung eintragen.")

    xp = duration + effort * 12
    entry = {
        "id": new_id("sport"),
        "member_id": member_id,
        "sport_type": sport_type,
        "title": title,
        "amount": str(payload.get("amount") or "").strip(),
        "duration": duration,
        "effort": effort,
        "xp": xp,
        "created_at": today(),
    }
    state["sport_entries"].insert(0, entry)
    award_xp(state, member_id, sport_type, xp)
    return entry


def add_external_sport_entry(state: dict, payload: dict) -> dict | None:
    source = str(payload.get("external_source") or "").strip()
    external_id = str(payload.get("external_id") or "").strip()
    if not source or not external_id:
        raise ValueError("Externe Aktivitaet ist unvollstaendig.")

    for entry in state["sport_entries"]:
        if entry.get("external_source") == source and entry.get("external_id") == external_id:
            return None

    entry = add_sport_entry(state, payload)
    entry["external_source"] = source
    entry["external_id"] = external_id
    entry["external_url"] = str(payload.get("external_url") or "").strip()
    return entry


def add_nutrition_entry(state: dict, payload: dict) -> dict:
    member_id = str(payload.get("member_id", ""))
    if member_id not in members_by_id(state):
        raise ValueError("Mitglied wurde nicht gefunden.")

    meal = str(payload.get("meal") or "").strip()
    if not meal:
        raise ValueError("Bitte eine Mahlzeit eintragen.")

    protein = max(0, int(payload.get("protein") or 0))
    calories = max(0, int(payload.get("calories") or 0))
    water = max(0.0, float(payload.get("water") or 0))
    xp = min(90, 15 + protein + int(water * 10))
    entry = {
        "id": new_id("meal"),
        "member_id": member_id,
        "meal": meal,
        "protein": protein,
        "calories": calories,
        "water": water,
        "xp": xp,
        "created_at": today(),
    }
    state["nutrition_entries"].insert(0, entry)
    award_xp(state, member_id, "nutrition", xp)
    return entry


def add_assignment(state: dict, payload: dict) -> dict:
    category = str(payload.get("category") or "")
    if category not in ("endurance", "strength", "nutrition"):
        raise ValueError("Kategorie wurde nicht gefunden.")

    members = members_by_id(state)
    from_member = str(payload.get("from_member") or "")
    to_member = str(payload.get("to_member") or "")
    if from_member not in members or to_member not in members:
        raise ValueError("Mitglied wurde nicht gefunden.")

    title = str(payload.get("title") or "").strip()
    if not title:
        raise ValueError("Bitte eine Aufgabe eintragen.")

    assignment = {
        "id": new_id("assign"),
        "from_member": from_member,
        "to_member": to_member,
        "category": category,
        "title": title,
        "details": str(payload.get("details") or "").strip(),
        "due": str(payload.get("due") or "Diese Woche").strip(),
        "xp": max(20, int(payload.get("xp") or 50)),
        "status": "open",
        "created_at": today(),
    }
    state["assignments"].insert(0, assignment)
    award_xp(state, from_member, "team", 12)
    return assignment


def complete_assignment(state: dict, assignment_id: str) -> dict:
    for assignment in state["assignments"]:
        if assignment["id"] == assignment_id:
            assignment["status"] = "done"
            assignment["done_at"] = today()
            award_xp(state, assignment["to_member"], assignment["category"], assignment["xp"])
            award_xp(state, assignment["from_member"], "team", 8)
            return assignment
    raise ValueError("Aufgabe wurde nicht gefunden.")


def add_motivation(state: dict, payload: dict) -> dict:
    members = members_by_id(state)
    from_member = str(payload.get("from_member") or "")
    to_member = str(payload.get("to_member") or "")
    if from_member not in members or to_member not in members:
        raise ValueError("Mitglied wurde nicht gefunden.")

    message = str(payload.get("message") or "").strip()
    if not message:
        raise ValueError("Bitte eine Nachricht eintragen.")

    motivation = {
        "id": new_id("motivation"),
        "from_member": from_member,
        "to_member": to_member,
        "message": message,
        "created_at": today(),
    }
    state["motivations"].insert(0, motivation)
    award_xp(state, from_member, "team", 10)
    award_xp(state, to_member, "team", 5)
    return motivation


def add_challenge_progress(state: dict, payload: dict) -> dict:
    challenge_id = str(payload.get("challenge_id") or "")
    member_id = str(payload.get("member_id") or "")
    amount = max(1, int(payload.get("amount") or 1))

    if member_id not in members_by_id(state):
        raise ValueError("Mitglied wurde nicht gefunden.")

    for challenge in state["challenges"]:
        if challenge["id"] != challenge_id:
            continue

        participants = challenge.setdefault("participants", {})
        old_progress = int(participants.get(member_id, 0))
        new_progress = min(int(challenge["goal"]), old_progress + amount)
        participants[member_id] = new_progress

        category = challenge["category"]
        award_xp(state, member_id, category, amount * 10)

        completed = challenge.setdefault("completed", [])
        if new_progress >= int(challenge["goal"]) and member_id not in completed:
            completed.append(member_id)
            award_xp(state, member_id, category, int(challenge["xp"]))
            award_xp(state, member_id, "team", 20)

        return challenge

    raise ValueError("Challenge wurde nicht gefunden.")


def strava_store_pending(state: dict, oauth_state: str, member_id: str) -> None:
    if member_id not in members_by_id(state):
        raise ValueError("Mitglied wurde nicht gefunden.")

    strava = state.setdefault("integrations", {}).setdefault("strava", {})
    pending = strava.setdefault("pending", {})
    pending[oauth_state] = {"member_id": member_id, "created_at": today()}


def strava_consume_pending(state: dict, oauth_state: str) -> str:
    strava = state.setdefault("integrations", {}).setdefault("strava", {})
    pending = strava.setdefault("pending", {})
    payload = pending.pop(oauth_state, None)
    if not payload:
        raise ValueError("Strava-Verbindung konnte nicht bestaetigt werden.")
    return str(payload["member_id"])


def strava_set_connection(state: dict, member_id: str, token_payload: dict) -> None:
    if member_id not in members_by_id(state):
        raise ValueError("Mitglied wurde nicht gefunden.")

    athlete = token_payload.get("athlete") or {}
    strava = state.setdefault("integrations", {}).setdefault("strava", {})
    connections = strava.setdefault("connections", {})
    connections[member_id] = {
        "access_token": token_payload.get("access_token"),
        "refresh_token": token_payload.get("refresh_token"),
        "expires_at": token_payload.get("expires_at"),
        "athlete_id": athlete.get("id"),
        "athlete_name": " ".join(
            part for part in (athlete.get("firstname"), athlete.get("lastname")) if part
        ).strip()
        or athlete.get("username")
        or "Strava Athlete",
        "connected_at": today(),
    }


def strava_get_connection(state: dict, member_id: str) -> dict | None:
    return (
        state.get("integrations", {})
        .get("strava", {})
        .get("connections", {})
        .get(member_id)
    )


def strava_update_connection(state: dict, member_id: str, token_payload: dict) -> None:
    connection = strava_get_connection(state, member_id)
    if not connection:
        raise ValueError("Strava ist fuer dieses Mitglied nicht verbunden.")

    for key in ("access_token", "refresh_token", "expires_at"):
        if token_payload.get(key) is not None:
            connection[key] = token_payload[key]


def strava_set_last_sync(state: dict, member_id: str) -> None:
    strava = state.setdefault("integrations", {}).setdefault("strava", {})
    strava.setdefault("last_sync", {})[member_id] = today()
