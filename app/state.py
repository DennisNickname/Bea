from __future__ import annotations

import base64
import copy
import hashlib
import hmac
import json
import os
from datetime import date
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

PROJECT_ROOT = Path(__file__).resolve().parent.parent
STATE_PATH = Path(os.getenv("BEA_STATE_PATH", PROJECT_ROOT / "data" / "bea_state.json"))
CHECKIN_INTERVAL_DAYS = 90
PASSWORD_ITERATIONS = 240_000

AREAS = ("endurance", "strength", "nutrition", "team")

AREA_LABELS = {
    "endurance": "Ausdauer",
    "strength": "Kraft",
    "nutrition": "Nahrung",
    "team": "Teamgeist",
}

ACTIVITY_FACTORS = {
    "low": 1.25,
    "light": 1.4,
    "moderate": 1.6,
    "high": 1.8,
}

ACTIVITY_LABELS = {
    "low": "sitzend",
    "light": "leicht aktiv",
    "moderate": "moderat aktiv",
    "high": "sehr aktiv",
}

GOAL_ADJUSTMENTS = {
    "lose": -400,
    "maintain": 0,
    "gain": 300,
    "performance": 150,
}

GOAL_LABELS = {
    "lose": "Fett reduzieren",
    "maintain": "Gewicht halten",
    "gain": "Muskeln aufbauen",
    "performance": "Leistung steigern",
}

TRAINING_LABELS = {
    "gym": "Fitnessstudio",
    "home": "Zuhause",
    "mixed": "Gemischt",
}

ENDURANCE_LABELS = {
    "outdoor": "Draußen",
    "indoor": "Studio",
    "mixed": "Wetterabhängig",
}

DIET_LABELS = {
    "mixed": "Mischkost",
    "vegetarian": "Vegetarisch",
    "vegan": "Vegan",
    "high_protein": "Proteinbetont",
}

GOAL_METRIC_LABELS = {
    "weight": "Gewicht",
    "performance": "Leistung",
    "habit": "Gewohnheiten",
    "recomposition": "Körperform",
}

TRACKING_FREQUENCY_LABELS = {
    "daily": "täglich",
    "twice_weekly": "2x pro Woche",
    "weekly": "wöchentlich",
}

WORK_STYLE_LABELS = {
    "desk": "viel Sitzen",
    "standing": "viel Stehen",
    "physical": "körperlich aktiv",
    "shift": "Schichtarbeit",
    "mixed": "abwechslungsreich",
}

SLEEP_QUALITY_LABELS = {
    "good": "erholsam",
    "okay": "wechselhaft",
    "poor": "zu wenig erholsam",
    "irregular": "unregelmäßig",
}

STRESS_LABELS = {
    "low": "niedrig",
    "medium": "mittel",
    "high": "hoch",
    "very_high": "sehr hoch",
}

RECOVERY_LABELS = {
    "calm": "ruhig aufbauen",
    "balanced": "ausgewogen",
    "push": "fordernd mit klaren Pausen",
}

ADVENTURE_ROLE_LABELS = {
    "guardian": "Wächter",
    "scout": "Pfadfinder",
    "berserker": "Kraftheld",
    "alchemist": "Küchenalchemist",
    "bard": "Motivator",
}

MOTIVATION_STYLE_LABELS = {
    "numbers": "Zahlen und klare Fortschritte",
    "story": "Story, Quests und Abenteuer",
    "team": "Teamdruck und Ermutigung",
    "calm": "ruhige Routinen",
}

TRAINING_FOCUS_LABELS = {
    "balanced": "Ausgewogen stärker werden",
    "muscle": "Muskelaufbau",
    "strength": "Kraftwerte steigern",
    "endurance": "Ausdauer verbessern",
    "fat_loss": "Fett reduzieren",
    "posture": "Haltung & Rücken",
    "mobility": "Beweglichkeit & Kontrolle",
}

BODY_FOCUS_LABELS = {
    "full_body": "Ganzkörper",
    "legs_glutes": "Beine & Gesäß",
    "core": "Rumpf",
    "back_posture": "Rücken & Haltung",
    "upper_body": "Oberkörper",
    "shoulders_arms": "Schultern & Arme",
    "mobility": "Beweglichkeit",
    "endurance_base": "Ausdauerbasis",
}

INJURY_AREA_LABELS = {
    "none": "keine bekannten Einschränkungen",
    "shoulder": "Schulter",
    "back": "Rücken",
    "knee": "Knie",
    "hip": "Hüfte",
    "ankle": "Sprunggelenk / Fuß",
    "wrist": "Handgelenk",
    "other": "Sonstiges",
}

MEAL_LABELS = {
    "breakfast": "Frühstück",
    "lunch": "Mittagessen",
    "dinner": "Abendessen",
    "snack": "Snack",
}

FOOD_CATEGORIES = {
    "protein": "Protein",
    "carbs": "Kohlenhydrate",
    "fat": "Fette",
    "fruit": "Obst",
    "vegetable": "Gemüse",
    "dairy": "Milchprodukte",
    "drink": "Getränke",
    "other": "Sonstiges",
}

DEFAULT_FOOD_ITEMS = [
    {"id": "oats", "name": "Haferflocken", "category": "carbs", "calories": 372, "protein": 13.5, "carbs": 58.7, "fat": 7.0},
    {"id": "rice", "name": "Reis gekocht", "category": "carbs", "calories": 130, "protein": 2.7, "carbs": 28.0, "fat": 0.3},
    {"id": "potatoes", "name": "Kartoffeln", "category": "carbs", "calories": 77, "protein": 2.0, "carbs": 17.0, "fat": 0.1},
    {"id": "pasta", "name": "Vollkornnudeln gekocht", "category": "carbs", "calories": 124, "protein": 5.0, "carbs": 25.0, "fat": 0.8},
    {"id": "bread", "name": "Vollkornbrot", "category": "carbs", "calories": 214, "protein": 8.5, "carbs": 39.0, "fat": 2.0},
    {"id": "banana", "name": "Banane", "category": "fruit", "calories": 89, "protein": 1.1, "carbs": 22.8, "fat": 0.3},
    {"id": "apple", "name": "Apfel", "category": "fruit", "calories": 52, "protein": 0.3, "carbs": 14.0, "fat": 0.2},
    {"id": "berries", "name": "Beerenmix", "category": "fruit", "calories": 43, "protein": 0.8, "carbs": 7.5, "fat": 0.5},
    {"id": "broccoli", "name": "Brokkoli", "category": "vegetable", "calories": 34, "protein": 2.8, "carbs": 6.6, "fat": 0.4},
    {"id": "spinach", "name": "Spinat", "category": "vegetable", "calories": 23, "protein": 2.9, "carbs": 3.6, "fat": 0.4},
    {"id": "tomato", "name": "Tomate", "category": "vegetable", "calories": 18, "protein": 0.9, "carbs": 3.9, "fat": 0.2},
    {"id": "chicken", "name": "Hähnchenbrust", "category": "protein", "calories": 165, "protein": 31.0, "carbs": 0.0, "fat": 3.6},
    {"id": "salmon", "name": "Lachs", "category": "protein", "calories": 208, "protein": 20.0, "carbs": 0.0, "fat": 13.0},
    {"id": "tuna", "name": "Thunfisch", "category": "protein", "calories": 116, "protein": 26.0, "carbs": 0.0, "fat": 1.0},
    {"id": "egg", "name": "Ei", "category": "protein", "calories": 155, "protein": 13.0, "carbs": 1.1, "fat": 11.0},
    {"id": "tofu", "name": "Tofu", "category": "protein", "calories": 144, "protein": 15.7, "carbs": 3.9, "fat": 8.0},
    {"id": "lentils", "name": "Linsen gekocht", "category": "protein", "calories": 116, "protein": 9.0, "carbs": 20.0, "fat": 0.4},
    {"id": "kidney_beans", "name": "Kidneybohnen", "category": "protein", "calories": 127, "protein": 8.7, "carbs": 22.8, "fat": 0.5},
    {"id": "skyr", "name": "Skyr", "category": "dairy", "calories": 63, "protein": 11.0, "carbs": 4.0, "fat": 0.2},
    {"id": "quark", "name": "Magerquark", "category": "dairy", "calories": 67, "protein": 12.0, "carbs": 4.0, "fat": 0.2},
    {"id": "greek_yogurt", "name": "Griechischer Joghurt", "category": "dairy", "calories": 97, "protein": 9.0, "carbs": 3.8, "fat": 5.0},
    {"id": "milk", "name": "Milch 1,5%", "category": "dairy", "calories": 47, "protein": 3.4, "carbs": 4.9, "fat": 1.5},
    {"id": "almonds", "name": "Mandeln", "category": "fat", "calories": 579, "protein": 21.0, "carbs": 22.0, "fat": 50.0},
    {"id": "peanut_butter", "name": "Erdnussbutter", "category": "fat", "calories": 588, "protein": 25.0, "carbs": 20.0, "fat": 50.0},
    {"id": "olive_oil", "name": "Olivenöl", "category": "fat", "calories": 884, "protein": 0.0, "carbs": 0.0, "fat": 100.0},
    {"id": "avocado", "name": "Avocado", "category": "fat", "calories": 160, "protein": 2.0, "carbs": 9.0, "fat": 15.0},
    {"id": "protein_powder", "name": "Proteinpulver", "category": "protein", "calories": 390, "protein": 78.0, "carbs": 8.0, "fat": 6.0},
    {"id": "water", "name": "Wasser", "category": "drink", "calories": 0, "protein": 0.0, "carbs": 0.0, "fat": 0.0},
]

DEFAULT_MEAL_IDEAS = [
    {"id": "protein_oats", "meal_type": "breakfast", "title": "Protein Oats", "description": "Haferflocken, Skyr, Beeren und Proteinpulver.", "calories": 560, "protein": 48, "carbs": 62, "fat": 11, "youtube_url": ""},
    {"id": "quark_bowl", "meal_type": "breakfast", "title": "Quark Bowl", "description": "Magerquark mit Banane, Beeren und Mandeln.", "calories": 480, "protein": 42, "carbs": 48, "fat": 13, "youtube_url": ""},
    {"id": "egg_bread", "meal_type": "breakfast", "title": "Ei auf Vollkornbrot", "description": "Eier, Vollkornbrot, Tomate und Spinat.", "calories": 520, "protein": 30, "carbs": 45, "fat": 22, "youtube_url": ""},
    {"id": "chicken_rice", "meal_type": "lunch", "title": "Chicken Rice Bowl", "description": "Hähnchen, Reis, Brokkoli und Olivenöl.", "calories": 720, "protein": 55, "carbs": 82, "fat": 18, "youtube_url": ""},
    {"id": "lentil_pasta", "meal_type": "lunch", "title": "Linsen-Pasta", "description": "Vollkornnudeln mit Linsen, Tomaten und Spinat.", "calories": 690, "protein": 34, "carbs": 105, "fat": 12, "youtube_url": ""},
    {"id": "salmon_potatoes", "meal_type": "dinner", "title": "Lachs mit Kartoffeln", "description": "Lachs, Kartoffeln und Gemüse.", "calories": 680, "protein": 42, "carbs": 58, "fat": 28, "youtube_url": ""},
    {"id": "tofu_bowl", "meal_type": "dinner", "title": "Tofu Bowl", "description": "Tofu, Reis, Brokkoli, Avocado und Tomate.", "calories": 650, "protein": 32, "carbs": 72, "fat": 24, "youtube_url": ""},
    {"id": "skyr_snack", "meal_type": "snack", "title": "Skyr Snack", "description": "Skyr mit Beeren und etwas Erdnussbutter.", "calories": 310, "protein": 32, "carbs": 24, "fat": 10, "youtube_url": ""},
    {"id": "shake_banana", "meal_type": "snack", "title": "Proteinshake Banane", "description": "Proteinpulver, Milch und Banane.", "calories": 360, "protein": 38, "carbs": 42, "fat": 6, "youtube_url": ""},
]

