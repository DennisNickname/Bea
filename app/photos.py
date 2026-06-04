from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import os
import secrets
from pathlib import Path

from app.state import PROJECT_ROOT
from app.state import members_by_id
from app.state import new_id
from app.state import today

PHOTO_ROOT = Path(os.getenv("BEA_PHOTO_PATH", PROJECT_ROOT / "data" / "photos"))
MAX_PHOTO_BYTES = 6 * 1024 * 1024
PIN_ITERATIONS = 160_000

MIME_EXTENSIONS = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}


def photo_pin_is_set(state: dict, member_id: str) -> bool:
    return bool(state.setdefault("photo_access", {}).get(member_id))


def pin_hash(pin: str, salt: str) -> str:
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        pin.encode("utf-8"),
        bytes.fromhex(salt),
        PIN_ITERATIONS,
    )
    return digest.hex()


def set_photo_pin(state: dict, member_id: str, pin: str, current_pin: str = "") -> None:
    if member_id not in members_by_id(state):
        raise ValueError("Mitglied wurde nicht gefunden.")

    if len(pin) < 4:
        raise ValueError("Der Foto-PIN braucht mindestens 4 Zeichen.")

    access = state.setdefault("photo_access", {})
    existing = access.get(member_id)
    if existing and not verify_photo_pin(state, member_id, current_pin):
        raise ValueError("Der aktuelle Foto-PIN stimmt nicht.")

    salt = secrets.token_hex(16)
    access[member_id] = {
        "salt": salt,
        "pin_hash": pin_hash(pin, salt),
        "updated_at": today(),
    }


def verify_photo_pin(state: dict, member_id: str, pin: str) -> bool:
    access = state.setdefault("photo_access", {}).get(member_id)
    if not access:
        return False

    expected = str(access.get("pin_hash") or "")
    salt = str(access.get("salt") or "")
    if not expected or not salt:
        return False

    return hmac.compare_digest(pin_hash(pin, salt), expected)


def require_photo_pin(state: dict, member_id: str, pin: str) -> None:
    if member_id not in members_by_id(state):
        raise ValueError("Mitglied wurde nicht gefunden.")
    if not verify_photo_pin(state, member_id, pin):
        raise ValueError("Foto-PIN ist falsch oder noch nicht eingerichtet.")


def decode_image(data_url: str) -> tuple[str, str, bytes]:
    if not data_url.startswith("data:image/") or ";base64," not in data_url:
        raise ValueError("Bitte ein Bild im Browser auswaehlen.")

    header, encoded = data_url.split(";base64,", 1)
    mime_type = header.replace("data:", "", 1)
    extension = MIME_EXTENSIONS.get(mime_type)
    if not extension:
        raise ValueError("Erlaubt sind JPEG, PNG und WebP.")

    try:
        raw = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("Das Bild konnte nicht gelesen werden.") from exc

    if len(raw) > MAX_PHOTO_BYTES:
        raise ValueError("Das Bild ist groesser als 6 MB.")

    if mime_type == "image/jpeg" and not raw.startswith(b"\xff\xd8"):
        raise ValueError("JPEG-Datei ist ungueltig.")
    if mime_type == "image/png" and not raw.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("PNG-Datei ist ungueltig.")
    if mime_type == "image/webp" and not (raw.startswith(b"RIFF") and raw[8:12] == b"WEBP"):
        raise ValueError("WebP-Datei ist ungueltig.")

    return mime_type, extension, raw


def photo_path(photo: dict) -> Path:
    return PHOTO_ROOT / str(photo["file"])


def photo_data_url(photo: dict) -> str:
    path = photo_path(photo)
    raw = path.read_bytes()
    encoded = base64.b64encode(raw).decode("ascii")
    return f"data:{photo['mime_type']};base64,{encoded}"


def add_private_photo(state: dict, payload: dict) -> dict:
    member_id = str(payload.get("member_id") or "")
    pin = str(payload.get("pin") or "")
    require_photo_pin(state, member_id, pin)

    mime_type, extension, raw = decode_image(str(payload.get("image_data") or ""))
    photo_id = new_id("photo")
    relative = Path("private") / member_id / f"{photo_id}.{extension}"
    target = PHOTO_ROOT / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(raw)

    photo = {
        "id": photo_id,
        "member_id": member_id,
        "title": str(payload.get("title") or "Vergleichsfoto").strip(),
        "photo_type": str(payload.get("photo_type") or "Check-in").strip(),
        "note": str(payload.get("note") or "").strip(),
        "created_at": today(),
        "file": relative.as_posix(),
        "mime_type": mime_type,
        "public": False,
        "published_at": None,
    }
    state.setdefault("photos", []).insert(0, photo)
    return photo


def private_photos_for_member(state: dict, member_id: str, pin: str) -> list[dict]:
    require_photo_pin(state, member_id, pin)
    photos = []
    for photo in state.setdefault("photos", []):
        if photo.get("member_id") == member_id:
            photos.append(photo_response(photo, include_data=True))
    return photos


def public_photos(state: dict) -> list[dict]:
    photos = []
    for photo in state.setdefault("photos", []):
        if photo.get("public"):
            photos.append(photo_response(photo, include_data=True))
    return photos


def publish_photo(state: dict, member_id: str, pin: str, photo_id: str) -> dict:
    require_photo_pin(state, member_id, pin)
    for photo in state.setdefault("photos", []):
        if photo.get("id") == photo_id and photo.get("member_id") == member_id:
            photo["public"] = True
            photo["published_at"] = today()
            return photo
    raise ValueError("Foto wurde nicht gefunden.")


def photo_response(photo: dict, include_data: bool = False) -> dict:
    response = {
        "id": photo["id"],
        "member_id": photo["member_id"],
        "title": photo["title"],
        "photo_type": photo["photo_type"],
        "note": photo["note"],
        "created_at": photo["created_at"],
        "public": bool(photo.get("public")),
        "published_at": photo.get("published_at"),
    }
    if include_data:
        response["image_data"] = photo_data_url(photo)
    return response