RPG_DAILY_QUEST_POOL = [
    {
        "id": "move-20",
        "title": "20 Minuten Bewegung",
        "description": "Spaziergang, lockerer Lauf, Rad oder Laufband zählen.",
        "area": "endurance",
        "reward_xp": 40,
        "damage": 28,
    },
    {
        "id": "strength-set",
        "title": "Kraftanker setzen",
        "description": "Mindestens eine Kraftübung mit sauberer Technik erledigen.",
        "area": "strength",
        "reward_xp": 45,
        "damage": 32,
    },
    {
        "id": "protein-meal",
        "title": "Protein-Mahlzeit tracken",
        "description": "Eine Mahlzeit mit Proteinquelle eintragen.",
        "area": "nutrition",
        "reward_xp": 35,
        "damage": 24,
    },
    {
        "id": "water-check",
        "title": "Wasser-Rune aktivieren",
        "description": "Mindestens 0,7 Liter Wasser in einer Mahlzeit oder als Snack eintragen.",
        "area": "nutrition",
        "reward_xp": 30,
        "damage": 20,
    },
    {
        "id": "motivate-friend",
        "title": "Verbündeten stärken",
        "description": "Einer Person Motivation schicken oder eine faire Aufgabe zuweisen.",
        "area": "team",
        "reward_xp": 35,
        "damage": 26,
    },
    {
        "id": "plan-check",
        "title": "Plan prüfen",
        "description": "Fitnessplan, Wetter oder heutige Mahlzeiten ansehen und den Tag bewusst planen.",
        "area": "team",
        "reward_xp": 25,
        "damage": 18,
    },
]

RPG_DAILY_BOSSES = [
    {"name": "Schweinehund-Schatten", "title": "Tagesboss", "weakness": "Routine", "max_hp": 220},
    {"name": "Sofa-Magier", "title": "Tagesboss", "weakness": "Bewegung", "max_hp": 210},
    {"name": "Snack-Sphinx", "title": "Tagesboss", "weakness": "Protein", "max_hp": 230},
    {"name": "Ausreden-Golem", "title": "Tagesboss", "weakness": "Teamgeist", "max_hp": 240},
]

RPG_WEEKLY_BOSSES = [
    {"name": "Plateau-Drache", "title": "Wöchentlicher Endgegner", "weakness": "Konstanz", "max_hp": 1100},
    {"name": "Chaos-Titan", "title": "Wöchentlicher Endgegner", "weakness": "Planung", "max_hp": 1000},
    {"name": "Zucker-Hydra", "title": "Wöchentlicher Endgegner", "weakness": "Nahrung", "max_hp": 1050},
    {"name": "Trägheits-Kolos", "title": "Wöchentlicher Endgegner", "weakness": "Gemeinschaft", "max_hp": 1150},
]

RPG_TITLES = [
    (1, "Novize"),
    (3, "Adept"),
    (5, "Held"),
    (8, "Champion"),
    (12, "Legende"),
]

AVATAR_DEFAULTS = {
    "height_cm": 170,
    "weight_kg": 70,
    "neck_cm": 36,
    "shoulder_width": 100,
    "chest_cm": 96,
    "waist_width": 92,
    "hip_width": 98,
    "thigh_left_cm": 56,
    "thigh_right_cm": 56,
    "muscle": 45,
    "body_fat": 35,
    "hair_style": "short",
    "clothing_style": "training",
    "skin_color": "#d59f7a",
    "hair_color": "#2f241f",
    "outfit_color": "#2563eb",
}

AVATAR_HAIR_STYLES = {
    "short": "Kurz",
    "bob": "Bob",
    "long": "Lang",
    "curly": "Lockig",
    "bun": "Dutt",
}

AVATAR_CLOTHING_STYLES = {
    "training": "Trainingsshirt",
    "hoodie": "Hoodie",
    "tank": "Tanktop",
    "jacket": "Sportjacke",
    "dress": "Kleid",
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
            "focus": "Ganzkörper",
            "xp": {"endurance": 280, "strength": 470, "nutrition": 180, "team": 210},
            "streak": 3,
        },
        {
            "id": "nina",
            "name": "Nina",
            "focus": "Ernährung",
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
            "amount": "4 Sätze",
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
            "message": "Stark drangeblieben, heute zählt die Routine.",
            "created_at": "2026-06-04",
        }
    ],
    "groups": [
        {
            "id": "early-birds",
            "name": "Early Birds",
            "description": "Morgens aktiv werden, bevor der Tag laut wird.",
            "focus": "Ausdauer",
            "members": ["bea", "mara"],
            "created_by": "bea",
            "created_at": "2026-06-04",
        },
        {
            "id": "iron-circle",
            "name": "Iron Circle",
            "description": "Krafttraining, Technik und saubere Routinen.",
            "focus": "Kraft",
            "members": ["bea", "jonas"],
            "created_by": "jonas",
            "created_at": "2026-06-04",
        },
        {
            "id": "fuel-club",
            "name": "Fuel Club",
            "description": "Mahlzeiten planen, Protein treffen und Wasser nicht vergessen.",
            "focus": "Nahrung",
            "members": ["nina"],
            "created_by": "nina",
            "created_at": "2026-06-04",
        },
    ],
    "challenges": [
        {
            "id": "team-100",
            "title": "Team 100 Minuten Ausdauer",
            "category": "endurance",
            "group_id": "early-birds",
            "goal": 100,
            "unit": "Minuten",
            "xp": 120,
            "participants": {"bea": 30, "mara": 38},
            "completed": [],
        },
        {
            "id": "protein-week",
            "title": "Protein Woche",
            "category": "nutrition",
            "group_id": "fuel-club",
            "goal": 7,
            "unit": "Tage",
            "xp": 90,
            "participants": {"nina": 5},
            "completed": [],
        },
        {
            "id": "push-pull",
            "title": "Kraftzirkel",
            "category": "strength",
            "group_id": "iron-circle",
            "goal": 5,
            "unit": "Einheiten",
            "xp": 110,
            "participants": {"bea": 2, "jonas": 3},
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
    "profiles": {},
    "generated_plans": {},
    "food_items": DEFAULT_FOOD_ITEMS,
    "meal_ideas": DEFAULT_MEAL_IDEAS,
    "youtube_links": [],
    "rpg": {},
    "avatars": {},
    "weight_entries": [],
    "auth": {
        "passwords": {},
    },
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
    temp_path = STATE_PATH.with_name(f".{STATE_PATH.name}.{os.getpid()}.{uuid4().hex}.tmp")
    try:
        with temp_path.open("w", encoding="utf-8") as handle:
            json.dump(state, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        temp_path.replace(STATE_PATH)
    finally:
        temp_path.unlink(missing_ok=True)


def update_settings(state: dict, payload: dict) -> dict:
    label = str(payload.get("location_label") or "Berlin").strip()
    try:
        latitude = float(payload.get("latitude"))
        longitude = float(payload.get("longitude"))
    except (TypeError, ValueError) as exc:
        raise ValueError("Bitte gültige Koordinaten eintragen.") from exc

    if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
        raise ValueError("Koordinaten liegen außerhalb des gültigen Bereichs.")

    settings = state.setdefault("settings", {})
    settings["location_label"] = label
    settings["latitude"] = round(latitude, 6)
    settings["longitude"] = round(longitude, 6)
    return settings


def auth_passwords(state: dict) -> dict:
    return state.setdefault("auth", {}).setdefault("passwords", {})


def password_is_configured(state: dict, member_id: str) -> bool:
    record = auth_passwords(state).get(member_id, {})
    return bool(record.get("hash") and record.get("salt"))


def validate_password_strength(password: str) -> None:
    if len(password) < 12:
        raise ValueError("Passwort muss mindestens 12 Zeichen lang sein.")
    if len(password) > 128:
        raise ValueError("Passwort darf maximal 128 Zeichen lang sein.")
    if password.strip() != password:
        raise ValueError("Passwort darf nicht mit Leerzeichen beginnen oder enden.")
    checks = (
        any(char.islower() for char in password),
        any(char.isupper() for char in password),
        any(char.isdigit() for char in password),
        any(not char.isalnum() for char in password),
    )
    if sum(checks) < 3:
        raise ValueError("Passwort braucht mindestens 3 Arten: klein, groß, Zahl oder Sonderzeichen.")


def password_hash(password: str, salt: bytes, iterations: int) -> str:
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return base64.b64encode(digest).decode("ascii")


def set_member_password(state: dict, member_id: str, password: str) -> None:
    if member_id not in members_by_id(state):
        raise ValueError("Mitglied wurde nicht gefunden.")
    validate_password_strength(password)
    salt = os.urandom(16)
    auth_passwords(state)[member_id] = {
        "algorithm": "pbkdf2_sha256",
        "iterations": PASSWORD_ITERATIONS,
        "salt": base64.b64encode(salt).decode("ascii"),
        "hash": password_hash(password, salt, PASSWORD_ITERATIONS),
        "updated_at": today(),
    }


def verify_member_password(state: dict, member_id: str, password: str) -> bool:
    record = auth_passwords(state).get(member_id)
    if not record:
        return False
    try:
        salt = base64.b64decode(str(record["salt"]))
        iterations = int(record.get("iterations") or PASSWORD_ITERATIONS)
        expected = str(record["hash"])
    except (KeyError, TypeError, ValueError):
        return False
    actual = password_hash(password, salt, iterations)
    return hmac.compare_digest(actual, expected)


def as_int(payload: dict, key: str, default: int = 0) -> int:
    try:
        return int(float(payload.get(key, default)))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{key} muss eine Zahl sein.") from exc


def as_float(payload: dict, key: str, default: float = 0.0) -> float:
    try:
        return float(payload.get(key, default))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{key} muss eine Zahl sein.") from exc


def optional_value(payload: dict, key: str) -> str | None:
    value = payload.get(key)
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def as_optional_int(payload: dict, key: str) -> int | None:
    value = optional_value(payload, key)
    if value is None:
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{key} muss eine Zahl sein.") from exc


def as_optional_float(payload: dict, key: str) -> float | None:
    value = optional_value(payload, key)
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{key} muss eine Zahl sein.") from exc


def as_optional_date(payload: dict, key: str) -> str:
    value = optional_value(payload, key)
    if value is None:
        return ""
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{key} muss ein gültiges Datum sein.") from exc
    if parsed < date.today():
        raise ValueError("Bitte ein Zieldatum in der Zukunft eintragen.")
    return parsed.isoformat()


def as_choice_list(payload: dict, key: str, allowed: dict[str, str], default: list[str] | None = None) -> list[str]:
    raw_value = payload.get(key, default or [])
    if raw_value is None:
        raw_values = []
    elif isinstance(raw_value, list):
        raw_values = raw_value
    else:
        raw_values = str(raw_value).split(",")

    values = []
    for raw_item in raw_values:
        item = str(raw_item).strip()
        if not item:
            continue
        if item not in allowed:
            raise ValueError(f"{key} enthält einen unbekannten Wert.")
        if item not in values:
            values.append(item)
    return values


def clamp(value: int, minimum: int, maximum: int) -> int:
    return min(maximum, max(minimum, value))


def calculate_bmr(profile: dict) -> int:
    base = 10 * profile["weight_kg"] + 6.25 * profile["height_cm"] - 5 * profile["age"]
    sex_constant = {"male": 5, "female": -161, "neutral": -78}[profile["sex"]]
    return round(base + sex_constant)


def calculate_macros(profile: dict, calories: int) -> dict[str, int]:
    goal = profile["goal"]
    weight = profile["weight_kg"]
    protein_factor = {
        "lose": 1.9,
        "maintain": 1.6,
        "gain": 1.8,
        "performance": 1.7,
    }[goal]
    if profile["diet_style"] == "vegan":
        protein_factor += 0.1

    protein = round(weight * protein_factor)
    fat = max(45, round(weight * 0.8))
    carbs = max(80, round((calories - protein * 4 - fat * 9) / 4))
    return {"protein_g": protein, "fat_g": fat, "carbs_g": carbs}


def suggested_focus_areas(goal: str, training_focus: str) -> list[str]:
    suggestions = {
        "lose": ["full_body", "endurance_base", "core"],
        "maintain": ["full_body", "back_posture", "mobility"],
        "gain": ["legs_glutes", "upper_body", "core"],
        "performance": ["legs_glutes", "core", "endurance_base"],
    }.get(goal, ["full_body", "core"])
    focus_boosts = {
        "muscle": ["legs_glutes", "upper_body"],
        "strength": ["legs_glutes", "back_posture"],
        "endurance": ["endurance_base", "core"],
        "fat_loss": ["full_body", "endurance_base"],
        "posture": ["back_posture", "core", "mobility"],
        "mobility": ["mobility", "core"],
        "balanced": ["full_body"],
    }.get(training_focus, ["full_body"])
    ordered = []
    for item in suggestions + focus_boosts:
        if item not in ordered:
            ordered.append(item)
    return ordered[:4]


def active_injury_areas(profile: dict) -> list[str]:
    return [area for area in profile.get("injury_areas", []) if area != "none"]


def injury_considerations(profile: dict) -> list[dict]:
    injuries = active_injury_areas(profile)
    if not injuries and not profile.get("injury_notes"):
        return [
            {
                "title": "Keine Verletzungshistorie angegeben",
                "details": "Trotzdem gilt: Schmerz ist ein Stoppsignal, Technik geht vor Gewicht, Steigerungen bleiben klein.",
            }
        ]

    templates = {
        "shoulder": "Keine Übung in stechenden Schulterwinkel erzwingen. Drücken neutral greifen, Ellenbogen etwa 30-45 Grad vom Körper führen, Überkopf-Last nur schmerzfrei.",
        "back": "Rücken neutral halten, Rumpf vor jeder Wiederholung anspannen, schwere Hinge- oder Hebevarianten erst nach sauberer Technik steigern.",
        "knee": "Knie folgen den Zehen, Sprünge und tiefe Kniebeugen nur schmerzfrei. Starte mit Box Squat, Step-up niedrig oder Beinpresse kontrolliert.",
        "hip": "Hüfte nicht in Schmerzbereiche pressen. Schrittlänge verkleinern, Tempo reduzieren und Gesäßaktivierung vor Beintraining nutzen.",
        "ankle": "Bei Lauf- oder Sprungbelastung vorsichtig dosieren. Rad, Ergometer, Walking oder Laufband mit geringer Steigung sind die erste Wahl.",
        "wrist": "Handgelenke neutral halten. Für Liegestütze Griffe nutzen, Kurzhanteln neutral greifen und starke Beugung vermeiden.",
        "other": "Unklare Beschwerden konservativ behandeln: Last reduzieren, Bewegungsausmaß begrenzen und bei Unsicherheit medizinisch abklären.",
    }
    notes = [
        {"title": INJURY_AREA_LABELS.get(area, "Einschränkung"), "details": templates.get(area, templates["other"])}
        for area in injuries
    ]
    if profile.get("injury_notes"):
        notes.append({"title": "Deine Notiz", "details": profile["injury_notes"]})
    return notes


def exercise_item(
    name: str,
    sets: str,
    reps: str,
    explanation: str,
    cues: list[str],
    avoid: str,
    alternative: str,
    rest: str = "60-90 s",
    progression: str = "",
) -> dict:
    return {
        "name": name,
        "sets": sets,
        "reps": reps,
        "rest": rest,
        "explanation": explanation,
        "cues": cues,
        "avoid": avoid,
        "alternative": alternative,
        "progression": progression,
    }


def strength_progression_rule(profile: dict) -> str:
    experience = profile.get("experience", "beginner")
    recovery_pressure = (
        float(profile.get("sleep_hours") or 7.0) < 6.5
        or profile.get("sleep_quality") in ("poor", "irregular")
        or profile.get("stress_level") in ("high", "very_high")
    )
    if recovery_pressure:
        return "Nur steigern, wenn Technik, Schlaf und Schmerzfreiheit stimmen; sonst Gewicht halten oder 10 % leichter trainieren."
    if experience == "beginner":
        return "Doppelprogression: erst alle Sätze am oberen Wiederholungsziel sauber schaffen, dann nächstes Mal 1-2 kg je Hantel oder 2,5-5 kg an Maschinen erhöhen."
    if experience == "advanced":
        return "Wenn alle Arbeitssätze mit 1-2 Wiederholungen Reserve gelingen, nächste Woche 2,5-5 % mehr Last; jede 4. Woche bewusst leichter."
    return "Wenn alle Sätze im Zielbereich sauber gelingen, nächste Einheit 2,5-5 % mehr Last oder einen zusätzlichen sauberen Satz ergänzen."


def plan_progression_guidance(profile: dict, checkin_number: int) -> list[dict]:
    recovery_days = clamp(int(profile.get("recovery_days_per_week") or 2), 1, 4)
    adjustment = GOAL_ADJUSTMENTS.get(profile.get("goal", "maintain"), 0)
    calorie_direction = "leicht erhöhen" if adjustment > 0 else "leicht senken" if adjustment < 0 else "stabil halten"
    return [
        {
            "title": "Kraft progressiv steigern",
            "details": strength_progression_rule(profile),
        },
        {
            "title": "Ausdauer dosiert ausbauen",
            "details": "Alle 1-2 Wochen entweder 5 Minuten Zone 2 ergänzen oder einen Intervallblock hinzufügen, nicht beides gleichzeitig.",
        },
        {
            "title": "Deload und Regeneration",
            "details": f"Nach 3 harten Wochen folgt 1 leichtere Woche. Plane mindestens {recovery_days} Regenerationstage ein und steigere nicht bei Schmerzen.",
        },
        {
            "title": "Ernährung nach Check-in anpassen",
            "details": f"Nach Check-in {checkin_number} Kalorien {calorie_direction}; Gewicht, Hunger, Energie und Trainingsleistung entscheiden über die nächste Anpassung.",
        },
    ]


def strength_exercises(profile: dict, session_index: int, equipment: str) -> list[dict]:
    injuries = set(active_injury_areas(profile))
    focus = set(profile.get("focus_areas", []))
    experience = profile.get("experience", "beginner")
    sets = "2-3" if experience == "beginner" else "3-4" if experience == "intermediate" else "4"
    reps = "8-10" if profile.get("goal") in ("gain", "strength") else "8-12"
    progression = strength_progression_rule(profile)

    if profile["training_location"] == "gym":
        squat_name = "Beinpresse kontrolliert" if "knee" in injuries else "Goblet Squat oder Beinpresse"
        row_name = "Brustgestütztes Rudern" if "back" in injuries else "Kabelrudern"
        push_name = "Brustpresse neutral" if "shoulder" in injuries or "wrist" in injuries else "Kurzhantel-Bankdrücken"
        hinge_name = "Hip Thrust Maschine" if "back" in injuries else "Rumänisches Kreuzheben leicht"
    elif profile["training_location"] == "home":
        squat_name = "Box Squat zum Stuhl" if "knee" in injuries else "Goblet Squat mit Rucksack"
        row_name = "Einarmiges Rudern abgestützt"
        push_name = "Erhöhte Liegestütze mit Griffen" if "wrist" in injuries or "shoulder" in injuries else "Erhöhte Liegestütze"
        hinge_name = "Hip Hinge mit Rucksack" if "back" not in injuries else "Glute Bridge"
    else:
        squat_name = "Goblet Squat oder Beinpresse" if "knee" not in injuries else "Box Squat oder Beinpresse kurz"
        row_name = "Rudern abgestützt oder Kabelrudern"
        push_name = "Brustpresse neutral oder erhöhte Liegestütze" if "shoulder" in injuries else "Kurzhantel-Drücken oder Liegestütze"
        hinge_name = "Hip Thrust oder Rumänisches Kreuzheben leicht" if "back" not in injuries else "Hip Thrust"

    base = [
        exercise_item(
            squat_name,
            sets,
            reps,
            "Trainiert Beine, Gesäß und Rumpf als Hauptbewegung.",
            ["Füße fest, Gewicht über Mittelfuß", "Knie folgen den Zehen", "Brustkorb ruhig, Bauch fest"],
            "Nicht in den unteren Rücken fallen und keine schmerzhaften Kniepositionen erzwingen.",
            "Bei Beschwerden: kleineres Bewegungsausmaß oder nur Sitz-zu-Stand.",
            progression=progression,
        ),
        exercise_item(
            row_name,
            sets,
            "10-12",
            "Stärkt oberen Rücken und Haltung, wichtig als Ausgleich zu Drückübungen.",
            ["Schulterblätter nach hinten unten ziehen", "Nacken lang lassen", "Zug aus dem Ellenbogen führen"],
            "Nicht mit Schwung reissen und nicht ins Hohlkreuz ausweichen.",
            "Bei Rückenstress: Brust abstützen oder Band-Rudern im Sitzen.",
            progression=progression,
        ),
        exercise_item(
            push_name,
            sets,
            "8-12",
            "Trainiert Brust, Schultern und Arme mit kontrollierter Druckbewegung.",
            ["Handgelenke neutral", "Ellenbogen leicht schräg am Körper", "Langsam ablassen, kraftvoll hochdrücken"],
            "Keine stechenden Schulterwinkel, kein Durchhängen im unteren Rücken.",
            "Bei Schulterthema: Bewegungsradius kleiner und neutraler Griff.",
            progression=progression,
        ),
        exercise_item(
            hinge_name,
            sets,
            "8-10",
            "Stärkt Gesäß, Beinrückseite und Hüftstreckung.",
            ["Hüfte nach hinten schieben", "Rücken neutral", "Gewicht nah am Körper halten"],
            "Nicht aus dem Rücken heben und nicht in Schmerz hineinziehen.",
            "Bei Rückenhistorie: Glute Bridge oder Hip Thrust statt freiem Heben.",
            progression=progression,
        ),
        exercise_item(
            "Dead Bug" if "core" in focus or session_index % 2 == 0 else "Pallof Press",
            "2-3",
            "8-12 je Seite",
            "Schult Rumpfspannung, damit Kraftübungen stabiler und sicherer werden.",
            ["Rippen unten halten", "Langsam ausatmen", "Becken ruhig halten"],
            "Nicht ins Hohlkreuz kippen und nicht hektisch arbeiten.",
            "Bei Nackenstress: Kopf ablegen und Bewegung kleiner machen.",
            "45-60 s",
            "Erst Kontrolle und Atemrhythmus verbessern, dann Wiederholungen oder Haltezeit leicht erhöhen.",
        ),
    ]

    if "back_posture" in focus:
        base.append(
            exercise_item(
                "Face Pull oder Band Pull-Apart",
                "2-3",
                "12-15",
                "Extra-Fokus für Haltung, Schulterblattkontrolle und oberen Rücken.",
                ["Daumen Richtung Ohren", "Schultern tief", "Langsam zurückführen"],
                "Nicht ins Hohlkreuz ziehen und nicht mit dem Nacken arbeiten.",
                "Bei Schulterreiz: Band leichter wählen oder Bewegung kleiner.",
                "45-60 s",
                "Erst saubere Wiederholungen bis 15 schaffen, dann Band stärker oder langsameres Tempo wählen.",
            )
        )
    if "legs_glutes" in focus and "hip" not in injuries:
        base.append(
            exercise_item(
                "Glute Bridge Pause Reps",
                "2-3",
                "10-14",
                "Zusätzlicher Gesäßfokus ohne hohe Gelenkbelastung.",
                ["Oben 1 Sekunde halten", "Rippen unten", "Druck über Fersen"],
                "Nicht aus dem unteren Rücken überstrecken.",
                "Bei Hüftreiz: Bewegungsradius verkleinern.",
                "45-60 s",
                progression,
            )
        )

    return base[:6]


def endurance_blocks(profile: dict, session_index: int, endurance_place: str) -> list[dict]:
    injuries = set(active_injury_areas(profile))
    low_impact = bool(injuries.intersection({"knee", "ankle", "hip", "back"}))
    if low_impact:
        mode = "Rad, Ergometer, Crosstrainer oder Walking"
    elif profile["endurance_preference"] == "indoor":
        mode = "Laufband, Ruderergometer oder Bike"
    elif profile["endurance_preference"] == "outdoor":
        mode = "Laufen, Radfahren oder Wandern draußen"
    else:
        mode = f"Laufen, Radfahren, Wandern oder Studiooption {endurance_place}"

    if profile["goal"] == "performance" and session_index % 2 == 1 and not low_impact:
        main = "6 x 1 min zügig, dazwischen 2 min locker. Nur ausführen, wenn Schlaf und Gelenke gut sind."
    else:
        main = "25-40 min Zone 2: du kannst noch kurze Sätze sprechen und atmest kontrolliert."

    return [
        exercise_item(
            "Warm-up",
            "1",
            "6-8 min",
            f"Locker starten mit {mode}, Puls und Gelenke vorbereiten.",
            ["Tempo langsam steigern", "Schultern locker", "Schmerzfrei bleiben"],
            "Nicht kalt in Intervalle oder Steigungen starten.",
            "Bei Beschwerden: 5 min gehen und Belastung abbrechen.",
            "ohne Pause",
        ),
        exercise_item(
            "Hauptteil",
            "1",
            main,
            "Der Hauptreiz für Herz-Kreislauf, Fettstoffwechsel oder Leistungsaufbau.",
            ["Atmung kontrollieren", "Schritte oder Trittfrequenz gleichmäßig", "Intensität nicht durch Ego treiben lassen"],
            "Kein Sprinten bei Knie-, Hüft- oder Sprunggelenkschmerz.",
            "Bei Belastungsproblemen: Bike oder Crosstrainer statt Laufbelastung.",
            "nach Bedarf",
        ),
        exercise_item(
            "Cooldown",
            "1",
            "5-8 min",
            "Puls langsam senken und Regeneration einleiten.",
            ["Tempo schrittweise senken", "Locker ausschwingen", "Danach Wasser und kurzer Energie-Check"],
            "Nicht abrupt nach hoher Intensität stoppen.",
            "Bei Schwindel: hinsetzen, trinken, Training dokumentieren.",
            "ohne Pause",
        ),
    ]


def focus_recommendations(profile: dict) -> list[dict]:
    selected = [BODY_FOCUS_LABELS[item] for item in profile.get("focus_areas", []) if item in BODY_FOCUS_LABELS]
    suggested = [BODY_FOCUS_LABELS[item] for item in suggested_focus_areas(profile["goal"], profile["training_focus"])]
    goal_label = GOAL_LABELS.get(profile["goal"], "Fitnessziel")
    focus_label = TRAINING_FOCUS_LABELS.get(profile["training_focus"], "Ausgewogen stärker werden")
    recommendations = [
        {
            "title": "Dein Fokus",
            "details": ", ".join(selected) if selected else "Keine Auswahl: Bea nutzt den Zielvorschlag.",
        },
        {
            "title": "Bea Vorschlag",
            "details": f"Für {goal_label} mit Fokus {focus_label}: {', '.join(suggested)}.",
        },
        {
            "title": "Progression",
            "details": "Steigere zuerst Technik und Wiederholungen, dann Gewicht. Wenn Schmerz oder Schlafproblem auftaucht, bleibt die Last stabil.",
        },
    ]
    return recommendations


def training_sessions(profile: dict) -> list[dict]:
    workouts = profile["workouts_per_week"]
    location = profile["training_location"]
    endurance = profile["endurance_preference"]
    goal = profile["goal"]
    experience = profile["experience"]
    sleep_hours = float(profile.get("sleep_hours") or 7.0)
    stress_level = profile.get("stress_level", "medium")
    sleep_quality = profile.get("sleep_quality", "okay")
    recovery_style = profile.get("recovery_style", "balanced")

    strength_count = 2 if workouts <= 3 else 3
    if goal == "gain":
        strength_count = min(workouts, strength_count + 1)
    recovery_pressure = (
        sleep_hours < 6.5
        or sleep_quality in ("poor", "irregular")
        or stress_level in ("high", "very_high")
    )
    if recovery_pressure and workouts > 2:
        strength_count = max(1, strength_count - 1)
    endurance_count = max(1, workouts - strength_count)

    equipment = {
        "gym": "Langhantel, Maschinen und freie Gewichte",
        "home": "Körpergewicht, Band oder Kurzhanteln",
        "mixed": "Studio oder Zuhause, je nach Woche",
    }[location]
    endurance_place = {
        "outdoor": "draußen",
        "indoor": "im Studio",
        "mixed": "je nach Wetter aus dem Fitnessplan",
    }[endurance]
    intensity = {
        "beginner": "sauber, locker steigernd",
        "intermediate": "moderat fordernd",
        "advanced": "progressiv und anspruchsvoll",
    }[experience]
    if recovery_pressure:
        intensity = f"{intensity}, aber mit klarer Belastungsgrenze"
    if recovery_style == "push" and not recovery_pressure:
        intensity = f"{intensity}, mit messbarer Progression"

    sessions = []
    safety_notes = injury_considerations(profile)
    focus_label = TRAINING_FOCUS_LABELS.get(profile.get("training_focus", "balanced"), "Ausgewogen stärker werden")
    for index in range(strength_count):
        sessions.append(
            {
                "type": "Kraft",
                "title": f"Kraft Einheit {index + 1}",
                "duration": "45-60 min",
                "focus": focus_label,
                "details": f"Ganzkörper mit {equipment}: Unterkörper, Zug, Druck, Hüfte und Rumpf. Intensität: {intensity}.",
                "exercises": strength_exercises(profile, index, equipment),
                "safety_notes": safety_notes,
            }
        )

    for index in range(endurance_count):
        if goal == "performance":
            detail = "1 lockere Zone-2 Einheit und 1 Intervallblock, wenn die Woche es erlaubt."
        elif goal == "lose":
            detail = "Ruhige Zone-2 Einheit für zusätzlichen Verbrauch und Regeneration."
        else:
            detail = "Grundlagenausdauer ohne die Krafttage zu stören."
        sessions.append(
            {
                "type": "Ausdauer",
                "title": f"Ausdauer Einheit {index + 1}",
                "duration": "30-50 min",
                "focus": "Ausdauerbasis und Belastungssteuerung",
                "details": f"{detail} Ort: {endurance_place}.",
                "exercises": endurance_blocks(profile, index, endurance_place),
                "safety_notes": safety_notes,
            }
        )

    return sessions[:workouts]


def recovery_sessions(profile: dict) -> list[dict]:
    recovery_days = clamp(int(profile.get("recovery_days_per_week") or 2), 1, 4)
    mobility = clamp(int(profile.get("mobility_minutes") or 12), 0, 60)
    sleep_hours = float(profile.get("sleep_hours") or 7.0)
    sleep_quality = profile.get("sleep_quality", "okay")
    stress_level = profile.get("stress_level", "medium")
    work_style = WORK_STYLE_LABELS.get(profile.get("work_style", "mixed"), "abwechslungsreich")

    mobility_text = f"{mobility} min Mobility" if mobility else "5-10 min lockere Gelenkpflege"
    sleep_note = "Schlaf stabil halten" if sleep_hours >= 7 and sleep_quality == "good" else "Schlaf priorisieren und Spätbelastung reduzieren"
    stress_note = "Atmung, Spaziergang oder leichtes Dehnen" if stress_level in ("high", "very_high") else "lockere Bewegung ohne Leistungsdruck"
    blocks = [
        {
            "type": "Regeneration",
            "title": "Ruhetag mit Beweglichkeit",
            "duration": f"{mobility_text}",
            "details": f"Entlastet den Plan bei Alltag mit {work_style}. Fokus: Hüfte, Brustwirbelsäule, Waden und Nacken.",
        },
        {
            "type": "Regeneration",
            "title": "Schlaf- und Nervensystem-Reset",
            "duration": "15-25 min",
            "details": f"{sleep_note}: Abendroutine, ruhiger Puls und kurze Reflexion zu Energie, Hunger und Muskelkater.",
        },
        {
            "type": "Regeneration",
            "title": "Aktive Erholung",
            "duration": "20-40 min",
            "details": f"{stress_note}. Geeignet für lockeres Gehen, entspanntes Radfahren oder sehr leichtes Laufband.",
        },
        {
            "type": "Regeneration",
            "title": "Deload-Fenster",
            "duration": "1 Einheit leichter",
            "details": "Wenn zwei Tage in Folge Energie oder Schlaf schlecht sind: Volumen halbieren, Technik sauber halten, keine Maximalversuche.",
        },
    ]
    return blocks[:recovery_days]


def goal_tracking_plan(profile: dict, calories: dict, training: list[dict]) -> dict:
    metric = profile.get("goal_metric", "habit")
    tracking = profile.get("tracking_frequency", "weekly")
    target_weight = profile.get("target_weight_kg")
    current_weight = profile.get("weight_kg")
    target_date = profile.get("target_date", "")
    goal_text = profile.get("primary_goal_text") or GOAL_LABELS.get(profile["goal"], "Fitnessziel")

    milestones = [
        "Woche 1: Basiswerte eintragen und die ersten Quests abschließen.",
        "Woche 2-3: Training, Hunger, Schlaf und Stimmung gegen den Plan prüfen.",
        "Woche 4: Kalorien und Trainingslast anhand der echten Bilanz anpassen.",
    ]
    if target_weight:
        delta = round(float(target_weight) - float(current_weight), 1)
        direction = "aufbauen" if delta > 0 else "reduzieren"
        milestones.insert(1, f"Gewichtsziel: {abs(delta)} kg {direction}, in kleinen Wochenetappen statt Sprint.")
    if target_date:
        milestones.append(f"Zieldatum: {target_date}. Bis dahin werden Wochenboss, Gewichtstrend und Energie abgeglichen.")

    checkpoints = [
        {
            "title": "Check-in Rhythmus",
            "details": f"{TRACKING_FREQUENCY_LABELS.get(tracking, 'wöchentlich')} Gewicht, Energie, Schlaf, Hunger und Questserie bewerten.",
        },
        {
            "title": "Plan-Treue",
            "details": f"{len(training)} geplante Einheiten inklusive Regeneration markieren und Ausfälle als Alltagshinweis notieren.",
        },
        {
            "title": "Boss-Fortschritt",
            "details": "Tägliche Quests zeigen, ob der Charakter wirklich stärker wird: nicht perfekt sein, sondern wieder auftauchen.",
        },
    ]
    return {
        "goal_text": goal_text,
        "metric": metric,
        "metric_label": GOAL_METRIC_LABELS.get(metric, "Gewohnheiten"),
        "tracking_frequency": tracking,
        "tracking_label": TRACKING_FREQUENCY_LABELS.get(tracking, "wöchentlich"),
        "target_weight_kg": target_weight,
        "target_date": target_date,
        "calorie_delta": int(calories["target"]) - int(calories["maintenance"]),
        "milestones": milestones,
        "checkpoints": checkpoints,
    }


def adventure_profile(profile: dict) -> dict:
    role = profile.get("adventure_role", "guardian")
    work_style = profile.get("work_style", "mixed")
    sleep_quality = profile.get("sleep_quality", "okay")
    motivation = profile.get("motivation_style", "story")
    hobbies = profile.get("hobbies") or "noch offen"
    origin = profile.get("character_origin") or "Der Alltag ist das Startgebiet."
    character_name = profile.get("character_name") or ""
    return {
        "character_name": character_name,
        "role": role,
        "role_label": ADVENTURE_ROLE_LABELS.get(role, "Wächter"),
        "origin": origin,
        "hobbies": hobbies,
        "daily_life": f"{WORK_STYLE_LABELS.get(work_style, 'abwechslungsreich')}, {profile.get('daily_steps', 6000)} Schritte, {profile.get('work_schedule') or 'normaler Wochenrhythmus'}",
        "sleep": f"{profile.get('sleep_hours', 7)} h, {SLEEP_QUALITY_LABELS.get(sleep_quality, 'wechselhaft')}",
        "motivation_label": MOTIVATION_STYLE_LABELS.get(motivation, "Story, Quests und Abenteuer"),
        "avatar_notes": "Avatar und Körperform werden mit Ganzkörperbildern, Größe und manuellen Anpassungen fortgeschrieben.",
    }


def meal_templates(profile: dict, calories: int, macros: dict) -> list[dict]:
    meals = profile["meals_per_day"]
    diet = profile["diet_style"]
    protein_source = {
        "mixed": "Eier, Fisch, Fleisch, Quark oder Hülsenfrüchte",
        "vegetarian": "Quark, Skyr, Eier, Tofu oder Hülsenfrüchte",
        "vegan": "Tofu, Tempeh, Seitan, Bohnen oder veganes Protein",
        "high_protein": "mageres Protein, Skyr, Eier oder Proteinshake",
    }[diet]
    calories_per_meal = round(calories / meals)
    protein_per_meal = round(macros["protein_g"] / meals)
    templates = []
    for index in range(meals):
        if index == 0:
            title = "Frühstück"
            focus = "Protein plus langsam verdauliche Kohlenhydrate"
        elif index == meals - 1:
            title = "Abendessen"
            focus = "Protein, Gemüse und je nach Training Kohlenhydrate"
        else:
            title = f"Mahlzeit {index + 1}"
            focus = "Planbare Energie für Training und Alltag"
        templates.append(
            {
                "title": title,
                "target": f"ca. {calories_per_meal} kcal, {protein_per_meal} g Protein",
                "details": f"{focus}. Gute Quellen: {protein_source}.",
            }
        )
    return templates


def add_days(date_key: str, days: int) -> str:
    return (date.fromisoformat(date_key) + timedelta(days=days)).isoformat()


def next_questionnaire_date(answered_at: str) -> str:
    return add_days(answered_at, CHECKIN_INTERVAL_DAYS)


def days_until(date_key: str) -> int:
    return (date.fromisoformat(date_key) - date.today()).days


def questionnaire_status(state: dict, member_id: str) -> dict:
    plans = state.get("generated_plans", {})
    profile = state.get("profiles", {}).get(member_id, {})
    plan = plans.get(member_id)
    if not plan:
        return {
            "member_id": member_id,
            "state": "onboarding",
            "is_due": True,
            "label": "Anmeldung offen",
            "message": "Beim ersten Anmelden wird der Fragebogen ausgefüllt und der Startplan erstellt.",
            "button_label": "Onboarding starten",
            "last_completed_at": "",
            "next_due_at": today(),
            "days_until_due": 0,
        }

    last_completed_at = str(profile.get("last_questionnaire_at") or plan.get("created_at") or today())
    next_due_at = str(profile.get("next_questionnaire_at") or plan.get("next_checkin_at") or next_questionnaire_date(last_completed_at))
    remaining = days_until(next_due_at)
    is_due = remaining <= 0
    return {
        "member_id": member_id,
        "state": "due" if is_due else "scheduled",
        "is_due": is_due,
        "label": "3-Monats-Check-in fällig" if is_due else "Plan aktuell",
        "message": (
            "Bitte Fortschritt, Alltag und Ziele neu beantworten. Danach werden Training und Ernährung angepasst."
            if is_due
            else f"Nächster automatischer Check-in in {remaining} Tagen."
        ),
        "button_label": "Check-in beantworten" if is_due else "Plan ansehen",
        "last_completed_at": last_completed_at,
        "next_due_at": next_due_at,
        "days_until_due": remaining,
    }


def create_personal_plan(state: dict, payload: dict) -> dict:
    member_id = str(payload.get("member_id") or "")
    if member_id not in members_by_id(state):
        raise ValueError("Mitglied wurde nicht gefunden.")

    answered_at = today()
    existing_profile = state.setdefault("profiles", {}).get(member_id, {})
    previous_plan = state.setdefault("generated_plans", {}).get(member_id)
    checkin_count = int(existing_profile.get("checkin_count") or 0) + 1
    is_onboarding = not previous_plan

    target_weight_kg = as_optional_float(payload, "target_weight_kg")
    daily_steps = as_optional_int(payload, "daily_steps")
    sleep_hours = as_optional_float(payload, "sleep_hours")
    recovery_days = as_optional_int(payload, "recovery_days_per_week")
    mobility_minutes = as_optional_int(payload, "mobility_minutes")
    focus_areas = as_choice_list(payload, "focus_areas", BODY_FOCUS_LABELS)
    injury_areas = as_choice_list(payload, "injury_areas", INJURY_AREA_LABELS, ["none"])
    if len(injury_areas) > 1 and "none" in injury_areas:
        injury_areas = [area for area in injury_areas if area != "none"]

    profile = {
        "member_id": member_id,
        "age": as_int(payload, "age"),
        "sex": str(payload.get("sex") or "neutral"),
        "height_cm": as_float(payload, "height_cm"),
        "weight_kg": as_float(payload, "weight_kg"),
        "activity": str(payload.get("activity") or "moderate"),
        "goal": str(payload.get("goal") or "maintain"),
        "workouts_per_week": clamp(as_int(payload, "workouts_per_week", 4), 2, 6),
        "training_location": str(payload.get("training_location") or "mixed"),
        "endurance_preference": str(payload.get("endurance_preference") or "mixed"),
        "diet_style": str(payload.get("diet_style") or "mixed"),
        "meals_per_day": clamp(as_int(payload, "meals_per_day", 3), 2, 6),
        "experience": str(payload.get("experience") or "beginner"),
        "restrictions": str(payload.get("restrictions") or "").strip(),
        "primary_goal_text": str(payload.get("primary_goal_text") or "").strip(),
        "target_weight_kg": target_weight_kg,
        "target_date": as_optional_date(payload, "target_date"),
        "goal_metric": str(payload.get("goal_metric") or "habit"),
        "tracking_frequency": str(payload.get("tracking_frequency") or "weekly"),
        "hobbies": str(payload.get("hobbies") or "").strip(),
        "work_style": str(payload.get("work_style") or "mixed"),
        "work_schedule": str(payload.get("work_schedule") or "").strip(),
        "daily_steps": clamp(daily_steps if daily_steps is not None else 6000, 0, 40000),
        "sleep_hours": sleep_hours if sleep_hours is not None else 7.0,
        "sleep_quality": str(payload.get("sleep_quality") or "okay"),
        "stress_level": str(payload.get("stress_level") or "medium"),
        "recovery_days_per_week": clamp(recovery_days if recovery_days is not None else 2, 1, 4),
        "mobility_minutes": clamp(mobility_minutes if mobility_minutes is not None else 12, 0, 60),
        "recovery_style": str(payload.get("recovery_style") or "balanced"),
        "training_focus": str(payload.get("training_focus") or "balanced"),
        "focus_areas": focus_areas,
        "injury_areas": injury_areas or ["none"],
        "injury_notes": str(payload.get("injury_notes") or "").strip(),
        "character_name": str(payload.get("character_name") or "").strip(),
        "character_origin": str(payload.get("character_origin") or "").strip(),
        "adventure_role": str(payload.get("adventure_role") or "guardian"),
        "motivation_style": str(payload.get("motivation_style") or "story"),
        "created_at": existing_profile.get("created_at") or answered_at,
        "updated_at": answered_at,
        "onboarded_at": existing_profile.get("onboarded_at") or answered_at,
        "last_questionnaire_at": answered_at,
        "next_questionnaire_at": next_questionnaire_date(answered_at),
        "checkin_count": checkin_count,
        "questionnaire_type": "onboarding" if is_onboarding else "quarterly_checkin",
    }

    if not 13 <= profile["age"] <= 90:
        raise ValueError("Bitte ein Alter zwischen 13 und 90 eintragen.")
    if profile["sex"] not in ("female", "male", "neutral"):
        raise ValueError("Bitte ein Geschlecht für die Formel auswählen.")
    if not 120 <= profile["height_cm"] <= 230:
        raise ValueError("Bitte eine plausible Körpergröße eintragen.")
    if not 35 <= profile["weight_kg"] <= 250:
        raise ValueError("Bitte ein plausibles Gewicht eintragen.")
    if profile["activity"] not in ACTIVITY_FACTORS:
        raise ValueError("Aktivitätslevel wurde nicht gefunden.")
    if profile["goal"] not in GOAL_ADJUSTMENTS:
        raise ValueError("Ziel wurde nicht gefunden.")
    if profile["training_location"] not in TRAINING_LABELS:
        raise ValueError("Trainingsort wurde nicht gefunden.")
    if profile["endurance_preference"] not in ENDURANCE_LABELS:
        raise ValueError("Ausdauerpräferenz wurde nicht gefunden.")
    if profile["diet_style"] not in DIET_LABELS:
        raise ValueError("Ernährungsform wurde nicht gefunden.")
    if profile["experience"] not in ("beginner", "intermediate", "advanced"):
        raise ValueError("Trainingserfahrung wurde nicht gefunden.")
    if target_weight_kg is not None and not 35 <= target_weight_kg <= 250:
        raise ValueError("Bitte ein plausibles Zielgewicht eintragen.")
    if profile["goal_metric"] not in GOAL_METRIC_LABELS:
        raise ValueError("Zielmessung wurde nicht gefunden.")
    if profile["tracking_frequency"] not in TRACKING_FREQUENCY_LABELS:
        raise ValueError("Trackingrhythmus wurde nicht gefunden.")
    if profile["work_style"] not in WORK_STYLE_LABELS:
        raise ValueError("Arbeitsalltag wurde nicht gefunden.")
    if not 3 <= profile["sleep_hours"] <= 12:
        raise ValueError("Bitte realistische Schlafstunden zwischen 3 und 12 eintragen.")
    if profile["sleep_quality"] not in SLEEP_QUALITY_LABELS:
        raise ValueError("Schlafqualität wurde nicht gefunden.")
    if profile["stress_level"] not in STRESS_LABELS:
        raise ValueError("Stresslevel wurde nicht gefunden.")
    if profile["recovery_style"] not in RECOVERY_LABELS:
        raise ValueError("Regenerationsstil wurde nicht gefunden.")
    if profile["training_focus"] not in TRAINING_FOCUS_LABELS:
        raise ValueError("Trainingsfokus wurde nicht gefunden.")
    if profile["adventure_role"] not in ADVENTURE_ROLE_LABELS:
        raise ValueError("Abenteuerrolle wurde nicht gefunden.")
    if profile["motivation_style"] not in MOTIVATION_STYLE_LABELS:
        raise ValueError("Motivationsart wurde nicht gefunden.")
    if not profile["focus_areas"]:
        profile["focus_areas"] = suggested_focus_areas(profile["goal"], profile["training_focus"])

    bmr = calculate_bmr(profile)
    maintenance = round(bmr * ACTIVITY_FACTORS[profile["activity"]])
    target_calories = max(1200, maintenance + GOAL_ADJUSTMENTS[profile["goal"]])
    macros = calculate_macros(profile, target_calories)
    training = training_sessions(profile)
    regeneration = recovery_sessions(profile)
    calories = {
        "bmr": bmr,
        "maintenance": maintenance,
        "target": target_calories,
        "goal_label": GOAL_LABELS[profile["goal"]],
        "activity_label": ACTIVITY_LABELS[profile["activity"]],
    }
    plan = {
        "member_id": member_id,
        "created_at": answered_at,
        "plan_version": checkin_count,
        "plan_reason": "Anmeldung" if is_onboarding else "3-Monats-Check-in",
        "previous_plan_created_at": previous_plan.get("created_at") if previous_plan else "",
        "last_questionnaire_at": answered_at,
        "next_checkin_at": profile["next_questionnaire_at"],
        "calories": calories,
        "macros": macros,
        "training": training,
        "regeneration": regeneration,
        "nutrition": meal_templates(profile, target_calories, macros),
        "progression": plan_progression_guidance(profile, checkin_count),
        "training_focus": {
            "label": TRAINING_FOCUS_LABELS[profile["training_focus"]],
            "areas": [BODY_FOCUS_LABELS[area] for area in profile["focus_areas"]],
            "recommendations": focus_recommendations(profile),
            "injury_considerations": injury_considerations(profile),
        },
        "goal_tracking": goal_tracking_plan(profile, calories, training + regeneration),
        "adventure": adventure_profile(profile),
        "lifestyle": {
            "work_style_label": WORK_STYLE_LABELS[profile["work_style"]],
            "daily_steps": profile["daily_steps"],
            "sleep_label": SLEEP_QUALITY_LABELS[profile["sleep_quality"]],
            "stress_label": STRESS_LABELS[profile["stress_level"]],
            "recovery_label": RECOVERY_LABELS[profile["recovery_style"]],
        },
        "notes": [
            "Kalorienbedarf ist eine Schätzung und sollte nach 2-3 Wochen anhand von Gewicht, Energie und Leistung angepasst werden.",
            "Bei Erkrankungen, Schwangerschaft oder Essstörungen bitte medizinisch abklären.",
        ],
    }
    if profile["restrictions"]:
        plan["notes"].append(f"Rücksicht auf: {profile['restrictions']}.")
    if active_injury_areas(profile) or profile["injury_notes"]:
        plan["notes"].append("Verletzungshistorie wurde berücksichtigt. Bei akuten Schmerzen, Taubheit oder Unsicherheit bitte medizinisch abklären.")

    state.setdefault("profiles", {})[member_id] = profile
    state.setdefault("generated_plans", {})[member_id] = plan
    award_xp(state, member_id, "nutrition", 35)
    award_xp(state, member_id, "team", 15)
    return plan


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


def rpg_title_for_level(level: int) -> str:
    title = RPG_TITLES[0][1]
    for minimum_level, candidate in RPG_TITLES:
        if level >= minimum_level:
            title = candidate
    return title


def rpg_character(member: dict) -> dict:
    total = total_xp(member)
    level = level_for_xp(total)
    strongest_area = max(AREAS, key=lambda area: int(member.get("xp", {}).get(area, 0)))
    return {
        "member_id": member["id"],
        "name": member["name"],
        "class_name": AREA_LABELS[strongest_area],
        "title": rpg_title_for_level(level["level"]),
        "level": level["level"],
        "progress": level["progress"],
        "next_xp": level["next_xp"],
        "total_xp": total,
        "strongest_area": strongest_area,
        "streak": int(member.get("streak", 0)),
    }


def week_key_for(date_key: str | None = None) -> str:
    current = date.fromisoformat(date_key) if date_key else date.today()
    iso = current.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def rotated_pool(pool: list[dict], seed: int, count: int) -> list[dict]:
    start = seed % len(pool)
    return [copy.deepcopy(pool[(start + index) % len(pool)]) for index in range(count)]


def daily_quests_for(date_key: str) -> list[dict]:
    seed = date.fromisoformat(date_key).toordinal()
    quests = rotated_pool(RPG_DAILY_QUEST_POOL, seed, 4)
    for quest in quests:
        quest["date"] = date_key
    return quests


def daily_boss_for(date_key: str) -> dict:
    seed = date.fromisoformat(date_key).toordinal()
    boss = copy.deepcopy(RPG_DAILY_BOSSES[seed % len(RPG_DAILY_BOSSES)])
    boss.update(
        {
            "id": f"daily-{date_key}",
            "date": date_key,
            "hp": boss["max_hp"],
            "status": "active",
            "defeated_at": "",
        }
    )
    return boss


def weekly_boss_for(week_key: str) -> dict:
    year_text, week_text = week_key.split("-W", 1)
    monday = date.fromisocalendar(int(year_text), int(week_text), 1)
    boss = copy.deepcopy(RPG_WEEKLY_BOSSES[monday.toordinal() % len(RPG_WEEKLY_BOSSES)])
    boss.update(
        {
            "id": f"weekly-{week_key}",
            "week": week_key,
            "hp": boss["max_hp"],
            "status": "active",
            "defeated_at": "",
        }
    )
    return boss


def ensure_rpg_state(state: dict) -> dict:
    rpg = state.setdefault("rpg", {})
    date_key = today()
    week_key = week_key_for(date_key)

    if rpg.get("daily_date") != date_key or not rpg.get("daily_boss"):
        rpg["daily_date"] = date_key
        rpg["daily_quests"] = daily_quests_for(date_key)
        rpg["daily_boss"] = daily_boss_for(date_key)

    if rpg.get("weekly_key") != week_key or not rpg.get("weekly_boss"):
        rpg["weekly_key"] = week_key
        rpg["weekly_boss"] = weekly_boss_for(week_key)

    rpg.setdefault("completed_quests", {})
    rpg.setdefault("battle_log", [])
    return rpg


def rpg_completion_key(date_key: str, member_id: str, quest_id: str) -> str:
    return f"{date_key}:{member_id}:{quest_id}"


def apply_boss_damage(boss: dict, damage: int) -> dict:
    before = max(0, int(boss.get("hp", boss.get("max_hp", 0))))
    actual_damage = min(before, max(0, int(damage)))
    boss["hp"] = before - actual_damage
    defeated = before > 0 and boss["hp"] == 0
    if defeated:
        boss["status"] = "defeated"
        boss["defeated_at"] = today()
    return {"damage": actual_damage, "defeated": defeated}


def complete_daily_quest(state: dict, payload: dict) -> dict:
    rpg = ensure_rpg_state(state)
    member_id = str(payload.get("member_id") or "")
    quest_id = str(payload.get("quest_id") or "")
    members = members_by_id(state)

    if member_id not in members:
        raise ValueError("Mitglied wurde nicht gefunden.")

    quest = next((item for item in rpg["daily_quests"] if item["id"] == quest_id), None)
    if not quest:
        raise ValueError("Quest wurde nicht gefunden.")

    completion_key = rpg_completion_key(rpg["daily_date"], member_id, quest_id)
    completions = rpg.setdefault("completed_quests", {})
    if completion_key in completions:
        raise ValueError("Diese Quest wurde für dieses Mitglied heute schon abgeschlossen.")

    reward_xp = int(quest["reward_xp"])
    award_xp(state, member_id, quest["area"], reward_xp)
    award_xp(state, member_id, "team", 5)

    character = rpg_character(members[member_id])
    damage = int(quest["damage"]) + character["level"] * 3
    daily_result = apply_boss_damage(rpg["daily_boss"], damage)
    weekly_result = apply_boss_damage(rpg["weekly_boss"], max(10, damage // 2))

    completions[completion_key] = {
        "member_id": member_id,
        "quest_id": quest_id,
        "date": rpg["daily_date"],
        "reward_xp": reward_xp,
        "damage": daily_result["damage"],
        "created_at": today(),
    }

    if daily_result["defeated"]:
        award_xp(state, member_id, "team", 35)
    if weekly_result["defeated"]:
        award_xp(state, member_id, "team", 90)

    rpg.setdefault("battle_log", []).insert(
        0,
        {
            "id": new_id("battle"),
            "member_id": member_id,
            "quest_id": quest_id,
            "quest_title": quest["title"],
            "daily_damage": daily_result["damage"],
            "weekly_damage": weekly_result["damage"],
            "daily_defeated": daily_result["defeated"],
            "weekly_defeated": weekly_result["defeated"],
            "created_at": today(),
        },
    )
    rpg["battle_log"] = rpg["battle_log"][:25]

    return {
        "quest": quest,
        "character": character,
        "daily_boss": rpg["daily_boss"],
        "weekly_boss": rpg["weekly_boss"],
        "daily_result": daily_result,
        "weekly_result": weekly_result,
    }


def clean_hex_color(value: object, default: str) -> str:
    clean = str(value or "").strip().lower()
    if len(clean) != 7 or not clean.startswith("#"):
        return default
    if any(char not in "0123456789abcdef" for char in clean[1:]):
        return default
    return clean


def calculate_avatar_bmi(profile: dict) -> float | None:
    try:
        height_m = float(profile.get("height_cm", 0)) / 100
        weight = float(profile.get("weight_kg", 0))
    except (TypeError, ValueError):
        return None
    if height_m <= 0 or weight <= 0:
        return None
    return round(weight / (height_m * height_m), 1)


def avatar_body_label(profile: dict) -> str:
    muscle = int(profile.get("muscle", 45))
    body_fat = int(profile.get("body_fat", 35))
    waist = int(profile.get("waist_width", 92))
    hips = int(profile.get("hip_width", 98))
    chest = int(profile.get("chest_cm", 96))
    shoulders = int(profile.get("shoulder_width", 100))
    bmi = calculate_avatar_bmi(profile)

    if muscle >= 70 and body_fat <= 45:
        return "athletisch"
    if muscle >= 70:
        return "kraftvoll"
    if shoulders >= 112 and chest >= 104:
        return "breit"
    if hips - waist >= 16:
        return "kurvig"
    if body_fat <= 30 and waist <= 88 and (bmi is None or bmi < 25):
        return "schlank"
    if body_fat >= 60 or (bmi is not None and bmi >= 30):
        return "weich"
    return "ausgeglichen"


def avatar_profile_for_member(state: dict, member_id: str) -> dict:
    member = members_by_id(state).get(member_id)
    if not member:
        raise ValueError("Mitglied wurde nicht gefunden.")

    stored = copy.deepcopy(state.setdefault("avatars", {}).get(member_id, {}))
    profile = copy.deepcopy(AVATAR_DEFAULTS)
    profile.update(stored)
    profile["member_id"] = member_id
    profile["name"] = member["name"]
    profile["bmi"] = calculate_avatar_bmi(profile)
    profile["body_label"] = avatar_body_label(profile)
    profile.setdefault("front_photo_id", "")
    profile.setdefault("side_photo_id", "")
    profile.setdefault("calibration", "Noch nicht kalibriert")
    return profile


def save_avatar_profile(state: dict, payload: dict, photo_ids: dict[str, str] | None = None) -> dict:
    member_id = str(payload.get("member_id") or "")
    members = members_by_id(state)
    if member_id not in members:
        raise ValueError("Mitglied wurde nicht gefunden.")

    existing = state.setdefault("avatars", {}).get(member_id, {})
    photo_ids = photo_ids or {}

    hair_style = str(payload.get("hair_style") or existing.get("hair_style") or AVATAR_DEFAULTS["hair_style"])
    clothing_style = str(payload.get("clothing_style") or existing.get("clothing_style") or AVATAR_DEFAULTS["clothing_style"])
    if hair_style not in AVATAR_HAIR_STYLES:
        raise ValueError("Frisur wurde nicht gefunden.")
    if clothing_style not in AVATAR_CLOTHING_STYLES:
        raise ValueError("Kleidung wurde nicht gefunden.")

    profile = copy.deepcopy(existing) if existing else {}
    profile.update(
        {
            "member_id": member_id,
            "height_cm": clamp(as_int(payload, "height_cm", int(existing.get("height_cm", AVATAR_DEFAULTS["height_cm"]))), 120, 230),
            "weight_kg": clamp(as_int(payload, "weight_kg", int(existing.get("weight_kg", AVATAR_DEFAULTS["weight_kg"]))), 35, 250),
            "neck_cm": clamp(as_int(payload, "neck_cm", int(existing.get("neck_cm", AVATAR_DEFAULTS["neck_cm"]))), 25, 60),
            "shoulder_width": clamp(as_int(payload, "shoulder_width", int(existing.get("shoulder_width", AVATAR_DEFAULTS["shoulder_width"]))), 60, 140),
            "chest_cm": clamp(as_int(payload, "chest_cm", int(existing.get("chest_cm", AVATAR_DEFAULTS["chest_cm"]))), 60, 180),
            "waist_width": clamp(as_int(payload, "waist_width", int(existing.get("waist_width", AVATAR_DEFAULTS["waist_width"]))), 55, 150),
            "hip_width": clamp(as_int(payload, "hip_width", int(existing.get("hip_width", AVATAR_DEFAULTS["hip_width"]))), 60, 150),
            "thigh_left_cm": clamp(as_int(payload, "thigh_left_cm", int(existing.get("thigh_left_cm", AVATAR_DEFAULTS["thigh_left_cm"]))), 35, 100),
            "thigh_right_cm": clamp(as_int(payload, "thigh_right_cm", int(existing.get("thigh_right_cm", AVATAR_DEFAULTS["thigh_right_cm"]))), 35, 100),
            "muscle": clamp(as_int(payload, "muscle", int(existing.get("muscle", AVATAR_DEFAULTS["muscle"]))), 0, 100),
            "body_fat": clamp(as_int(payload, "body_fat", int(existing.get("body_fat", AVATAR_DEFAULTS["body_fat"]))), 0, 100),
            "hair_style": hair_style,
            "clothing_style": clothing_style,
            "skin_color": clean_hex_color(payload.get("skin_color"), str(existing.get("skin_color", AVATAR_DEFAULTS["skin_color"]))),
            "hair_color": clean_hex_color(payload.get("hair_color"), str(existing.get("hair_color", AVATAR_DEFAULTS["hair_color"]))),
            "outfit_color": clean_hex_color(payload.get("outfit_color"), str(existing.get("outfit_color", AVATAR_DEFAULTS["outfit_color"]))),
            "updated_at": today(),
        }
    )
    if not profile.get("created_at"):
        profile["created_at"] = today()
    if photo_ids.get("front_photo_id"):
        profile["front_photo_id"] = photo_ids["front_photo_id"]
    if photo_ids.get("side_photo_id"):
        profile["side_photo_id"] = photo_ids["side_photo_id"]

    references = []
    if profile.get("front_photo_id"):
        references.append("Front")
    if profile.get("side_photo_id"):
        references.append("Seite")
    profile["calibration"] = " + ".join(references) if references else "Manuell"
    profile["bmi"] = calculate_avatar_bmi(profile)
    profile["body_label"] = avatar_body_label(profile)

    state.setdefault("avatars", {})[member_id] = profile
    award_xp(state, member_id, "team", 15)
    return profile


def add_weight_entry(state: dict, payload: dict) -> dict:
    member_id = str(payload.get("member_id") or "")
    if member_id not in members_by_id(state):
        raise ValueError("Mitglied wurde nicht gefunden.")

    weight_kg = as_float(payload, "weight_kg")
    if not 35 <= weight_kg <= 250:
        raise ValueError("Bitte ein plausibles Gewicht zwischen 35 und 250 kg eintragen.")

    entry_date = str(payload.get("entry_date") or today()).strip()
    try:
        date.fromisoformat(entry_date)
    except ValueError as exc:
        raise ValueError("Bitte ein gültiges Datum eintragen.") from exc

    entry = {
        "id": new_id("weight"),
        "member_id": member_id,
        "weight_kg": round(weight_kg, 1),
        "entry_date": entry_date,
        "note": str(payload.get("note") or "").strip(),
        "created_at": today(),
    }
    state.setdefault("weight_entries", []).insert(0, entry)
    award_xp(state, member_id, "team", 6)
    return entry


def weight_entries_for_member(state: dict, member_id: str) -> list[dict]:
    entries = [
        entry
        for entry in state.setdefault("weight_entries", [])
        if entry.get("member_id") == member_id
    ]
    return sorted(entries, key=lambda item: item.get("entry_date", ""), reverse=True)


def latest_weight_for_member(state: dict, member_id: str) -> float | None:
    entries = weight_entries_for_member(state, member_id)
    if entries:
        return float(entries[0]["weight_kg"])
    profile = state.setdefault("profiles", {}).get(member_id)
    if profile and profile.get("weight_kg"):
        return float(profile["weight_kg"])
    return None


def weight_change_for_member(state: dict, member_id: str, days: int = 30) -> float | None:
    entries = weight_entries_for_member(state, member_id)
    if len(entries) < 2:
        return None

    cutoff = date.today() - timedelta(days=days)
    recent = [entry for entry in entries if date.fromisoformat(entry["entry_date"]) >= cutoff]
    if len(recent) < 2:
        return None
    newest = float(recent[0]["weight_kg"])
    oldest = float(recent[-1]["weight_kg"])
    return round(newest - oldest, 1)


def food_items(state: dict) -> list[dict]:
    return sorted(state.setdefault("food_items", copy.deepcopy(DEFAULT_FOOD_ITEMS)), key=lambda item: item["name"])


def meal_ideas(state: dict) -> list[dict]:
    return state.setdefault("meal_ideas", copy.deepcopy(DEFAULT_MEAL_IDEAS))


def food_by_id(state: dict, food_id: str) -> dict | None:
    for food in food_items(state):
        if food["id"] == food_id:
            return food
    return None


def meal_idea_by_id(state: dict, idea_id: str) -> dict | None:
    for idea in meal_ideas(state):
        if idea["id"] == idea_id:
            return idea
    return None


def add_food_item(state: dict, payload: dict) -> dict:
    name = str(payload.get("name") or "").strip()
    if not name:
        raise ValueError("Bitte einen Namen für das Lebensmittel eintragen.")

    category = str(payload.get("category") or "other")
    if category not in FOOD_CATEGORIES:
        raise ValueError("Kategorie wurde nicht gefunden.")

    item = {
        "id": new_id("food"),
        "name": name,
        "category": category,
        "calories": max(0, as_int(payload, "calories", 0)),
        "protein": max(0.0, as_float(payload, "protein", 0.0)),
        "carbs": max(0.0, as_float(payload, "carbs", 0.0)),
        "fat": max(0.0, as_float(payload, "fat", 0.0)),
    }
    state.setdefault("food_items", []).append(item)
    return item


def scaled_food_nutrition(food: dict, grams: float) -> dict[str, float]:
    factor = grams / 100
    return {
        "calories": round(float(food["calories"]) * factor),
        "protein": round(float(food["protein"]) * factor, 1),
        "carbs": round(float(food["carbs"]) * factor, 1),
        "fat": round(float(food["fat"]) * factor, 1),
    }


def normalize_youtube_url(url: str) -> str:
    clean = str(url or "").strip()
    if not clean:
        return ""
    if "youtube.com/watch" not in clean and "youtu.be/" not in clean and "youtube.com/shorts/" not in clean:
        raise ValueError("Bitte einen YouTube-Link eintragen.")
    return clean


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
        raise ValueError("Bitte eine Übung eintragen.")

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
        "youtube_url": normalize_youtube_url(str(payload.get("youtube_url") or "")),
        "created_at": today(),
    }
    state["sport_entries"].insert(0, entry)
    award_xp(state, member_id, sport_type, xp)
    return entry


def add_external_sport_entry(state: dict, payload: dict) -> dict | None:
    source = str(payload.get("external_source") or "").strip()
    external_id = str(payload.get("external_id") or "").strip()
    if not source or not external_id:
        raise ValueError("Externe Aktivität ist unvollständig.")

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

    meal_type = str(payload.get("meal_type") or "snack")
    if meal_type not in MEAL_LABELS:
        raise ValueError("Mahlzeit wurde nicht gefunden.")

    meal = str(payload.get("meal") or "").strip()
    grams = max(1.0, as_float(payload, "grams", 100.0))
    food = food_by_id(state, str(payload.get("food_id") or ""))
    idea = meal_idea_by_id(state, str(payload.get("meal_idea_id") or ""))

    carbs = max(0.0, as_float(payload, "carbs", 0.0)) if payload.get("carbs") else 0.0
    fat = max(0.0, as_float(payload, "fat", 0.0)) if payload.get("fat") else 0.0

    if idea:
        meal_type = idea["meal_type"]
        meal = idea["title"]
        protein = int(idea["protein"])
        calories = int(idea["calories"])
        carbs = float(idea["carbs"])
        fat = float(idea["fat"])
        youtube_url = normalize_youtube_url(str(payload.get("youtube_url") or idea.get("youtube_url") or ""))
    elif food:
        nutrition = scaled_food_nutrition(food, grams)
        meal = meal or food["name"]
        protein = int(round(nutrition["protein"]))
        calories = int(nutrition["calories"])
        carbs = float(nutrition["carbs"])
        fat = float(nutrition["fat"])
        youtube_url = normalize_youtube_url(str(payload.get("youtube_url") or ""))
    else:
        protein = max(0, int(payload.get("protein") or 0))
        calories = max(0, int(payload.get("calories") or 0))
        youtube_url = normalize_youtube_url(str(payload.get("youtube_url") or ""))

    if not meal:
        raise ValueError("Bitte eine Mahlzeit eintragen.")

    water = max(0.0, float(payload.get("water") or 0))
    xp = min(90, 15 + protein + int(water * 10))
    entry = {
        "id": new_id("meal"),
        "member_id": member_id,
        "meal_type": meal_type,
        "meal": meal,
        "protein": protein,
        "calories": calories,
        "carbs": round(carbs, 1),
        "fat": round(fat, 1),
        "water": water,
        "xp": xp,
        "source": "Gericht" if idea else "Lebensmittel" if food else "Manuell",
        "food_id": food["id"] if food else "",
        "meal_idea_id": idea["id"] if idea else "",
        "grams": round(grams, 1) if food else 0,
        "youtube_url": youtube_url,
        "created_at": today(),
    }
    state["nutrition_entries"].insert(0, entry)
    award_xp(state, member_id, "nutrition", xp)
    return entry


def add_youtube_link(state: dict, payload: dict) -> dict:
    context = str(payload.get("context") or "")
    if context not in ("training", "meal"):
        raise ValueError("Video-Bereich wurde nicht gefunden.")

    member_id = str(payload.get("member_id") or "")
    if member_id not in members_by_id(state):
        raise ValueError("Mitglied wurde nicht gefunden.")

    title = str(payload.get("title") or "").strip()
    url = normalize_youtube_url(str(payload.get("youtube_url") or ""))
    if not title:
        raise ValueError("Bitte einen Titel für das Video eintragen.")
    if not url:
        raise ValueError("Bitte einen YouTube-Link eintragen.")

    link = {
        "id": new_id("yt"),
        "member_id": member_id,
        "context": context,
        "title": title,
        "youtube_url": url,
        "note": str(payload.get("note") or "").strip(),
        "created_at": today(),
    }
    state.setdefault("youtube_links", []).insert(0, link)
    award_xp(state, member_id, "team", 5)
    return link


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
            if assignment.get("status") == "done":
                return assignment
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


def groups(state: dict) -> list[dict]:
    return state.setdefault("groups", copy.deepcopy(DEFAULT_STATE["groups"]))


def group_by_id(state: dict, group_id: str) -> dict | None:
    for group in groups(state):
        if group.get("id") == group_id:
            return group
    return None


def group_name(state: dict, group_id: str) -> str:
    if not group_id:
        return "Alle"
    group = group_by_id(state, group_id)
    return str(group.get("name")) if group else "Unbekannte Gruppe"


def groups_for_member(state: dict, member_id: str) -> list[dict]:
    return [group for group in groups(state) if member_id in group.setdefault("members", [])]


def create_group(state: dict, payload: dict) -> dict:
    creator = str(payload.get("created_by") or "")
    if creator not in members_by_id(state):
        raise ValueError("Mitglied wurde nicht gefunden.")

    name = str(payload.get("name") or "").strip()
    if len(name) < 3:
        raise ValueError("Bitte einen Gruppennamen mit mindestens 3 Zeichen eintragen.")

    existing_names = {str(group.get("name", "")).lower() for group in groups(state)}
    if name.lower() in existing_names:
        raise ValueError("Diese Gruppe gibt es bereits.")

    focus = str(payload.get("focus") or "Team")
    group = {
        "id": new_id("group"),
        "name": name,
        "description": str(payload.get("description") or "").strip(),
        "focus": focus.strip() or "Team",
        "members": [creator],
        "created_by": creator,
        "created_at": today(),
    }
    groups(state).insert(0, group)
    award_xp(state, creator, "team", 20)
    return group


def join_group(state: dict, payload: dict) -> dict:
    member_id = str(payload.get("member_id") or "")
    group_id = str(payload.get("group_id") or "")
    if member_id not in members_by_id(state):
        raise ValueError("Mitglied wurde nicht gefunden.")

    group = group_by_id(state, group_id)
    if not group:
        raise ValueError("Gruppe wurde nicht gefunden.")

    members = group.setdefault("members", [])
    if member_id not in members:
        members.append(member_id)
        award_xp(state, member_id, "team", 10)

    for challenge in state.setdefault("challenges", []):
        if challenge.get("group_id") == group_id:
            challenge.setdefault("participants", {}).setdefault(member_id, 0)
    return group


def create_challenge(state: dict, payload: dict) -> dict:
    creator = str(payload.get("created_by") or "")
    if creator not in members_by_id(state):
        raise ValueError("Mitglied wurde nicht gefunden.")

    title = str(payload.get("title") or "").strip()
    if len(title) < 3:
        raise ValueError("Bitte einen Challenge-Titel eintragen.")

    category = str(payload.get("category") or "")
    if category not in ("endurance", "strength", "nutrition", "team"):
        raise ValueError("Kategorie wurde nicht gefunden.")

    group_id = str(payload.get("group_id") or "").strip()
    group = group_by_id(state, group_id) if group_id else None
    if group_id and not group:
        raise ValueError("Gruppe wurde nicht gefunden.")
    if group and creator not in group.setdefault("members", []):
        raise ValueError("Du musst der Gruppe beitreten, bevor du dort eine Challenge erstellst.")

    goal = max(1, as_int(payload, "goal", 10))
    unit = str(payload.get("unit") or "Punkte").strip() or "Punkte"
    xp = clamp(as_int(payload, "xp", 100), 10, 1000)
    member_ids = group.setdefault("members", []) if group else [member["id"] for member in state["members"]]
    challenge = {
        "id": new_id("challenge"),
        "title": title,
        "category": category,
        "group_id": group_id,
        "goal": goal,
        "unit": unit,
        "xp": xp,
        "participants": {member_id: 0 for member_id in member_ids},
        "completed": [],
        "created_by": creator,
        "description": str(payload.get("description") or "").strip(),
        "created_at": today(),
    }
    state.setdefault("challenges", []).insert(0, challenge)
    award_xp(state, creator, "team", 18)
    return challenge


def add_challenge_progress(state: dict, payload: dict) -> dict:
    challenge_id = str(payload.get("challenge_id") or "")
    member_id = str(payload.get("member_id") or "")
    amount = max(1, int(payload.get("amount") or 1))

    if member_id not in members_by_id(state):
        raise ValueError("Mitglied wurde nicht gefunden.")

    for challenge in state["challenges"]:
        if challenge["id"] != challenge_id:
            continue

        group_id = str(challenge.get("group_id") or "")
        if group_id:
            group = group_by_id(state, group_id)
            if group and member_id not in group.setdefault("members", []):
                raise ValueError("Dieses Mitglied ist nicht in der Challenge-Gruppe.")

        participants = challenge.setdefault("participants", {})
        goal = int(challenge["goal"])
        old_progress = min(goal, int(participants.get(member_id, 0)))
        new_progress = min(goal, old_progress + amount)
        actual_delta = max(0, new_progress - old_progress)
        participants[member_id] = new_progress

        category = challenge["category"]
        if actual_delta:
            award_xp(state, member_id, category, actual_delta * 10)

        completed = challenge.setdefault("completed", [])
        if new_progress >= int(challenge["goal"]) and member_id not in completed:
            completed.append(member_id)
            if old_progress < goal:
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
        raise ValueError("Strava-Verbindung konnte nicht bestätigt werden.")
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
        raise ValueError("Strava ist für dieses Mitglied nicht verbunden.")

    for key in ("access_token", "refresh_token", "expires_at"):
        if token_payload.get(key) is not None:
            connection[key] = token_payload[key]


def strava_set_last_sync(state: dict, member_id: str) -> None:
    strava = state.setdefault("integrations", {}).setdefault("strava", {})
    strava.setdefault("last_sync", {})[member_id] = today()
