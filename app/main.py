from __future__ import annotations

import html
import ipaddress
import json
import os
import secrets
import shlex
import shutil
import signal
import subprocess
import threading
import time
import urllib.parse
from datetime import date
from datetime import timedelta
from pathlib import Path

from fastapi import FastAPI
from fastapi import HTTPException
from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi.responses import JSONResponse
from fastapi.responses import RedirectResponse

from app.integrations import exchange_strava_code
from app.integrations import fetch_strava_activities
from app.integrations import strava_access_token
from app.integrations import strava_activity_payload
from app.integrations import strava_authorization_url
from app.integrations import strava_is_configured
from app.photos import add_private_photo
from app.photos import photo_pin_is_set
from app.photos import private_photos_for_member
from app.photos import public_photos
from app.photos import publish_photo
from app.photos import require_photo_pin
from app.photos import set_photo_pin
from app.state import ACTIVITY_LABELS
from app.state import ADVENTURE_ROLE_LABELS
from app.state import add_weight_entry
from app.state import AREA_LABELS
from app.state import AREAS
from app.state import BODY_FOCUS_LABELS
from app.state import DIET_LABELS
from app.state import ENDURANCE_LABELS
from app.state import FOOD_CATEGORIES
from app.state import GOAL_METRIC_LABELS
from app.state import GOAL_LABELS
from app.state import HEALTH_JOURNEY_LESSONS
from app.state import INJURY_AREA_LABELS
from app.state import MEAL_LABELS
from app.state import MINDSET_EXERCISES
from app.state import MOTIVATION_STYLE_LABELS
from app.state import RECOVERY_LABELS
from app.state import SLEEP_QUALITY_LABELS
from app.state import STRESS_LABELS
from app.state import TRACKING_FREQUENCY_LABELS
from app.state import TRAINING_FOCUS_LABELS
from app.state import TRAINING_LABELS
from app.state import WORK_STYLE_LABELS
from app.state import add_external_sport_entry
from app.state import add_food_item
from app.state import add_assignment
from app.state import add_challenge_progress
from app.state import add_mindset_entry
from app.state import add_motivation
from app.state import add_nutrition_entry
from app.state import add_sport_entry
from app.state import add_youtube_link
from app.state import complete_assignment
from app.state import complete_daily_quest
from app.state import complete_health_journey_lesson
from app.state import create_challenge
from app.state import create_group
from app.state import create_personal_plan
from app.state import ensure_rpg_state
from app.state import avatar_profile_for_member
from app.state import AVATAR_CLOTHING_STYLES
from app.state import AVATAR_HAIR_STYLES
from app.state import food_items
from app.state import group_name
from app.state import groups
from app.state import groups_for_member
from app.state import health_journey_status
from app.state import join_group
from app.state import latest_weight_for_member
from app.state import leaderboard
from app.state import level_for_xp
from app.state import load_state
from app.state import meal_ideas
from app.state import member_name
from app.state import members_by_id
from app.state import password_is_configured
from app.state import questionnaire_status
from app.state import rpg_character
from app.state import rpg_completion_key
from app.state import save_state
from app.state import save_avatar_profile
from app.state import set_member_password
from app.state import strava_consume_pending
from app.state import strava_get_connection
from app.state import strava_set_connection
from app.state import strava_set_last_sync
from app.state import strava_store_pending
from app.state import strava_update_connection
from app.state import team_totals
from app.state import total_xp
from app.state import update_settings
from app.state import verify_member_password
from app.state import weight_change_for_member
from app.state import weight_entries_for_member
from app.weather import fetch_forecast

app = FastAPI(title="Bea")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SERVICE_NAME = os.getenv("BEA_SERVICE_NAME", "bea.service")
SESSION_COOKIE = "bea_session"
SESSION_TTL_SECONDS = int(os.getenv("BEA_SESSION_TTL_SECONDS", str(12 * 60 * 60)))
SESSIONS: dict[str, dict] = {}

NAV_ITEMS = (
    ("/", "Dashboard"),
    ("/abenteuer", "Abenteuer"),
    ("/reise", "Reise"),
    ("/avatar", "Avatar"),
    ("/fortschritt", "Fortschritt"),
    ("/gruppen", "Gruppen"),
    ("/fragebogen", "Fragebogen"),
    ("/freunde", "Freunde"),
    ("/challenges", "Challenges"),
    ("/fitnessplan", "Fitnessplan"),
    ("/sport", "Sport"),
    ("/mindset", "Mindset"),
    ("/nahrung", "Nahrung"),
    ("/fotos", "Fotos"),
    ("/integrationen", "Integrationen"),
)

NAV_GROUPS = (
    ("Planung", (("/", "Dashboard"), ("/fitnessplan", "Fitnessplan"), ("/fragebogen", "Check-in"))),
    ("Abenteuer", (("/abenteuer", "Abenteuer"), ("/reise", "Reise"), ("/avatar", "Avatar"), ("/fortschritt", "Fortschritt"))),
    ("Community", (("/freunde", "Freunde"), ("/gruppen", "Gruppen"), ("/challenges", "Challenges"))),
    ("Tracking", (("/sport", "Sport"), ("/mindset", "Mindset"), ("/nahrung", "Nahrung"), ("/fotos", "Fotos"), ("/integrationen", "Integrationen"))),
)


def h(value: object) -> str:
    return html.escape(str(value), quote=True)


def parse_form_body(body: bytes) -> dict[str, str]:
    parsed = urllib.parse.parse_qs(body.decode("utf-8"), keep_blank_values=True)
    return {key: values[-1] if values else "" for key, values in parsed.items()}


def safe_next_url(value: str) -> str:
    target = value if value.startswith("/") and not value.startswith("//") else "/"
    return target if not target.startswith(("/login", "/api/login")) else "/"


def create_session(member_id: str) -> str:
    token = secrets.token_urlsafe(32)
    SESSIONS[token] = {
        "member_id": member_id,
        "expires_at": time.time() + SESSION_TTL_SECONDS,
    }
    return token


def current_session(request: Request) -> dict | None:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    session = SESSIONS.get(token)
    if not session:
        return None
    if float(session.get("expires_at", 0)) < time.time():
        SESSIONS.pop(token, None)
        return None
    return session


def current_member_id(request: Request) -> str:
    session = current_session(request)
    return str(session.get("member_id", "")) if session else ""


def cookie_secure(request: Request) -> bool:
    return request.url.scheme == "https" or os.getenv("BEA_SECURE_COOKIE", "").lower() in ("1", "true", "yes")


def set_session_cookie(response: RedirectResponse, request: Request, token: str) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=SESSION_TTL_SECONDS,
        httponly=True,
        secure=cookie_secure(request),
        samesite="strict",
    )


def clear_session_cookie(response: RedirectResponse, request: Request) -> None:
    response.delete_cookie(SESSION_COOKIE, secure=cookie_secure(request), samesite="strict")


def login_redirect_for(request: Request) -> RedirectResponse:
    target = request.url.path
    if request.url.query:
        target = f"{target}?{request.url.query}"
    return RedirectResponse(f"/login?next={urllib.parse.quote(target)}", status_code=303)


def private_network_only() -> bool:
    return os.getenv("BEA_PRIVATE_NETWORK_ONLY", "1").lower() not in ("0", "false", "no", "off")


def request_from_private_network(request: Request) -> bool:
    if not request.client:
        return True
    try:
        address = ipaddress.ip_address(request.client.host)
    except ValueError:
        return False
    return address.is_private or address.is_loopback or address.is_link_local


def _combined_output(result: subprocess.CompletedProcess[str]) -> str:
    output = "\n".join(part for part in (result.stdout, result.stderr) if part)
    return output.strip() or "Kein Output."


def _running_under_systemd() -> bool:
    return any(os.getenv(name) for name in ("INVOCATION_ID", "JOURNAL_STREAM", "SYSTEMD_EXEC_PID"))


def _terminate_self_soon() -> None:
    def terminate() -> None:
        time.sleep(1.5)
        os.kill(os.getpid(), signal.SIGTERM)

    threading.Thread(target=terminate, daemon=True).start()


def _systemctl_restart_command() -> list[str] | None:
    systemctl = shutil.which("systemctl")
    if not systemctl:
        return None

    sudo = shutil.which("sudo")
    if sudo:
        return [sudo, "-n", systemctl, "restart", SERVICE_NAME]
    return [systemctl, "restart", SERVICE_NAME]


def _restart_service_soon() -> str:
    strategy = os.getenv("BEA_RESTART_STRATEGY", "auto").strip().lower()
    if strategy in ("off", "disabled", "none"):
        return "Update geladen. Automatischer Neustart ist deaktiviert."

    if strategy in ("self", "self-terminate", "terminate") or (strategy == "auto" and _running_under_systemd()):
        _terminate_self_soon()
        return "Update geladen. Dienstprozess wird beendet und von systemd neu gestartet."

    def restart_command_soon(command: list[str]) -> None:
        time.sleep(1.5)
        subprocess.Popen(
            command,
            cwd=PROJECT_ROOT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )

    restart_command = os.getenv("BEA_RESTART_COMMAND")
    if restart_command:
        command = shlex.split(restart_command)
    else:
        command = _systemctl_restart_command()

    if command:
        threading.Thread(target=restart_command_soon, args=(command,), daemon=True).start()
        return "Update geladen. Dienstneustart wurde angestossen."

    return "Update geladen. Kein automatischer Neustartmechanismus gefunden."


def area_class(area: str) -> str:
    return {
        "endurance": "area-endurance",
        "strength": "area-strength",
        "nutrition": "area-nutrition",
        "mindset": "area-mindset",
        "team": "area-team",
    }.get(area, "area-team")


def training_type_area(training_type: str) -> str:
    return {
        "Kraft": "strength",
        "Ausdauer": "endurance",
        "Regeneration": "team",
    }.get(training_type, "team")


@app.middleware("http")
async def require_authenticated_member(request: Request, call_next):
    path = request.url.path
    if private_network_only() and not request_from_private_network(request):
        return JSONResponse(
            status_code=403,
            content={"detail": {"message": "Bea ist nur im privaten Netzwerk oder per VPN erreichbar."}},
        )

    public_paths = {"/login", "/api/login", "/logout", "/favicon.ico"}
    if path in public_paths:
        return await call_next(request)

    if current_session(request):
        return await call_next(request)

    if path.startswith("/api") or path == "/update":
        return JSONResponse(
            status_code=401,
            content={"detail": {"message": "Bitte anmelden, bevor Daten gelesen oder geändert werden."}},
        )

    return login_redirect_for(request)


def render_member_options(state: dict, selected: str = "") -> str:
    return "\n".join(
        f'<option value="{h(member["id"])}" {"selected" if member["id"] == selected else ""}>{h(member["name"])}</option>'
        for member in state["members"]
    )


def render_member_options_for_ids(state: dict, member_ids: list[str], selected: str = "") -> str:
    allowed = set(member_ids)
    options = [
        member
        for member in state["members"]
        if not allowed or member["id"] in allowed
    ]
    if not options:
        options = state["members"]
    return "\n".join(
        f'<option value="{h(member["id"])}" {"selected" if member["id"] == selected else ""}>{h(member["name"])}</option>'
        for member in options
    )


def render_category_options(selected: str = "strength") -> str:
    return "\n".join(
        f'<option value="{h(area)}" {"selected" if area == selected else ""}>{h(AREA_LABELS[area])}</option>'
        for area in ("strength", "endurance", "nutrition")
    )


def render_group_options(state: dict, selected: str = "", include_all: bool = True) -> str:
    options = ['<option value="">Alle Mitglieder</option>'] if include_all else []
    options.extend(
        f'<option value="{h(group["id"])}" {"selected" if group["id"] == selected else ""}>{h(group["name"])}</option>'
        for group in groups(state)
    )
    return "\n".join(options)


def render_options(options: dict[str, str], selected: str = "") -> str:
    return "\n".join(
        f'<option value="{h(value)}" {"selected" if value == selected else ""}>{h(label)}</option>'
        for value, label in options.items()
    )


def render_checkbox_options(options: dict[str, str], name: str, selected: tuple[str, ...] = ()) -> str:
    selected_values = set(selected)
    return "\n".join(
        f"""
        <label class="choice-option">
          <input type="checkbox" name="{h(name)}" value="{h(value)}" {"checked" if value in selected_values else ""}>
          <span>{h(label)}</span>
        </label>
        """
        for value, label in options.items()
    )


def render_food_options(state: dict) -> str:
    return '<option value="">Manuell eintragen</option>' + "\n".join(
        f'<option value="{h(item["id"])}">{h(item["name"])} - {h(item["calories"])} kcal / 100g</option>'
        for item in food_items(state)
    )


def render_meal_idea_options(state: dict) -> str:
    return '<option value="">Kein Gericht</option>' + "\n".join(
        f'<option value="{h(item["id"])}">{h(MEAL_LABELS[item["meal_type"]])}: {h(item["title"])} - {h(item["calories"])} kcal</option>'
        for item in meal_ideas(state)
    )


def youtube_embed_url(url: str) -> str:
    parsed = urllib.parse.urlparse(str(url or ""))
    host = parsed.netloc.lower().replace("www.", "")
    video_id = ""
    if host == "youtu.be":
        video_id = parsed.path.strip("/").split("/")[0]
    elif host in ("youtube.com", "m.youtube.com"):
        if parsed.path == "/watch":
            video_id = urllib.parse.parse_qs(parsed.query).get("v", [""])[0]
        elif parsed.path.startswith("/shorts/"):
            video_id = parsed.path.split("/")[2]
        elif parsed.path.startswith("/embed/"):
            video_id = parsed.path.split("/")[2]
    if not video_id:
        return ""
    return f"https://www.youtube-nocookie.com/embed/{h(video_id)}"


def render_video_card(title: str, url: str, note: str = "") -> str:
    embed = youtube_embed_url(url)
    if not embed:
        return ""
    return f"""
      <article class="card">
        <div class="video-frame">
          <iframe src="{embed}" title="{h(title)}" loading="lazy" allowfullscreen></iframe>
        </div>
        <h3>{h(title)}</h3>
        <p class="subtle">{h(note)}</p>
      </article>
    """


def render_youtube_links(state: dict, context: str) -> str:
    cards = []
    for link in state.get("youtube_links", []):
        if link.get("context") == context:
            cards.append(render_video_card(link["title"], link["youtube_url"], link.get("note", "")))

    if context == "training":
        for entry in state.get("sport_entries", []):
            if entry.get("youtube_url"):
                cards.append(render_video_card(entry["title"], entry["youtube_url"], f'{member_name(state, entry["member_id"])} - {entry["created_at"]}'))
    else:
        for entry in state.get("nutrition_entries", []):
            if entry.get("youtube_url"):
                cards.append(render_video_card(entry["meal"], entry["youtube_url"], f'{member_name(state, entry["member_id"])} - {entry["created_at"]}'))

    if not cards:
        return '<article class="card"><p class="subtle">Noch keine YouTube-Videos angehängt.</p></article>'
    return "".join(cards[:6])


def progress_bar(progress: int, label: str = "") -> str:
    safe_progress = min(100, max(0, int(progress)))
    return f"""
      <div class="progress" aria-label="{h(label)}">
        <span style="width: {safe_progress}%"></span>
      </div>
    """


def level_meter(label: str, xp: int, area: str) -> str:
    level = level_for_xp(xp)
    return f"""
      <article class="level-meter {area_class(area)}">
        <div>
          <p>{h(label)}</p>
          <strong>Level {level["level"]}</strong>
        </div>
        {progress_bar(level["progress"], f'{label} Fortschritt')}
        <small>{xp} XP / nächstes Level bei {level["next_xp"]} XP</small>
      </article>
    """


def render_layout(active_path: str, title: str, body: str) -> str:
    nav = "\n".join(
        f"""
        <section class="nav-group">
          <h2>{h(group_label)}</h2>
          <div class="nav-links">
            {"".join(
                f'<a class="{"is-active" if path == active_path else ""}" href="{path}">{label}</a>'
                for path, label in items
            )}
          </div>
        </section>
        """
        for group_label, items in NAV_GROUPS
    )
    return f"""
    <!doctype html>
    <html lang="de">
      <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>{h(title)} · Bea</title>
        <style>
          :root {{
            color-scheme: light;
            font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            --ink: #172033;
            --muted: #667085;
            --line: #d8e0ea;
            --surface: #ffffff;
            --surface-soft: #fff8ec;
            --page: #f7f4ed;
            --green: #168a5f;
            --blue: #2563eb;
            --red: #df3f58;
            --gold: #d98b13;
            --violet: #7c3aed;
            --cyan: #0891b2;
            --mindset: #8b5cf6;
            --shadow: 0 1rem 2.8rem rgb(23 32 51 / 10%);
          }}

          * {{
            box-sizing: border-box;
          }}

          body {{
            margin: 0;
            min-height: 100vh;
            overflow-x: hidden;
            background:
              linear-gradient(120deg, rgb(37 99 235 / 13%), transparent 26rem),
              linear-gradient(245deg, rgb(22 138 95 / 14%), transparent 28rem),
              linear-gradient(0deg, rgb(217 139 19 / 10%), transparent 18rem),
              repeating-linear-gradient(90deg, rgb(255 255 255 / 38%) 0 1px, transparent 1px 5rem),
              var(--page);
            color: var(--ink);
          }}

          a {{
            color: inherit;
            text-decoration: none;
          }}

          button,
          input,
          select,
          textarea {{
            font: inherit;
          }}

          .app-shell {{
            display: grid;
            grid-template-columns: minmax(13.75rem, 15rem) minmax(0, 1fr);
            min-height: 100vh;
          }}

          .sidebar {{
            position: sticky;
            top: 0;
            z-index: 6;
            display: flex;
            height: 100vh;
            min-width: 0;
            flex-direction: column;
            gap: 1rem;
            overflow-y: auto;
            border-right: 1px solid var(--line);
            padding: 1rem;
            background: rgb(255 255 255 / 90%);
            backdrop-filter: blur(18px);
            box-shadow: 0 0.4rem 1.6rem rgb(23 32 51 / 8%);
          }}

          .sidebar::before {{
            position: absolute;
            top: 0;
            left: 0;
            width: 0.32rem;
            height: 100%;
            content: "";
            background: linear-gradient(180deg, var(--blue), var(--green), var(--gold), var(--red), var(--violet));
          }}

          .brand {{
            display: flex;
            align-items: center;
            gap: 0.65rem;
            font-weight: 850;
            letter-spacing: 0;
          }}

          .brand-mark {{
            display: grid;
            width: 2.55rem;
            height: 2.55rem;
            place-items: center;
            border-radius: 0.45rem;
            background: #000000;
            color: #fff;
            box-shadow: 0 0.7rem 1.4rem rgb(23 32 51 / 20%);
          }}

          .side-nav {{
            display: grid;
            gap: 0.95rem;
            min-width: 0;
          }}

          .nav-group {{
            display: grid;
            gap: 0.4rem;
            min-width: 0;
          }}

          .nav-group h2 {{
            margin: 0;
            color: var(--muted);
            font-size: 0.75rem;
            font-weight: 900;
            letter-spacing: 0;
            text-transform: uppercase;
          }}

          .nav-links {{
            display: grid;
            gap: 0.35rem;
            min-width: 0;
          }}

          .nav-links a {{
            display: flex;
            min-height: 2.45rem;
            min-width: 0;
            align-items: center;
            border-radius: 0.45rem;
            padding: 0.62rem 0.75rem;
            background: rgb(255 255 255 / 62%);
            color: var(--muted);
            font-weight: 700;
            overflow-wrap: anywhere;
            box-shadow: inset 0 0 0 1px rgb(216 224 234 / 75%);
            transition: color 150ms ease, background 150ms ease, transform 150ms ease, box-shadow 150ms ease;
          }}

          .nav-links a:hover {{
            color: var(--ink);
            transform: translateX(2px);
            box-shadow: inset 0 0 0 1px rgb(37 99 235 / 32%), 0 0.45rem 1rem rgb(23 32 51 / 8%);
          }}

          .nav-links a.is-active {{
            background: linear-gradient(135deg, var(--ink), #31436a);
            color: #fff;
            box-shadow: 0 0.65rem 1.4rem rgb(23 32 51 / 18%);
          }}

          .update-form {{
            margin: 0;
          }}

          .topbar-actions {{
            display: grid;
            gap: 0.45rem;
            justify-items: stretch;
            margin-top: auto;
          }}

          .sidebar .button,
          .sidebar .update-button {{
            width: 100%;
          }}

          .button,
          .update-button {{
            border: 0;
            border-radius: 0.5rem;
            padding: 0.72rem 0.95rem;
            background: linear-gradient(135deg, var(--green), #11a87b);
            color: #ffffff;
            font-weight: 800;
            cursor: pointer;
            box-shadow: 0 0.7rem 1.4rem rgb(22 138 95 / 22%);
            transition: transform 150ms ease, filter 150ms ease, box-shadow 150ms ease;
          }}

          .button:hover,
          .update-button:hover {{
            filter: saturate(1.08) brightness(1.02);
            transform: translateY(-1px);
          }}

          .button.secondary {{
            background: #eef4f0;
            color: var(--ink);
            box-shadow: inset 0 0 0 1px rgb(22 138 95 / 16%);
          }}

          .button.blue {{
            background: linear-gradient(135deg, var(--blue), var(--cyan));
            box-shadow: 0 0.7rem 1.4rem rgb(37 99 235 / 22%);
          }}

          .button.red {{
            background: linear-gradient(135deg, var(--red), #fb7185);
            box-shadow: 0 0.7rem 1.4rem rgb(223 63 88 / 22%);
          }}

          .button.disco {{
            background: linear-gradient(135deg, var(--violet), #ec4899);
            box-shadow: 0 0.7rem 1.4rem rgb(124 58 237 / 22%);
          }}

          .button.disco-stop {{
            background: linear-gradient(135deg, #31414f, #64748b);
            box-shadow: 0 0.7rem 1.4rem rgb(49 65 79 / 18%);
          }}

          .button:disabled,
          .update-button:disabled {{
            cursor: wait;
            opacity: 0.7;
          }}

          .content-shell {{
            min-width: 0;
          }}

          .page {{
            width: min(100%, 1220px);
            margin: 0 auto;
            box-sizing: border-box;
            padding: 1.5rem clamp(1rem, 3vw, 2.5rem) 3.25rem;
          }}

          .page-heading {{
            position: relative;
            display: grid;
            grid-template-columns: minmax(0, 1fr) auto;
            gap: 1rem;
            align-items: end;
            margin: 0.35rem 0 1.15rem;
            padding: 1.1rem 0 0.2rem;
          }}

          .page-heading::after {{
            position: absolute;
            bottom: -0.35rem;
            left: 0;
            width: min(18rem, 48vw);
            height: 0.32rem;
            border-radius: 999px;
            content: "";
            background: linear-gradient(90deg, var(--blue), var(--green), var(--gold), var(--red));
          }}

          .quick-actions {{
            display: flex;
            max-width: 35rem;
            flex-wrap: wrap;
            gap: 0.55rem;
            justify-content: flex-end;
          }}

          .quick-link {{
            display: inline-flex;
            min-height: 2.65rem;
            align-items: center;
            border-radius: 0.5rem;
            padding: 0.65rem 0.8rem;
            background: rgb(255 255 255 / 82%);
            color: var(--ink);
            font-weight: 850;
            box-shadow: inset 0 0 0 1px rgb(216 224 234 / 82%), 0 0.55rem 1.25rem rgb(23 32 51 / 8%);
            transition: transform 150ms ease, box-shadow 150ms ease;
          }}

          .quick-link:hover {{
            transform: translateY(-1px);
            box-shadow: inset 0 0 0 1px rgb(37 99 235 / 24%), 0 0.8rem 1.5rem rgb(23 32 51 / 12%);
          }}

          .quick-link.blue {{
            color: var(--blue);
          }}

          .quick-link.green {{
            color: var(--green);
          }}

          .quick-link.red {{
            color: var(--red);
          }}

          .quick-link.gold {{
            color: var(--gold);
          }}

          .eyebrow {{
            margin: 0 0 0.35rem;
            color: var(--muted);
            font-size: 0.82rem;
            font-weight: 850;
            letter-spacing: 0;
            text-transform: uppercase;
          }}

          h1,
          h2,
          h3,
          p {{
            margin-top: 0;
          }}

          h1 {{
            margin-bottom: 0;
            font-size: 4rem;
            line-height: 1;
            letter-spacing: 0;
          }}

          h2 {{
            margin-bottom: 0.8rem;
            font-size: 1.35rem;
            letter-spacing: 0;
          }}

          h3 {{
            margin-bottom: 0.4rem;
            font-size: 1rem;
            letter-spacing: 0;
          }}

          .subtle {{
            margin-bottom: 0;
            color: var(--muted);
          }}

          .grid {{
            display: grid;
            gap: 1rem;
          }}

          .grid.two {{
            grid-template-columns: repeat(2, minmax(0, 1fr));
          }}

          .grid.three {{
            grid-template-columns: repeat(3, minmax(0, 1fr));
          }}

          .grid.four {{
            grid-template-columns: repeat(4, minmax(0, 1fr));
          }}

          .panel,
          .card,
          .stat-card,
          .level-meter {{
            border: 1px solid rgb(216 224 234 / 88%);
            border-radius: 0.5rem;
            background: rgb(255 255 255 / 90%);
            box-shadow: var(--shadow);
          }}

          .panel {{
            position: relative;
            overflow: hidden;
            padding: 1.05rem;
          }}

          .panel::before {{
            display: block;
            height: 0.25rem;
            margin: -1.05rem -1.05rem 1rem;
            content: "";
            background: linear-gradient(90deg, var(--blue), var(--green), var(--gold));
          }}

          .card {{
            position: relative;
            padding: 0.98rem;
            transition: transform 150ms ease, box-shadow 150ms ease;
          }}

          .card:hover {{
            transform: translateY(-2px);
            box-shadow: 0 1.1rem 2.4rem rgb(23 32 51 / 13%);
          }}

          .card.area-endurance,
          .level-meter.area-endurance {{
            background: linear-gradient(135deg, #ffffff, #eef6ff);
            border-color: rgb(37 99 235 / 24%);
          }}

          .card.area-strength,
          .level-meter.area-strength {{
            background: linear-gradient(135deg, #ffffff, #fff1f3);
            border-color: rgb(223 63 88 / 24%);
          }}

          .card.area-nutrition,
          .level-meter.area-nutrition {{
            background: linear-gradient(135deg, #ffffff, #eefcf5);
            border-color: rgb(22 138 95 / 24%);
          }}

          .card.area-mindset,
          .level-meter.area-mindset {{
            background: linear-gradient(135deg, #ffffff, #f4f0ff);
            border-color: rgb(139 92 246 / 25%);
          }}

          .card.area-team,
          .level-meter.area-team {{
            background: linear-gradient(135deg, #ffffff, #fff8e8);
            border-color: rgb(217 139 19 / 28%);
          }}

          .character-card {{
            display: grid;
            grid-template-columns: auto minmax(0, 1fr);
            gap: 0.85rem;
            align-items: center;
          }}

          .character-avatar {{
            display: grid;
            width: 3.4rem;
            height: 3.4rem;
            place-items: center;
            border-radius: 0.5rem;
            background: linear-gradient(135deg, var(--ink), var(--violet));
            color: #fff;
            font-size: 1.45rem;
            font-weight: 900;
            box-shadow: 0 0.7rem 1.4rem rgb(23 32 51 / 18%);
          }}

          .avatar-stage {{
            display: grid;
            min-height: 28rem;
            place-items: center;
            border: 1px solid rgb(216 224 234 / 82%);
            border-radius: 0.5rem;
            padding: 1rem;
            background:
              linear-gradient(180deg, rgb(255 255 255 / 72%), rgb(255 248 236 / 76%)),
              repeating-linear-gradient(90deg, rgb(37 99 235 / 8%) 0 1px, transparent 1px 3rem);
          }}

          .avatar-svg {{
            width: min(100%, 18rem);
            height: auto;
            filter: drop-shadow(0 1rem 1.4rem rgb(23 32 51 / 14%));
          }}

          .avatar-card {{
            display: grid;
            gap: 0.85rem;
          }}

          .avatar-meta {{
            display: flex;
            flex-wrap: wrap;
            gap: 0.5rem;
          }}

          .swatch-row {{
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 0.75rem;
          }}

          input[type="color"] {{
            height: 2.8rem;
            padding: 0.2rem;
          }}

          input[type="range"] {{
            accent-color: var(--blue);
          }}

          .boss-card {{
            overflow: hidden;
            border-color: rgb(124 58 237 / 28%);
            background:
              linear-gradient(135deg, rgb(124 58 237 / 10%), transparent 18rem),
              linear-gradient(315deg, rgb(223 63 88 / 10%), transparent 16rem),
              rgb(255 255 255 / 92%);
          }}

          .boss-card.is-defeated {{
            border-color: rgb(22 138 95 / 32%);
            background: linear-gradient(135deg, #ffffff, #ecfdf3);
          }}

          .boss-hp .progress span {{
            background: linear-gradient(90deg, var(--red), var(--violet));
          }}

          .boss-card.is-defeated .boss-hp .progress span {{
            background: linear-gradient(90deg, var(--green), var(--cyan));
          }}

          .stat-card {{
            position: relative;
            overflow: hidden;
            padding: 1rem;
            background: linear-gradient(135deg, #ffffff 0%, var(--surface-soft) 100%);
          }}

          .stat-card::before {{
            display: block;
            height: 0.28rem;
            margin: -1rem -1rem 0.85rem;
            content: "";
            background: linear-gradient(90deg, var(--blue), var(--green));
          }}

          .stat-card:nth-child(2n)::before {{
            background: linear-gradient(90deg, var(--green), var(--gold));
          }}

          .stat-card:nth-child(3n)::before {{
            background: linear-gradient(90deg, var(--red), var(--violet));
          }}

          .stat-card strong {{
            display: block;
            font-size: 2rem;
            line-height: 1;
          }}

          .mini-metric {{
            border-radius: 0.5rem;
            padding: 0.8rem;
            background: rgb(255 255 255 / 72%);
            box-shadow: inset 0 0 0 1px rgb(216 224 234 / 76%);
          }}

          .mini-metric strong {{
            display: block;
            font-size: 1.45rem;
            line-height: 1;
          }}

          .stat-card span,
          .mini-metric span,
          .level-meter small,
          .meta {{
            color: var(--muted);
            font-size: 0.9rem;
          }}

          .level-meter {{
            display: grid;
            gap: 0.65rem;
            padding: 1rem;
            background: linear-gradient(135deg, #ffffff, #f8fbff);
          }}

          .level-meter > div {{
            display: flex;
            justify-content: space-between;
            gap: 1rem;
          }}

          .level-meter p {{
            margin-bottom: 0;
            color: var(--muted);
            font-weight: 750;
          }}

          .progress {{
            height: 0.72rem;
            overflow: hidden;
            border-radius: 999px;
            background: #e7edf3;
          }}

          .progress span {{
            display: block;
            height: 100%;
            border-radius: inherit;
            background: linear-gradient(90deg, var(--green), var(--cyan));
          }}

          .area-endurance .progress span,
          .tag.area-endurance {{
            background: var(--blue);
          }}

          .area-strength .progress span,
          .tag.area-strength {{
            background: var(--red);
          }}

          .area-nutrition .progress span,
          .tag.area-nutrition {{
            background: var(--green);
          }}

          .area-mindset .progress span,
          .tag.area-mindset {{
            background: var(--mindset);
          }}

          .area-team .progress span,
          .tag.area-team {{
            background: var(--gold);
          }}

          .tag {{
            display: inline-flex;
            align-items: center;
            min-height: 1.75rem;
            border-radius: 0.4rem;
            padding: 0.28rem 0.55rem;
            color: #fff;
            font-size: 0.78rem;
            font-weight: 850;
            box-shadow: 0 0.45rem 0.9rem rgb(23 32 51 / 12%);
          }}

          .recommendation {{
            display: inline-flex;
            align-items: center;
            min-height: 2rem;
            border-radius: 0.45rem;
            padding: 0.35rem 0.6rem;
            color: #fff;
            font-size: 0.85rem;
            font-weight: 850;
          }}

          .recommendation.outdoor {{
            background: var(--green);
          }}

          .recommendation.studio {{
            background: var(--red);
          }}

          .integration-status {{
            display: inline-flex;
            align-items: center;
            min-height: 2rem;
            border-radius: 0.45rem;
            padding: 0.35rem 0.6rem;
            background: #e7ecea;
            color: var(--ink);
            font-size: 0.85rem;
            font-weight: 850;
          }}

          .integration-status.connected {{
            background: rgb(31 92 77 / 12%);
            color: var(--green);
          }}

          .integration-status.missing {{
            background: rgb(163 58 58 / 12%);
            color: var(--red);
          }}

          .list {{
            display: grid;
            gap: 0.75rem;
          }}

          .row {{
            display: flex;
            gap: 0.75rem;
            align-items: center;
            justify-content: space-between;
            flex-wrap: wrap;
          }}

          .member-rank {{
            display: grid;
            grid-template-columns: 2rem minmax(0, 1fr) auto;
            gap: 0.85rem;
            align-items: center;
            padding: 0.75rem 0;
            border-bottom: 1px solid var(--line);
          }}

          .member-rank:last-child {{
            border-bottom: 0;
          }}

          .rank-number {{
            display: grid;
            width: 2rem;
            height: 2rem;
            place-items: center;
            border-radius: 0.4rem;
            background: #eef2f0;
            color: var(--muted);
            font-weight: 850;
          }}

          .member-rank:nth-child(1) .rank-number {{
            background: var(--gold);
            color: #fff;
          }}

          .member-rank:nth-child(2) .rank-number {{
            background: var(--blue);
            color: #fff;
          }}

          .member-rank:nth-child(3) .rank-number {{
            background: var(--green);
            color: #fff;
          }}

          .form-grid {{
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 0.75rem;
          }}

          .form-grid .full {{
            grid-column: 1 / -1;
          }}

          .form-section-title {{
            grid-column: 1 / -1;
            margin-top: 0.35rem;
            padding-top: 0.65rem;
            border-top: 1px solid var(--line);
          }}

          .form-section-title h3 {{
            margin-bottom: 0.25rem;
          }}

          .choice-grid {{
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 0.55rem;
          }}

          .choice-option {{
            display: flex;
            align-items: center;
            gap: 0.5rem;
            min-height: 2.65rem;
            border: 1px solid var(--line);
            border-radius: 0.5rem;
            padding: 0.55rem 0.65rem;
            background: rgb(255 255 255 / 72%);
            color: var(--ink);
            font-size: 0.86rem;
          }}

          .choice-option input {{
            width: auto;
            accent-color: var(--blue);
          }}

          label {{
            display: grid;
            gap: 0.35rem;
            color: var(--muted);
            font-size: 0.86rem;
            font-weight: 800;
          }}

          input,
          select,
          textarea {{
            width: 100%;
            border: 1px solid var(--line);
            border-radius: 0.45rem;
            padding: 0.72rem 0.75rem;
            background: rgb(255 255 255 / 94%);
            color: var(--ink);
            box-shadow: inset 0 1px 0 rgb(255 255 255 / 80%);
          }}

          input:focus,
          select:focus,
          textarea:focus {{
            border-color: var(--blue);
            outline: 3px solid rgb(37 99 235 / 16%);
          }}

          textarea {{
            min-height: 5.5rem;
            resize: vertical;
          }}

          .exercise-list {{
            display: grid;
            gap: 0.7rem;
            margin-top: 0.85rem;
          }}

          .exercise-item {{
            border-top: 1px solid var(--line);
            padding-top: 0.7rem;
          }}

          .exercise-item:first-child {{
            border-top: 0;
            padding-top: 0;
          }}

          .exercise-item .meta {{
            display: block;
            margin-bottom: 0.35rem;
          }}

          .cue-list {{
            margin: 0.45rem 0 0;
            padding-left: 1.1rem;
            color: var(--muted);
          }}

          table {{
            width: 100%;
            overflow: hidden;
            border-collapse: collapse;
            border-radius: 0.5rem;
          }}

          th,
          td {{
            padding: 0.75rem 0.5rem;
            border-bottom: 1px solid var(--line);
            text-align: left;
            vertical-align: top;
          }}

          th {{
            background: #f2f6fb;
            color: var(--muted);
            font-size: 0.78rem;
            text-transform: uppercase;
          }}

          tbody tr:nth-child(even) {{
            background: rgb(247 250 252 / 72%);
          }}

          .photo-grid {{
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 1rem;
          }}

          .photo-card {{
            overflow: hidden;
            border: 1px solid var(--line);
            border-radius: 0.5rem;
            background: #fff;
          }}

          .photo-frame {{
            aspect-ratio: 4 / 5;
            overflow: hidden;
            background: #e7ecea;
          }}

          .photo-frame img {{
            display: block;
            width: 100%;
            height: 100%;
            object-fit: cover;
          }}

          .photo-body {{
            display: grid;
            gap: 0.55rem;
            padding: 0.85rem;
          }}

          .compare-board {{
            display: none;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 1rem;
            margin-top: 1rem;
          }}

          .compare-board.is-visible {{
            display: grid;
          }}

          .compare-board img {{
            display: block;
            width: 100%;
            aspect-ratio: 4 / 5;
            border-radius: 0.5rem;
            object-fit: cover;
            background: #e7ecea;
          }}

          .video-frame {{
            aspect-ratio: 16 / 9;
            overflow: hidden;
            border-radius: 0.5rem;
            background: #17212b;
          }}

          .video-frame iframe {{
            width: 100%;
            height: 100%;
            border: 0;
          }}

          .update-status {{
            position: fixed;
            right: 1rem;
            bottom: 1rem;
            z-index: 10;
            max-width: min(26rem, calc(100vw - 2rem));
            border-radius: 0.5rem;
            padding: 0.85rem 1rem;
            background: var(--ink);
            color: #ffffff;
            font-size: 0.95rem;
            line-height: 1.4;
            opacity: 0;
            transform: translateY(0.5rem);
            transition: opacity 160ms ease, transform 160ms ease;
            pointer-events: none;
          }}

          .site-footer {{
            display: flex;
            width: min(100%, 1220px);
            margin: 0 auto 2rem;
            box-sizing: border-box;
            flex-wrap: wrap;
            gap: 0.75rem;
            align-items: center;
            justify-content: space-between;
            border-top: 1px solid rgb(216 224 234 / 75%);
            padding: 1rem clamp(1rem, 3vw, 2.5rem) 0;
            color: var(--muted);
            font-size: 0.9rem;
          }}

          .site-footer a {{
            color: var(--ink);
            font-weight: 850;
          }}

          .site-footer a:hover {{
            color: var(--blue);
          }}

          .update-status.is-visible {{
            opacity: 1;
            transform: translateY(0);
          }}

          @media (max-width: 840px) {{
            .app-shell {{
              grid-template-columns: 1fr;
            }}

            .sidebar {{
              position: relative;
              height: auto;
              border-right: 0;
              border-bottom: 1px solid var(--line);
            }}

            .sidebar::before {{
              width: 100%;
              height: 0.28rem;
              background: linear-gradient(90deg, var(--blue), var(--green), var(--gold), var(--red), var(--violet));
            }}

            .page-heading {{
              grid-template-columns: 1fr;
              align-items: start;
            }}

            .side-nav {{
              grid-template-columns: repeat(2, minmax(0, 1fr));
            }}

            .quick-actions {{
              justify-content: flex-start;
            }}

            h1 {{
              font-size: 2.55rem;
            }}

            .grid.two,
            .grid.three,
            .grid.four,
            .form-grid,
            .choice-grid,
            .photo-grid,
            .compare-board {{
              grid-template-columns: 1fr;
            }}
          }}

          @media (max-width: 560px) {{
            .side-nav {{
              grid-template-columns: 1fr;
            }}
          }}
        </style>
      </head>
      <body>
        <div class="app-shell">
          <aside class="sidebar">
            <a class="brand" href="/" aria-label="Bea Dashboard">
              <span class="brand-mark">B</span>
              <span>ea</span>
            </a>
            <nav class="side-nav" aria-label="Hauptnavigation">
              {nav}
            </nav>
            <div class="topbar-actions">
              <form class="update-form" id="update-form">
                <button class="update-button" id="update-button" type="submit">GitHub Update</button>
              </form>
              <button class="button disco" id="disco-start" type="button">Disco Start</button>
              <button class="button disco-stop" id="disco-stop" type="button">Disco Ende</button>
              <form method="post" action="/logout">
                <button class="button secondary" type="submit">Abmelden</button>
              </form>
            </div>
          </aside>
          <div class="content-shell">
            <main class="page">
              {body}
            </main>
            <footer class="site-footer">
              <span>Bea Fitness Community</span>
              <a href="/impressum">Impressum</a>
            </footer>
          </div>
        </div>
        <p class="update-status" id="update-status" role="status" aria-live="polite"></p>
        <script>
          const statusBox = document.querySelector("#update-status");

          function showStatus(message) {{
            statusBox.textContent = message;
            statusBox.classList.add("is-visible");
            window.clearTimeout(window.__beaStatusTimer);
            window.__beaStatusTimer = window.setTimeout(() => {{
              statusBox.classList.remove("is-visible");
            }}, 4500);
          }}

          async function postJson(endpoint, payload) {{
            const response = await fetch(endpoint, {{
              method: "POST",
              headers: {{ "Content-Type": "application/json" }},
              body: JSON.stringify(payload),
            }});
            const data = await response.json();
            if (!response.ok) {{
              const detail = data.detail || {{}};
              throw new Error(detail.message || data.message || "Aktion fehlgeschlagen.");
            }}
            return data;
          }}

          function payloadFromForm(form) {{
            const payload = {{}};
            new FormData(form).forEach((value, key) => {{
              if (Object.prototype.hasOwnProperty.call(payload, key)) {{
                if (Array.isArray(payload[key])) {{
                  payload[key].push(value);
                }} else {{
                  payload[key] = [payload[key], value];
                }}
              }} else {{
                payload[key] = value;
              }}
            }});
            return payload;
          }}

          document.querySelectorAll("[data-api-form]").forEach((form) => {{
            form.addEventListener("submit", async (event) => {{
              event.preventDefault();
              const button = form.querySelector("button[type='submit']");
              if (button) {{
                button.disabled = true;
              }}
              try {{
                const payload = payloadFromForm(form);
                const data = await postJson(form.dataset.endpoint, payload);
                showStatus(data.message || "Gespeichert.");
                window.setTimeout(() => window.location.reload(), 650);
              }} catch (error) {{
                showStatus(error.message || "Aktion fehlgeschlagen.");
                if (button) {{
                  button.disabled = false;
                }}
              }}
            }});
          }});

          function escapeHtml(value) {{
            return String(value || "")
              .replaceAll("&", "&amp;")
              .replaceAll("<", "&lt;")
              .replaceAll(">", "&gt;")
              .replaceAll('"', "&quot;")
              .replaceAll("'", "&#039;");
          }}

          function readFileAsDataUrl(file) {{
            return new Promise((resolve, reject) => {{
              const reader = new FileReader();
              reader.addEventListener("load", () => resolve(reader.result));
              reader.addEventListener("error", () => reject(new Error("Bild konnte nicht gelesen werden.")));
              reader.readAsDataURL(file);
            }});
          }}

          function renderPhotoGallery(photos, memberId, pin) {{
            const gallery = document.querySelector("#private-photo-gallery");
            if (!gallery) {{
              return;
            }}
            window.__beaPrivatePhotos = photos;
            if (!photos.length) {{
              gallery.innerHTML = '<article class="card"><p class="subtle">Noch keine privaten Vergleichsfotos vorhanden.</p></article>';
              return;
            }}

            gallery.innerHTML = photos.map((photo) => `
              <article class="photo-card">
                <div class="photo-frame">
                  <img src="${{photo.image_data}}" alt="${{escapeHtml(photo.title)}}">
                </div>
                <div class="photo-body">
                  <div class="row">
                    <strong>${{escapeHtml(photo.title)}}</strong>
                    <span class="tag area-team">${{photo.public ? "Community" : "Privat"}}</span>
                  </div>
                  <p class="subtle">${{escapeHtml(photo.photo_type)}} · ${{escapeHtml(photo.created_at)}}</p>
                  <p class="subtle">${{escapeHtml(photo.note)}}</p>
                  <label>
                    <input class="photo-compare" type="checkbox" value="${{photo.id}}">
                    Vergleichen
                  </label>
                  <button class="button secondary" type="button" data-publish-photo="${{photo.id}}">In Community veröffentlichen</button>
                </div>
              </article>
            `).join("");

            gallery.querySelectorAll("[data-publish-photo]").forEach((button) => {{
              button.addEventListener("click", async () => {{
                try {{
                  const data = await postJson("/api/photos/publish", {{
                    member_id: memberId,
                    pin,
                    photo_id: button.dataset.publishPhoto,
                  }});
                  showStatus(data.message || "Foto veröffentlicht.");
                  window.setTimeout(() => window.location.reload(), 650);
                }} catch (error) {{
                  showStatus(error.message || "Foto konnte nicht veröffentlicht werden.");
                }}
              }});
            }});
          }}

          const photoUploadForm = document.querySelector("#photo-upload-form");
          if (photoUploadForm) {{
            photoUploadForm.addEventListener("submit", async (event) => {{
              event.preventDefault();
              const button = photoUploadForm.querySelector("button[type='submit']");
              const fileInput = photoUploadForm.querySelector("input[type='file']");
              const file = fileInput.files[0];
              if (!file) {{
                showStatus("Bitte ein Foto auswählen.");
                return;
              }}
              if (button) {{
                button.disabled = true;
              }}
              try {{
                const payload = Object.fromEntries(new FormData(photoUploadForm).entries());
                payload.image_data = await readFileAsDataUrl(file);
                delete payload.photo_file;
                const data = await postJson("/api/photos/upload", payload);
                showStatus(data.message || "Foto gespeichert.");
                photoUploadForm.reset();
              }} catch (error) {{
                showStatus(error.message || "Foto konnte nicht gespeichert werden.");
              }} finally {{
                if (button) {{
                  button.disabled = false;
                }}
              }}
            }});
          }}

          document.querySelectorAll("input[type='range'][data-output]").forEach((input) => {{
            const output = document.querySelector(input.dataset.output);
            const syncOutput = () => {{
              if (output) {{
                output.textContent = input.value;
              }}
            }};
            input.addEventListener("input", syncOutput);
            syncOutput();
          }});

          const avatarForm = document.querySelector("#avatar-form");
          if (avatarForm) {{
            const heightInput = avatarForm.querySelector("#avatar-height");
            const weightInput = avatarForm.querySelector("#avatar-weight");
            const bmiOutput = avatarForm.querySelector("#avatar-bmi");
            const syncAvatarBmi = () => {{
              const height = Number(heightInput?.value || 0) / 100;
              const weight = Number(weightInput?.value || 0);
              if (!bmiOutput || height <= 0 || weight <= 0) {{
                return;
              }}
              bmiOutput.value = (weight / (height * height)).toFixed(1);
            }};
            heightInput?.addEventListener("input", syncAvatarBmi);
            weightInput?.addEventListener("input", syncAvatarBmi);
            syncAvatarBmi();

            avatarForm.addEventListener("submit", async (event) => {{
              event.preventDefault();
              const button = avatarForm.querySelector("button[type='submit']");
              const frontInput = avatarForm.querySelector("input[name='front_photo_file']");
              const sideInput = avatarForm.querySelector("input[name='side_photo_file']");
              if (button) {{
                button.disabled = true;
              }}
              try {{
                const payload = Object.fromEntries(new FormData(avatarForm).entries());
                delete payload.front_photo_file;
                delete payload.side_photo_file;
                if (frontInput && frontInput.files[0]) {{
                  payload.front_image_data = await readFileAsDataUrl(frontInput.files[0]);
                }}
                if (sideInput && sideInput.files[0]) {{
                  payload.side_image_data = await readFileAsDataUrl(sideInput.files[0]);
                }}
                const data = await postJson("/api/avatar", payload);
                showStatus(data.message || "Avatar gespeichert.");
                window.setTimeout(() => window.location.reload(), 650);
              }} catch (error) {{
                showStatus(error.message || "Avatar konnte nicht gespeichert werden.");
                if (button) {{
                  button.disabled = false;
                }}
              }}
            }});
          }}

          const photoGalleryForm = document.querySelector("#photo-gallery-form");
          if (photoGalleryForm) {{
            photoGalleryForm.addEventListener("submit", async (event) => {{
              event.preventDefault();
              const payload = Object.fromEntries(new FormData(photoGalleryForm).entries());
              try {{
                const data = await postJson("/api/photos/private", payload);
                renderPhotoGallery(data.photos || [], payload.member_id, payload.pin);
                showStatus(data.message || "Private Galerie geladen.");
              }} catch (error) {{
                showStatus(error.message || "Private Galerie konnte nicht geladen werden.");
              }}
            }});
          }}

          const compareButton = document.querySelector("#photo-compare-button");
          if (compareButton) {{
            compareButton.addEventListener("click", () => {{
              const selected = [...document.querySelectorAll(".photo-compare:checked")].map((item) => item.value);
              if (selected.length !== 2) {{
                showStatus("Bitte genau zwei Fotos zum Vergleichen auswählen.");
                return;
              }}
              const photos = window.__beaPrivatePhotos || [];
              const selectedPhotos = selected.map((id) => photos.find((photo) => photo.id === id)).filter(Boolean);
              const board = document.querySelector("#compare-board");
              board.innerHTML = selectedPhotos.map((photo) => `
                <article>
                  <img src="${{photo.image_data}}" alt="${{escapeHtml(photo.title)}}">
                  <h3>${{escapeHtml(photo.title)}}</h3>
                  <p class="subtle">${{escapeHtml(photo.photo_type)}} · ${{escapeHtml(photo.created_at)}}</p>
                </article>
              `).join("");
              board.classList.add("is-visible");
            }});
          }}

          const updateForm = document.querySelector("#update-form");
          const updateButton = document.querySelector("#update-button");
          const discoStart = document.querySelector("#disco-start");
          const discoStop = document.querySelector("#disco-stop");
          const discoColors = ["#f7d046", "#35b779", "#2f80ed", "#a347c7", "#ef476f", "#06b6d4"];
          const originalBackground = document.body.style.background;
          let discoTimer = null;
          let discoIndex = 0;

          discoStart.addEventListener("click", () => {{
            if (discoTimer) {{
              return;
            }}
            document.body.style.transition = "background 180ms ease";
            discoTimer = window.setInterval(() => {{
              document.body.style.background = discoColors[discoIndex % discoColors.length];
              discoIndex += 1;
            }}, 500);
            showStatus("Disco gestartet.");
          }});

          discoStop.addEventListener("click", () => {{
            if (discoTimer) {{
              window.clearInterval(discoTimer);
              discoTimer = null;
            }}
            document.body.style.background = originalBackground;
            showStatus("Disco beendet.");
          }});

          updateForm.addEventListener("submit", async (event) => {{
            event.preventDefault();
            updateButton.disabled = true;
            updateButton.textContent = "Aktualisiere...";
            showStatus("Update wird geladen.");

            try {{
              const data = await postJson("/update", {{}});
              showStatus(data.message || "Update geladen. Dienst wird neu gestartet.");
              window.setTimeout(() => window.location.reload(), 8000);
            }} catch (error) {{
              showStatus(error.message || "Update fehlgeschlagen.");
              updateButton.disabled = false;
              updateButton.textContent = "GitHub Update";
            }}
          }});
        </script>
      </body>
    </html>
    """


def stat_cards(state: dict) -> str:
    open_assignments = sum(1 for item in state["assignments"] if item["status"] == "open")
    team_xp = sum(total_xp(member) for member in state["members"])
    sport_count = len(state["sport_entries"])
    meal_count = len(state["nutrition_entries"])
    stats = (
        ("Mitglieder", len(state["members"])),
        ("Team XP", team_xp),
        ("Offene Aufgaben", open_assignments),
        ("Einträge", sport_count + meal_count),
    )
    return "\n".join(
        f"""
        <article class="stat-card">
          <span>{h(label)}</span>
          <strong>{h(value)}</strong>
        </article>
        """
        for label, value in stats
    )


def render_leaderboard(state: dict, limit: int | None = None) -> str:
    members = leaderboard(state)
    if limit:
        members = members[:limit]

    rows = []
    for index, member in enumerate(members, start=1):
        total = total_xp(member)
        level = level_for_xp(total)
        rows.append(
            f"""
            <div class="member-rank">
              <span class="rank-number">{index}</span>
              <div>
                <strong>{h(member["name"])}</strong>
                <p class="subtle">{h(member["focus"])} · Serie {h(member["streak"])} Tage</p>
              </div>
              <div>
                <strong>Level {level["level"]}</strong>
                <p class="subtle">{total} XP</p>
              </div>
            </div>
            """
        )
    return "".join(rows)


def render_group_card(state: dict, group: dict) -> str:
    member_ids = group.setdefault("members", [])
    member_tags = "".join(
        f'<span class="tag area-team">{h(member_name(state, member_id))}</span>'
        for member_id in member_ids
    )
    challenge_count = sum(1 for challenge in state.setdefault("challenges", []) if challenge.get("group_id") == group["id"])
    return f"""
      <article class="card area-team">
        <div class="row">
          <div>
            <h3>{h(group["name"])}</h3>
            <p class="subtle">{h(group.get("description", ""))}</p>
          </div>
          <span class="tag area-team">{h(group.get("focus", "Team"))}</span>
        </div>
        <div class="avatar-meta" style="margin-top: 0.75rem;">
          {member_tags or '<span class="meta">Noch keine Mitglieder</span>'}
        </div>
        <p class="subtle" style="margin-top: 0.75rem;">{h(len(member_ids))} Mitglieder - {h(challenge_count)} Challenges</p>
        <form class="form-grid" data-api-form data-endpoint="/api/groups/join" style="margin-top: 0.85rem;">
          <input type="hidden" name="group_id" value="{h(group["id"])}">
          <label>
            Mitglied
            <select name="member_id">{render_member_options(state, "bea")}</select>
          </label>
          <button class="button blue" type="submit">Gruppe beitreten</button>
        </form>
      </article>
    """


def render_challenge_card(state: dict, challenge: dict, with_form: bool = False) -> str:
    total_progress = sum(int(value) for value in challenge.get("participants", {}).values())
    progress = int((total_progress / max(1, int(challenge["goal"]))) * 100)
    group_id = str(challenge.get("group_id") or "")
    challenge_group = next((group for group in groups(state) if group.get("id") == group_id), None)
    group_members = challenge_group.get("members", []) if challenge_group else []
    group_label = group_name(state, group_id)
    participants = []
    for member_id, value in challenge.get("participants", {}).items():
        participants.append(
            f'<span class="tag area-team">{h(member_name(state, member_id))}: {h(value)} {h(challenge["unit"])}</span>'
        )

    form = ""
    if with_form:
        form = f"""
          <form class="form-grid" data-api-form data-endpoint="/api/challenges/progress">
            <input type="hidden" name="challenge_id" value="{h(challenge["id"])}">
            <label>
              Mitglied
              <select name="member_id">{render_member_options_for_ids(state, group_members, "bea")}</select>
            </label>
            <label>
              Fortschritt
              <input name="amount" type="number" min="1" value="1">
            </label>
            <button class="button blue full" type="submit">Fortschritt eintragen</button>
          </form>
        """

    return f"""
      <article class="card {area_class(challenge["category"])}">
        <div class="row">
          <div>
            <h3>{h(challenge["title"])}</h3>
            <p class="subtle">{h(AREA_LABELS[challenge["category"]])} - Gruppe: {h(group_label)} - Bonus {h(challenge["xp"])} XP</p>
            <p class="subtle">{h(challenge.get("description", ""))}</p>
          </div>
          <span class="tag {area_class(challenge["category"])}">{h(total_progress)} / {h(challenge["goal"])} {h(challenge["unit"])}</span>
        </div>
        {progress_bar(progress, challenge["title"])}
        <div class="row" style="justify-content: flex-start; flex-wrap: wrap; margin-top: 0.8rem;">
          {"".join(participants)}
        </div>
        {form}
      </article>
    """


def render_assignment_card(state: dict, assignment: dict) -> str:
    category = assignment["category"]
    done = assignment["status"] == "done"
    complete_form = ""
    if not done:
        complete_form = f"""
          <form data-api-form data-endpoint="/api/assignments/complete">
            <input type="hidden" name="assignment_id" value="{h(assignment["id"])}">
            <button class="button secondary" type="submit">Erledigt</button>
          </form>
        """

    return f"""
      <article class="card {area_class(category)}">
        <div class="row">
          <span class="tag {area_class(category)}">{h(AREA_LABELS[category])}</span>
          <span class="meta">{h("erledigt" if done else "offen")}</span>
        </div>
        <h3>{h(assignment["title"])}</h3>
        <p>{h(assignment["details"])}</p>
        <p class="subtle">
          {h(member_name(state, assignment["from_member"]))} an {h(member_name(state, assignment["to_member"]))}
          · bis {h(assignment["due"])} · {h(assignment["xp"])} XP
        </p>
        {complete_form}
      </article>
    """


def render_rpg_boss_card(boss: dict) -> str:
    max_hp = max(1, int(boss.get("max_hp", 1)))
    hp = max(0, int(boss.get("hp", max_hp)))
    damage_progress = int(((max_hp - hp) / max_hp) * 100)
    defeated = hp <= 0
    status = "Besiegt" if defeated else "Aktiv"
    status_class = "area-nutrition" if defeated else "area-strength"
    card_class = "boss-card is-defeated" if defeated else "boss-card"
    return f"""
      <article class="card {card_class}">
        <div class="row">
          <div>
            <span class="tag area-team">{h(boss.get("title", "Boss"))}</span>
            <h3 style="margin-top: 0.65rem;">{h(boss.get("name", "Boss"))}</h3>
            <p class="subtle">Schwäche: {h(boss.get("weakness", "Konstanz"))}</p>
          </div>
          <span class="tag {status_class}">{status}</span>
        </div>
        <div class="boss-hp" style="margin-top: 0.9rem;">
          {progress_bar(damage_progress, f'{boss.get("name", "Boss")} Schaden')}
        </div>
        <p class="subtle" style="margin-top: 0.65rem;">{hp} / {max_hp} LP übrig</p>
      </article>
    """


def render_character_cards(state: dict) -> str:
    cards = []
    for member in leaderboard(state):
        character = rpg_character(member)
        profile = state.get("profiles", {}).get(member["id"], {})
        plan = state.get("generated_plans", {}).get(member["id"], {})
        adventure = plan.get("adventure", {})
        display_name = adventure.get("character_name") or character["name"]
        role_label = adventure.get("role_label") or ADVENTURE_ROLE_LABELS.get(profile.get("adventure_role", "guardian"), "Wächter")
        origin = adventure.get("origin") or profile.get("character_origin") or "Noch keine Herkunft notiert."
        hobbies = adventure.get("hobbies") or profile.get("hobbies") or "Hobbies noch offen"
        daily_life = adventure.get("daily_life") or WORK_STYLE_LABELS.get(profile.get("work_style", "mixed"), "abwechslungsreich")
        sleep = adventure.get("sleep") or f'{profile.get("sleep_hours", 7)} h, {SLEEP_QUALITY_LABELS.get(profile.get("sleep_quality", "okay"), "wechselhaft")}'
        motivation = adventure.get("motivation_label") or MOTIVATION_STYLE_LABELS.get(profile.get("motivation_style", "story"), "Story, Quests und Abenteuer")
        initial = str(display_name or "?")[0].upper()
        cards.append(
            f"""
            <article class="card character-card {area_class(character["strongest_area"])}">
              <span class="character-avatar">{h(initial)}</span>
              <div>
                <div class="row">
                  <div>
                    <h3>{h(display_name)}</h3>
                    <p class="subtle">{h(character["title"])} - {h(role_label)} der Klasse {h(character["class_name"])}</p>
                  </div>
                  <span class="tag {area_class(character["strongest_area"])}">Level {h(character["level"])}</span>
                </div>
                <div style="margin-top: 0.65rem;">{progress_bar(character["progress"], f'{character["name"]} Charakterfortschritt')}</div>
                <p class="subtle" style="margin-top: 0.45rem;">{h(character["total_xp"])} XP - Serie {h(character["streak"])} Tage</p>
                <p class="subtle" style="margin-top: 0.45rem;">Herkunft: {h(origin)}</p>
                <p class="subtle" style="margin-top: 0.45rem;">Hobbies: {h(hobbies)} - Alltag: {h(daily_life)} - Schlaf: {h(sleep)}</p>
                <p class="subtle" style="margin-top: 0.45rem;">Motivation: {h(motivation)}. {h(adventure.get("avatar_notes", "Avatar wird über Fotos und Körperwerte weiter verfeinert."))}</p>
              </div>
            </article>
            """
        )
    return "".join(cards)


def render_avatar_svg(profile: dict) -> str:
    height_cm = int(profile.get("height_cm", 170))
    weight_kg = int(profile.get("weight_kg", 70))
    neck_cm = int(profile.get("neck_cm", 36))
    shoulders = int(profile.get("shoulder_width", 100))
    chest = int(profile.get("chest_cm", 96))
    waist = int(profile.get("waist_width", 92))
    hips = int(profile.get("hip_width", 98))
    thigh_left = int(profile.get("thigh_left_cm", 56))
    thigh_right = int(profile.get("thigh_right_cm", 56))
    muscle = int(profile.get("muscle", 45))
    body_fat = int(profile.get("body_fat", 35))
    hair_style = str(profile.get("hair_style", "short"))
    clothing_style = str(profile.get("clothing_style", "training"))

    shoulder_width = max(58, min(96, 72 + (shoulders - 100) * 0.42 + muscle * 0.08))
    chest_width = max(46, min(90, 58 + (chest - 96) * 0.34 + muscle * 0.08))
    waist_width = max(38, min(82, 46 + (waist - 92) * 0.34 + body_fat * 0.10))
    hip_width = max(48, min(92, 58 + (hips - 98) * 0.36 + body_fat * 0.08))
    neck_width = max(12, min(24, 15 + (neck_cm - 36) * 0.25))
    arm_width = max(7, min(15, 9 + muscle * 0.06 + body_fat * 0.02))
    left_leg_width = max(12, min(24, 15 + (thigh_left - 56) * 0.20 + muscle * 0.03 + body_fat * 0.02))
    right_leg_width = max(12, min(24, 15 + (thigh_right - 56) * 0.20 + muscle * 0.03 + body_fat * 0.02))
    height_shift = max(-14, min(22, (height_cm - 170) * 0.22))
    shoe_color = "#263241"

    center = 100
    torso_top = 86
    chest_y = 104
    waist_y = 142 + height_shift * 0.18
    hip_y = 181 + height_shift * 0.35
    knee_y = 239 + height_shift * 0.62
    foot_y = 298 + height_shift

    skin = h(profile.get("skin_color", "#d59f7a"))
    hair = h(profile.get("hair_color", "#2f241f"))
    outfit = h(profile.get("outfit_color", "#2563eb"))
    shade = "rgb(23 32 51 / 14%)"

    hair_map = {
        "short": f"""
          <path d="M78 56 C80 36 116 31 123 55 C112 45 91 45 78 56 Z" fill="{hair}"></path>
          <path d="M80 50 C83 38 96 32 106 35 C97 37 90 43 86 54 Z" fill="rgb(255 255 255 / 16%)"></path>
        """,
        "bob": f"""
          <path d="M75 55 C76 35 122 34 125 56 L121 84 C111 78 89 78 79 84 Z" fill="{hair}"></path>
          <path d="M79 54 C86 43 112 42 121 55 C111 48 91 48 79 54 Z" fill="rgb(255 255 255 / 14%)"></path>
        """,
        "long": f"""
          <path d="M74 55 C76 34 124 34 126 56 C130 86 122 112 111 126 C110 104 89 104 88 126 C78 112 70 86 74 55 Z" fill="{hair}"></path>
          <path d="M80 53 C88 42 114 42 122 55 C112 48 91 48 80 53 Z" fill="rgb(255 255 255 / 14%)"></path>
        """,
        "curly": f"""
          <circle cx="79" cy="55" r="9" fill="{hair}"></circle>
          <circle cx="87" cy="43" r="10" fill="{hair}"></circle>
          <circle cx="100" cy="38" r="11" fill="{hair}"></circle>
          <circle cx="113" cy="43" r="10" fill="{hair}"></circle>
          <circle cx="122" cy="56" r="9" fill="{hair}"></circle>
          <path d="M78 59 C88 47 112 47 123 59 L121 78 C112 70 89 70 80 78 Z" fill="{hair}"></path>
        """,
        "bun": f"""
          <circle cx="100" cy="31" r="12" fill="{hair}"></circle>
          <path d="M77 56 C80 37 120 37 123 56 C111 46 90 46 77 56 Z" fill="{hair}"></path>
        """,
    }
    hair_svg = hair_map.get(hair_style, hair_map["short"])

    torso_path = f"""
      M {center - shoulder_width / 2:.1f} {torso_top:.1f}
      C {center - chest_width / 2:.1f} {chest_y - 8:.1f}, {center - chest_width / 2:.1f} {chest_y + 10:.1f}, {center - waist_width / 2:.1f} {waist_y:.1f}
      L {center - hip_width / 2:.1f} {hip_y:.1f}
      L {center + hip_width / 2:.1f} {hip_y:.1f}
      L {center + waist_width / 2:.1f} {waist_y:.1f}
      C {center + chest_width / 2:.1f} {chest_y + 10:.1f}, {center + chest_width / 2:.1f} {chest_y - 8:.1f}, {center + shoulder_width / 2:.1f} {torso_top:.1f}
      Z
    """
    dress_path = f"""
      M {center - shoulder_width / 2:.1f} {torso_top:.1f}
      C {center - chest_width / 2:.1f} {chest_y:.1f}, {center - waist_width / 2:.1f} {waist_y:.1f}, {center - hip_width / 2 - 7:.1f} {knee_y - 10:.1f}
      L {center + hip_width / 2 + 7:.1f} {knee_y - 10:.1f}
      C {center + waist_width / 2:.1f} {waist_y:.1f}, {center + chest_width / 2:.1f} {chest_y:.1f}, {center + shoulder_width / 2:.1f} {torso_top:.1f}
      Z
    """

    clothing_map = {
        "training": f"""
          <path d="{torso_path}" fill="{outfit}"></path>
          <path d="M{center - 17} {torso_top + 6} L{center} {torso_top + 28} L{center + 17} {torso_top + 6}" fill="none" stroke="rgb(255 255 255 / 34%)" stroke-width="3" stroke-linecap="round"></path>
          <rect x="{center - hip_width / 2:.1f}" y="{hip_y - 2:.1f}" width="{hip_width:.1f}" height="19" rx="7" fill="{outfit}" opacity="0.88"></rect>
        """,
        "hoodie": f"""
          <path d="{torso_path}" fill="{outfit}"></path>
          <path d="M{center - 25} 88 C{center - 15} 73 {center + 15} 73 {center + 25} 88" fill="none" stroke="rgb(255 255 255 / 46%)" stroke-width="5" stroke-linecap="round"></path>
          <rect x="{center - 19}" y="{waist_y - 13:.1f}" width="38" height="18" rx="8" fill="rgb(255 255 255 / 18%)"></rect>
        """,
        "tank": f"""
          <path d="{torso_path}" fill="{outfit}"></path>
          <path d="M{center - 24} {torso_top:.1f} C{center - 12} {torso_top + 18:.1f} {center + 12} {torso_top + 18:.1f} {center + 24} {torso_top:.1f}" fill="{skin}"></path>
          <path d="M{center - 19} {torso_top:.1f} L{center - 8} {chest_y + 7:.1f} M{center + 19} {torso_top:.1f} L{center + 8} {chest_y + 7:.1f}" stroke="rgb(255 255 255 / 42%)" stroke-width="4" stroke-linecap="round"></path>
        """,
        "jacket": f"""
          <path d="{torso_path}" fill="{outfit}"></path>
          <path d="M{center} {torso_top + 4:.1f} L{center} {hip_y - 2:.1f}" stroke="rgb(255 255 255 / 58%)" stroke-width="3"></path>
          <path d="M{center - 28} {torso_top + 8:.1f} C{center - 12} {chest_y + 6:.1f} {center - 10} {waist_y:.1f} {center - 18} {hip_y - 4:.1f}" fill="none" stroke="rgb(255 255 255 / 28%)" stroke-width="4"></path>
          <path d="M{center + 28} {torso_top + 8:.1f} C{center + 12} {chest_y + 6:.1f} {center + 10} {waist_y:.1f} {center + 18} {hip_y - 4:.1f}" fill="none" stroke="rgb(255 255 255 / 28%)" stroke-width="4"></path>
        """,
        "dress": f"""
          <path d="{dress_path}" fill="{outfit}"></path>
          <path d="M{center - 19} {torso_top + 2:.1f} C{center - 7} {chest_y + 6:.1f} {center + 7} {chest_y + 6:.1f} {center + 19} {torso_top + 2:.1f}" fill="none" stroke="rgb(255 255 255 / 36%)" stroke-width="4" stroke-linecap="round"></path>
        """,
    }
    clothing_svg = clothing_map.get(clothing_style, clothing_map["training"])

    return f"""
      <svg class="avatar-svg" viewBox="0 0 200 320" role="img" aria-label="Avatar von {h(profile.get("name", "Mitglied"))}">
        <ellipse cx="100" cy="304" rx="52" ry="8" fill="rgb(23 32 51 / 16%)"></ellipse>
        <path d="M{center - shoulder_width / 2:.1f} 92 C53 119 50 156 58 191" fill="none" stroke="{shade}" stroke-width="{arm_width + 2:.1f}" stroke-linecap="round"></path>
        <path d="M{center + shoulder_width / 2:.1f} 92 C147 119 150 156 142 191" fill="none" stroke="{shade}" stroke-width="{arm_width + 2:.1f}" stroke-linecap="round"></path>
        <rect x="{center - hip_width / 2:.1f}" y="{hip_y - 3:.1f}" width="{hip_width:.1f}" height="20" rx="8" fill="{shade}"></rect>
        {hair_svg}
        <circle cx="100" cy="58" r="22" fill="{skin}"></circle>
        <circle cx="91" cy="58" r="2" fill="#172033"></circle>
        <circle cx="109" cy="58" r="2" fill="#172033"></circle>
        <path d="M100 62 C98 66 98 68 102 68" fill="none" stroke="rgb(23 32 51 / 40%)" stroke-width="1.4" stroke-linecap="round"></path>
        <path d="M91 72 C96 76 104 76 109 72" fill="none" stroke="rgb(23 32 51 / 46%)" stroke-width="1.6" stroke-linecap="round"></path>
        <rect x="{center - neck_width / 2:.1f}" y="76" width="{neck_width:.1f}" height="18" rx="6" fill="{skin}"></rect>
        <path d="M{center - shoulder_width / 2:.1f} 92 C50 120 49 155 57 190" fill="none" stroke="{skin}" stroke-width="{arm_width:.1f}" stroke-linecap="round"></path>
        <path d="M{center + shoulder_width / 2:.1f} 92 C150 120 151 155 143 190" fill="none" stroke="{skin}" stroke-width="{arm_width:.1f}" stroke-linecap="round"></path>
        <circle cx="57" cy="191" r="{arm_width / 1.5:.1f}" fill="{skin}"></circle>
        <circle cx="143" cy="191" r="{arm_width / 1.5:.1f}" fill="{skin}"></circle>
        {clothing_svg}
        <rect x="{center - hip_width / 4 - left_leg_width:.1f}" y="{hip_y + 4:.1f}" width="{left_leg_width * 1.28:.1f}" height="{knee_y - hip_y + 8:.1f}" rx="10" fill="{outfit}" opacity="0.92"></rect>
        <rect x="{center + hip_width / 4 - right_leg_width * 0.28:.1f}" y="{hip_y + 4:.1f}" width="{right_leg_width * 1.28:.1f}" height="{knee_y - hip_y + 8:.1f}" rx="10" fill="{outfit}" opacity="0.92"></rect>
        <rect x="{center - hip_width / 4 - left_leg_width * 0.84:.1f}" y="{knee_y:.1f}" width="{left_leg_width:.1f}" height="{foot_y - knee_y:.1f}" rx="8" fill="{skin}"></rect>
        <rect x="{center + hip_width / 4 - right_leg_width * 0.16:.1f}" y="{knee_y:.1f}" width="{right_leg_width:.1f}" height="{foot_y - knee_y:.1f}" rx="8" fill="{skin}"></rect>
        <ellipse cx="{center - hip_width / 4 - left_leg_width * 0.30:.1f}" cy="{foot_y + 3:.1f}" rx="13" ry="5" fill="{shoe_color}"></ellipse>
        <ellipse cx="{center + hip_width / 4 + right_leg_width * 0.34:.1f}" cy="{foot_y + 3:.1f}" rx="13" ry="5" fill="{shoe_color}"></ellipse>
        <text x="100" y="315" text-anchor="middle" fill="rgb(23 32 51 / 58%)" font-size="8" font-weight="700">{h(weight_kg)} kg - BMI {h(profile.get("bmi") or "-")}</text>
      </svg>
    """


def render_avatar_card(profile: dict) -> str:
    hair_label = AVATAR_HAIR_STYLES.get(str(profile.get("hair_style", "short")), "Kurz")
    clothing_label = AVATAR_CLOTHING_STYLES.get(str(profile.get("clothing_style", "training")), "Trainingsshirt")
    bmi = profile.get("bmi")
    return f"""
      <article class="card avatar-card">
        <div class="avatar-stage">
          {render_avatar_svg(profile)}
        </div>
        <div>
          <div class="row">
            <div>
              <h3>{h(profile["name"])}</h3>
              <p class="subtle">Körperbau: {h(profile["body_label"])} - Kalibrierung: {h(profile["calibration"])}</p>
            </div>
            <span class="tag area-team">{h(profile["height_cm"])} cm / {h(profile.get("weight_kg", "-"))} kg</span>
          </div>
          <div class="avatar-meta" style="margin-top: 0.75rem;">
            <span class="tag area-strength">BMI {h(bmi if bmi is not None else "-")}</span>
            <span class="tag area-endurance">Hals {h(profile.get("neck_cm", "-"))}</span>
            <span class="tag area-endurance">Schulter {h(profile.get("shoulder_width", "-"))}</span>
            <span class="tag area-strength">Brust {h(profile.get("chest_cm", "-"))}</span>
            <span class="tag area-nutrition">Taille {h(profile.get("waist_width", "-"))}</span>
            <span class="tag area-nutrition">Hüfte {h(profile.get("hip_width", "-"))}</span>
            <span class="tag area-team">L/R OS {h(profile.get("thigh_left_cm", "-"))}/{h(profile.get("thigh_right_cm", "-"))}</span>
            <span class="tag area-team">{h(hair_label)}</span>
            <span class="tag area-team">{h(clothing_label)}</span>
          </div>
        </div>
      </article>
    """


def parse_entry_date(value: str) -> date:
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return date.min


def entries_since(entries: list[dict], days: int, member_id: str) -> list[dict]:
    cutoff = date.today() - timedelta(days=days)
    return [
        entry
        for entry in entries
        if entry.get("member_id") == member_id and parse_entry_date(str(entry.get("created_at") or entry.get("entry_date") or "")) >= cutoff
    ]


def progress_activity_balance(state: dict, member_id: str, days: int) -> dict:
    sports = entries_since(state.get("sport_entries", []), days, member_id)
    meals = entries_since(state.get("nutrition_entries", []), days, member_id)
    endurance = [entry for entry in sports if entry.get("sport_type") == "endurance"]
    strength = [entry for entry in sports if entry.get("sport_type") == "strength"]
    calories = sum(int(entry.get("calories", 0)) for entry in meals)
    protein = sum(int(entry.get("protein", 0)) for entry in meals)
    water = sum(float(entry.get("water", 0)) for entry in meals)
    return {
        "days": days,
        "sport_sessions": len(sports),
        "sport_minutes": sum(int(entry.get("duration", 0)) for entry in sports),
        "endurance_minutes": sum(int(entry.get("duration", 0)) for entry in endurance),
        "strength_sessions": len(strength),
        "sport_xp": sum(int(entry.get("xp", 0)) for entry in sports),
        "meal_count": len(meals),
        "calories": calories,
        "avg_calories": round(calories / max(1, days)),
        "protein": protein,
        "avg_protein": round(protein / max(1, days)),
        "water": round(water, 1),
        "avg_water": round(water / max(1, days), 1),
    }


def bmi_value(weight_kg: float | None, height_cm: float | None) -> float | None:
    if not weight_kg or not height_cm:
        return None
    height_m = float(height_cm) / 100
    if height_m <= 0:
        return None
    return round(float(weight_kg) / (height_m * height_m), 1)


def bmi_label(value: float | None) -> str:
    if value is None:
        return "Keine Daten"
    if value < 18.5:
        return "niedrig"
    if value < 25:
        return "Normalbereich"
    if value < 30:
        return "erhöht"
    return "stark erhöht"


def render_progress_member_card(state: dict, member: dict) -> str:
    member_id = member["id"]
    profile = state.get("profiles", {}).get(member_id, {})
    plan = state.get("generated_plans", {}).get(member_id, {})
    weight = latest_weight_for_member(state, member_id)
    height = profile.get("height_cm")
    bmi = bmi_value(weight, height)
    change = weight_change_for_member(state, member_id)
    change_text = "noch kein Verlauf" if change is None else f'{change:+.1f} kg / 30 Tage'
    target = plan.get("calories", {}).get("target")
    target_text = f"{target} kcal/Tag" if target else "Plan fehlt"
    return f"""
      <article class="card">
        <div class="row">
          <div>
            <h3>{h(member["name"])}</h3>
            <p class="subtle">{h(member.get("focus", ""))}</p>
          </div>
          <span class="tag area-team">{h(change_text)}</span>
        </div>
        <div class="grid three" style="margin-top: 0.85rem;">
          <div class="mini-metric">
            <span>Gewicht</span>
            <strong>{h(f"{weight:.1f} kg" if weight else "offen")}</strong>
          </div>
          <div class="mini-metric">
            <span>BMI</span>
            <strong>{h(bmi if bmi is not None else "-")}</strong>
          </div>
          <div class="mini-metric">
            <span>Plan</span>
            <strong>{h(target_text)}</strong>
          </div>
        </div>
        <p class="subtle" style="margin-top: 0.75rem;">BMI-Einordnung: {h(bmi_label(bmi))}. Nur als Orientierung.</p>
      </article>
    """


def render_balance_table(balance: dict) -> str:
    return f"""
      <table>
        <thead>
          <tr>
            <th>Zeitraum</th>
            <th>Sport</th>
            <th>Ausdauer</th>
            <th>Kraft</th>
            <th>Nahrung</th>
            <th>Kalorien / Tag</th>
            <th>Protein / Tag</th>
            <th>Wasser / Tag</th>
            <th>XP</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>{h(balance["days"])} Tage</td>
            <td>{h(balance["sport_sessions"])} Einheiten / {h(balance["sport_minutes"])} min</td>
            <td>{h(balance["endurance_minutes"])} min</td>
            <td>{h(balance["strength_sessions"])} Einheiten</td>
            <td>{h(balance["meal_count"])} Einträge</td>
            <td>{h(balance["avg_calories"])} kcal</td>
            <td>{h(balance["avg_protein"])} g</td>
            <td>{h(balance["avg_water"])} l</td>
            <td>{h(balance["sport_xp"])}</td>
          </tr>
        </tbody>
      </table>
    """


def render_weight_history(state: dict, member_id: str) -> str:
    rows = []
    for entry in weight_entries_for_member(state, member_id)[:8]:
        rows.append(
            f"""
            <tr>
              <td>{h(entry["entry_date"])}</td>
              <td>{h(entry["weight_kg"])} kg</td>
              <td>{h(entry.get("note", ""))}</td>
            </tr>
            """
        )
    if not rows:
        rows.append('<tr><td colspan="3" class="subtle">Noch keine Gewichtseinträge.</td></tr>')
    return f"""
      <table>
        <thead>
          <tr>
            <th>Datum</th>
            <th>Gewicht</th>
            <th>Notiz</th>
          </tr>
        </thead>
        <tbody>{"".join(rows)}</tbody>
      </table>
    """


def render_goal_tracking_summary(state: dict, member_id: str) -> str:
    plan = state.get("generated_plans", {}).get(member_id)
    if not plan:
        return """
          <article class="card">
            <h3>Noch kein Zielpfad</h3>
            <p class="subtle">Der erweiterte Fragebogen erstellt Ziel, Etappen, Check-ins und Abenteuerkontext.</p>
            <a class="button blue" href="/fragebogen" style="margin-top: 0.85rem;">Fragebogen starten</a>
          </article>
        """

    goal = plan.get("goal_tracking", {})
    checkpoints = goal.get("checkpoints", [])
    first_checkpoint = checkpoints[0]["details"] if checkpoints else "Check-ins entstehen mit dem nächsten Plan."
    target_parts = []
    if goal.get("target_weight_kg"):
        target_parts.append(f'{goal["target_weight_kg"]} kg')
    if goal.get("target_date"):
        target_parts.append(str(goal["target_date"]))
    target_label = " - ".join(target_parts) if target_parts else "offene Etappe"
    milestones = "".join(f"<li>{h(item)}</li>" for item in goal.get("milestones", [])[:3])
    calorie_delta_label = f'{int(goal.get("calorie_delta", 0)):+}'
    return f"""
      <article class="card area-team">
        <div class="row">
          <div>
            <span class="tag area-team">Zieltracking</span>
            <h3 style="margin-top: 0.65rem;">{h(goal.get("goal_text", "Fitnessziel"))}</h3>
          </div>
          <span class="tag area-nutrition">{h(goal.get("tracking_label", "wöchentlich"))}</span>
        </div>
        <div class="grid three" style="margin-top: 0.9rem;">
          <div class="mini-metric">
            <span>Messwert</span>
            <strong>{h(goal.get("metric_label", "Gewohnheiten"))}</strong>
          </div>
          <div class="mini-metric">
            <span>Zielmarke</span>
            <strong>{h(target_label)}</strong>
          </div>
          <div class="mini-metric">
            <span>Kalorienbilanz</span>
            <strong>{h(calorie_delta_label)}</strong>
          </div>
        </div>
        <p class="subtle" style="margin-top: 0.75rem;">{h(first_checkpoint)}</p>
        <ul class="subtle" style="margin-top: 0.75rem;">{milestones}</ul>
      </article>
    """


def render_plan_outlook(state: dict, member_id: str) -> str:
    plan = state.get("generated_plans", {}).get(member_id)
    if not plan:
        return """
          <article class="card">
            <h3>Noch kein Ausblick</h3>
            <p class="subtle">Füllt zuerst den Fragebogen aus. Danach berechnet Bea den Ausblick aus Zielkalorien, Erhaltung und Training.</p>
            <a class="button blue" href="/fragebogen" style="margin-top: 0.85rem;">Fragebogen starten</a>
          </article>
        """

    calories = plan["calories"]
    target = int(calories["target"])
    maintenance = int(calories["maintenance"])
    delta = target - maintenance
    weekly_weight_delta = round((delta * 7) / 7700, 2)
    four_week_delta = round(weekly_weight_delta * 4, 1)
    direction = "halten" if abs(weekly_weight_delta) < 0.05 else "steigen" if weekly_weight_delta > 0 else "sinken"
    training_count = len(plan.get("training", []))
    return f"""
      <article class="card area-nutrition">
        <div class="row">
          <div>
            <h3>Wenn der Plan eingehalten wird</h3>
            <p class="subtle">Ziel: {h(calories["goal_label"])} - Aktivität: {h(calories["activity_label"])}</p>
          </div>
          <span class="tag area-nutrition">{h(target)} kcal/Tag</span>
        </div>
        <div class="grid three" style="margin-top: 0.9rem;">
          <div class="mini-metric">
            <span>Kaloriendifferenz</span>
            <strong>{h(delta)}</strong>
          </div>
          <div class="mini-metric">
            <span>Trend / Woche</span>
            <strong>{h(f"{weekly_weight_delta:+.2f} kg")}</strong>
          </div>
          <div class="mini-metric">
            <span>4-Wochen-Ausblick</span>
            <strong>{h(f"{four_week_delta:+.1f} kg")}</strong>
          </div>
        </div>
        <p class="subtle" style="margin-top: 0.75rem;">Erwartung: Gewicht eher {h(direction)}. Geplant sind {h(training_count)} Trainingseinheiten pro Woche. Realität kann durch Wasser, Zyklus, Schlaf, Stress und Muskelaufbau abweichen.</p>
      </article>
    """


def render_daily_quest_card(state: dict, rpg: dict, quest: dict) -> str:
    completions = rpg.get("completed_quests", {})
    completed_members = [
        member
        for member in state["members"]
        if rpg_completion_key(rpg["daily_date"], member["id"], quest["id"]) in completions
    ]
    completion_tags = "".join(
        f'<span class="tag area-team">{h(member["name"])}</span>'
        for member in completed_members
    )
    completed_count = len(completed_members)
    total_members = max(1, len(state["members"]))
    return f"""
      <article class="card {area_class(quest["area"])}">
        <div class="row">
          <div>
            <span class="tag {area_class(quest["area"])}">{h(AREA_LABELS[quest["area"]])}</span>
            <h3 style="margin-top: 0.65rem;">{h(quest["title"])}</h3>
            <p class="subtle">{h(quest["description"])}</p>
          </div>
          <span class="tag area-team">+{h(quest["reward_xp"])} XP</span>
        </div>
        <div style="margin-top: 0.9rem;">{progress_bar(int((completed_count / total_members) * 100), quest["title"])}</div>
        <div class="row" style="justify-content: flex-start; margin-top: 0.8rem;">
          {completion_tags or '<span class="meta">Noch niemand</span>'}
        </div>
        <form class="form-grid" data-api-form data-endpoint="/api/rpg/quests/complete" style="margin-top: 0.85rem;">
          <input type="hidden" name="quest_id" value="{h(quest["id"])}">
          <label>
            Charakter
            <select name="member_id">{render_member_options(state, "bea")}</select>
          </label>
          <button class="button blue" type="submit">Quest abschließen</button>
        </form>
      </article>
    """


def render_battle_log(state: dict, rpg: dict) -> str:
    rows = []
    for item in rpg.get("battle_log", [])[:8]:
        extra = []
        if item.get("daily_defeated"):
            extra.append("Tagesboss besiegt")
        if item.get("weekly_defeated"):
            extra.append("Wochenboss besiegt")
        rows.append(
            f"""
            <article class="card">
              <div class="row">
                <div>
                  <h3>{h(member_name(state, item["member_id"]))} erledigt {h(item["quest_title"])}</h3>
                  <p class="subtle">{h(item["created_at"])} - {h(item["daily_damage"])} Tagesschaden, {h(item["weekly_damage"])} Wochenschaden</p>
                </div>
                <span class="tag area-team">{h(", ".join(extra) if extra else "Treffer")}</span>
              </div>
            </article>
            """
        )
    if not rows:
        return '<article class="card"><p class="subtle">Noch keine Kämpfe protokolliert. Schließt die erste Tagesquest ab.</p></article>'
    return "".join(rows)


def render_exercise_list(exercises: list[dict]) -> str:
    if not exercises:
        return ""
    items = []
    for exercise in exercises:
        cues = "".join(f"<li>{h(cue)}</li>" for cue in exercise.get("cues", []))
        progression = ""
        if exercise.get("progression"):
            progression = f'<p class="subtle" style="margin-top: 0.35rem;"><strong>Progression:</strong> {h(exercise["progression"])}</p>'
        items.append(
            f"""
            <div class="exercise-item">
              <div class="row">
                <h3>{h(exercise.get("name", "Übung"))}</h3>
                <span class="tag area-team">{h(exercise.get("sets", "-"))} x {h(exercise.get("reps", "-"))}</span>
              </div>
              <span class="meta">Pause: {h(exercise.get("rest", "60-90 s"))}</span>
              <p class="subtle">{h(exercise.get("explanation", ""))}</p>
              <ul class="cue-list">{cues}</ul>
              {progression}
              <p class="subtle" style="margin-top: 0.45rem;"><strong>Vermeiden:</strong> {h(exercise.get("avoid", ""))}</p>
              <p class="subtle" style="margin-top: 0.35rem;"><strong>Alternative:</strong> {h(exercise.get("alternative", ""))}</p>
            </div>
            """
        )
    return f'<div class="exercise-list">{"".join(items)}</div>'


def render_plan_info_cards(items: list[dict], empty_text: str) -> str:
    if not items:
        return f'<article class="card"><p class="subtle">{h(empty_text)}</p></article>'
    return "".join(
        f"""
        <article class="card">
          <h3>{h(item.get("title", "Hinweis"))}</h3>
          <p class="subtle">{h(item.get("details", ""))}</p>
        </article>
        """
        for item in items
    )


def render_generated_plan(state: dict, plan: dict) -> str:
    calories = plan["calories"]
    macros = plan["macros"]
    training = "".join(
        f"""
        <article class="card">
          <div class="row">
            <span class="tag {area_class(training_type_area(item["type"]))}">{h(item["type"])}</span>
            <span class="meta">{h(item["duration"])}</span>
          </div>
          <h3>{h(item["title"])}</h3>
          <p class="subtle"><strong>Fokus:</strong> {h(item.get("focus", "Allgemeine Fitness"))}</p>
          <p class="subtle">{h(item["details"])}</p>
          {render_exercise_list(item.get("exercises", []))}
        </article>
        """
        for item in plan.get("training", [])
    )
    nutrition = "".join(
        f"""
        <article class="card">
          <h3>{h(item["title"])}</h3>
          <p><strong>{h(item["target"])}</strong></p>
          <p class="subtle">{h(item["details"])}</p>
        </article>
        """
        for item in plan["nutrition"]
    )
    goal_tracking = plan.get("goal_tracking", {})
    milestones = "".join(f"<li>{h(item)}</li>" for item in goal_tracking.get("milestones", []))
    checkpoints = "".join(
        f"""
        <article class="card">
          <h3>{h(item["title"])}</h3>
          <p class="subtle">{h(item["details"])}</p>
        </article>
        """
        for item in goal_tracking.get("checkpoints", [])
    )
    target_parts = []
    if goal_tracking.get("target_weight_kg"):
        target_parts.append(f'{goal_tracking["target_weight_kg"]} kg')
    if goal_tracking.get("target_date"):
        target_parts.append(str(goal_tracking["target_date"]))
    target_label = " - ".join(target_parts) if target_parts else "offenes Etappenziel"
    calorie_delta = int(goal_tracking.get("calorie_delta", int(calories["target"]) - int(calories["maintenance"])))
    calorie_delta_label = f"{calorie_delta:+}"
    plan_reason = plan.get("plan_reason", "Plananpassung")
    plan_version = plan.get("plan_version", 1)
    next_checkin_at = plan.get("next_checkin_at", "")
    adventure = plan.get("adventure", {})
    lifestyle = plan.get("lifestyle", {})
    training_focus = plan.get("training_focus", {})
    focus_area_tags = "".join(
        f'<span class="tag area-strength">{h(area)}</span>'
        for area in training_focus.get("areas", [])
    )
    focus_cards = render_plan_info_cards(
        training_focus.get("recommendations", []),
        "Nach dem nächsten Fragebogen entstehen Fokusvorschläge.",
    )
    injury_cards = render_plan_info_cards(
        training_focus.get("injury_considerations", []),
        "Keine Verletzungshistorie angegeben. Technik bleibt trotzdem wichtiger als Gewicht.",
    )
    progression_cards = render_plan_info_cards(
        plan.get("progression", []),
        "Progression entsteht mit dem nächsten Check-in.",
    )
    regeneration = "".join(
        f"""
        <article class="card area-team">
          <div class="row">
            <span class="tag area-team">{h(item["type"])}</span>
            <span class="meta">{h(item["duration"])}</span>
          </div>
          <h3>{h(item["title"])}</h3>
          <p class="subtle">{h(item["details"])}</p>
        </article>
        """
        for item in plan.get("regeneration", [])
    )
    notes = "".join(f"<li>{h(note)}</li>" for note in plan.get("notes", []))
    return f"""
      <article class="panel">
        <div class="row">
          <div>
            <h2>{h(member_name(state, plan["member_id"]))}: Trainings- und Ernährungsplan</h2>
            <p class="subtle">Version {h(plan_version)} - {h(plan_reason)} am {h(plan["created_at"])} - Ziel: {h(calories["goal_label"])} - Aktivität: {h(calories["activity_label"])}</p>
          </div>
          <span class="tag area-nutrition">{h(calories["target"])} kcal/Tag</span>
        </div>

        <div class="grid four" style="margin-top: 1rem;">
          <article class="stat-card">
            <span>Grundumsatz</span>
            <strong>{h(calories["bmr"])}</strong>
          </article>
          <article class="stat-card">
            <span>Erhaltung</span>
            <strong>{h(calories["maintenance"])}</strong>
          </article>
          <article class="stat-card">
            <span>Protein</span>
            <strong>{h(macros["protein_g"])} g</strong>
          </article>
          <article class="stat-card">
            <span>Kohlenhydrate / Fett</span>
            <strong>{h(macros["carbs_g"])} g / {h(macros["fat_g"])} g</strong>
          </article>
          <article class="stat-card">
            <span>Nächster Check-in</span>
            <strong>{h(next_checkin_at or "offen")}</strong>
          </article>
        </div>

        <section class="grid two" style="margin-top: 1rem;">
          <article class="card area-team">
            <div class="row">
              <div>
                <span class="tag area-team">Zielverfolgung</span>
                <h3 style="margin-top: 0.65rem;">{h(goal_tracking.get("goal_text", calories["goal_label"]))}</h3>
              </div>
              <span class="tag area-nutrition">{h(goal_tracking.get("metric_label", "Gewohnheiten"))}</span>
            </div>
            <div class="grid three" style="margin-top: 0.9rem;">
              <div class="mini-metric">
                <span>Rhythmus</span>
                <strong>{h(goal_tracking.get("tracking_label", "wöchentlich"))}</strong>
              </div>
              <div class="mini-metric">
                <span>Zielmarke</span>
                <strong>{h(target_label)}</strong>
              </div>
              <div class="mini-metric">
                <span>Kalorienbilanz</span>
                <strong>{h(calorie_delta_label)}</strong>
              </div>
            </div>
            <ul class="subtle" style="margin-top: 0.8rem;">{milestones}</ul>
          </article>

          <article class="card area-strength">
            <div class="row">
              <div>
                <span class="tag area-strength">Abenteuerfigur</span>
                <h3 style="margin-top: 0.65rem;">{h(adventure.get("character_name") or member_name(state, plan["member_id"]))}</h3>
              </div>
              <span class="tag area-team">{h(adventure.get("role_label", "Wächter"))}</span>
            </div>
            <p class="subtle" style="margin-top: 0.75rem;">{h(adventure.get("origin", "Der Alltag ist das Startgebiet."))}</p>
            <p class="subtle" style="margin-top: 0.45rem;">Hobbies: {h(adventure.get("hobbies", "noch offen"))}</p>
            <p class="subtle" style="margin-top: 0.45rem;">Alltag: {h(adventure.get("daily_life", lifestyle.get("work_style_label", "abwechslungsreich")))}</p>
            <p class="subtle" style="margin-top: 0.45rem;">Motivation: {h(adventure.get("motivation_label", "Story, Quests und Abenteuer"))}</p>
          </article>
        </section>

        <section class="grid two" style="margin-top: 1rem;">
          <div>
            <h2>Fokus & Vorschläge</h2>
            <article class="card area-strength">
              <div class="row">
                <div>
                  <span class="tag area-strength">Trainingsfokus</span>
                  <h3 style="margin-top: 0.65rem;">{h(training_focus.get("label", "Ausgewogen stärker werden"))}</h3>
                </div>
              </div>
              <div class="row" style="justify-content: flex-start; margin-top: 0.75rem;">{focus_area_tags or '<span class="meta">Ganzkörper</span>'}</div>
            </article>
            <div class="list" style="margin-top: 0.8rem;">{focus_cards}</div>
          </div>
          <div>
            <h2>Verletzungen & Sicherheit</h2>
            <div class="list">{injury_cards}</div>
          </div>
        </section>

        <section class="grid two" style="margin-top: 1rem;">
          <div>
            <h2>Check-ins</h2>
            <div class="list">{checkpoints or '<article class="card"><p class="subtle">Nach dem nächsten Fragebogen entstehen Check-ins.</p></article>'}</div>
          </div>
          <div>
            <h2>Progression</h2>
            <div class="list">{progression_cards}</div>
          </div>
        </section>

        <section class="grid two" style="margin-top: 1rem;">
          <div>
            <h2>Trainingsplan</h2>
            <div class="list">{training}</div>
          </div>
          <div>
            <h2>Regeneration</h2>
            <div class="list">{regeneration or '<article class="card"><p class="subtle">Regeneration wird beim nächsten Plan automatisch eingeplant.</p></article>'}</div>
          </div>
        </section>

        <section class="grid" style="margin-top: 1rem;">
          <div>
            <h2>Ernährungsplan</h2>
            <div class="grid two">{nutrition}</div>
          </div>
        </section>

        <div class="card" style="margin-top: 1rem;">
          <h3>Hinweise</h3>
          <ul class="subtle">{notes}</ul>
        </div>
      </article>
    """


def render_plan_collection(state: dict) -> str:
    plans = state.get("generated_plans", {})
    if not plans:
        return """
          <article class="card">
            <h3>Noch kein Plan vorhanden</h3>
            <p class="subtle">Füllt zuerst den Fragebogen aus. Danach erscheinen Kalorienbedarf, Trainingsplan und Ernährungsplan hier.</p>
          </article>
        """

    ordered = []
    member_ids = {member["id"] for member in state["members"]}
    for member_id, plan in plans.items():
        if member_id in member_ids:
            ordered.append(render_generated_plan(state, plan))
    return "".join(ordered)


def questionnaire_link(member_id: str) -> str:
    return f"/fragebogen?member_id={urllib.parse.quote(member_id)}"


def render_questionnaire_status_cards(state: dict, only_due: bool = False) -> str:
    cards = []
    for member in state["members"]:
        status = questionnaire_status(state, member["id"])
        if only_due and not status["is_due"]:
            continue
        area = "area-nutrition" if status["is_due"] else "area-team"
        action_href = questionnaire_link(member["id"]) if status["is_due"] else "/fitnessplan"
        cards.append(
            f"""
            <article class="card {area}">
              <div class="row">
                <div>
                  <span class="tag {area}">{h(status["label"])}</span>
                  <h3 style="margin-top: 0.65rem;">{h(member["name"])}</h3>
                </div>
                <span class="meta">nächster Termin: {h(status["next_due_at"])}</span>
              </div>
              <p class="subtle" style="margin-top: 0.75rem;">{h(status["message"])}</p>
              <a class="button blue" href="{h(action_href)}" style="margin-top: 0.85rem;">{h(status["button_label"])}</a>
            </article>
            """
        )
    if not cards:
        return ""
    return "".join(cards)


def render_dashboard_checkin_prompt(state: dict) -> str:
    cards = render_questionnaire_status_cards(state, only_due=True)
    if not cards:
        return ""
    return f"""
      <section class="panel" style="margin-bottom: 1rem;">
        <div class="row">
          <div>
            <h2>Anmeldung & 3-Monats-Check-in</h2>
            <p class="subtle">Der Fragebogen erscheint beim ersten Anmelden und danach alle 90 Tage, damit Trainingsplan und Ernährungsplan neu angepasst werden.</p>
          </div>
        </div>
        <div class="grid two" style="margin-top: 1rem;">{cards}</div>
      </section>
    """


def dashboard_member_id(state: dict, request: Request) -> str:
    member_ids = {member["id"] for member in state["members"]}
    session_member = current_member_id(request)
    if session_member in member_ids:
        return session_member
    return "bea" if "bea" in member_ids else state["members"][0]["id"]


def render_start_avatar_panel(state: dict, member_id: str, rpg: dict) -> str:
    avatar = avatar_profile_for_member(state, member_id)
    member = members_by_id(state).get(member_id, state["members"][0])
    character = rpg_character(member)
    status = questionnaire_status(state, member_id)
    plan = state.get("generated_plans", {}).get(member_id, {})
    plan_label = f'Plan Version {plan.get("plan_version", 1)}' if plan else "Noch kein Plan"
    bmi = avatar.get("bmi")
    bmi_label_text = f"BMI {bmi}" if bmi is not None else "BMI offen"
    return f"""
      <article class="panel">
        <div class="row">
          <div>
            <p class="eyebrow">Dein Charakter</p>
            <h2>{h(avatar.get("name", member_name(state, member_id)))}</h2>
            <p class="subtle">{h(character["title"])} - Level {h(character["level"])} - {h(plan_label)}</p>
          </div>
          <span class="tag {area_class(character["strongest_area"])}">{h(character["class_name"])}</span>
        </div>
        <div class="grid two" style="margin-top: 1rem; align-items: center;">
          <div>{render_avatar_svg(avatar)}</div>
          <div class="list">
            <article class="card area-team">
              <h3>Heute im Fokus</h3>
              <p class="subtle">{h(status["message"])}</p>
              <a class="button blue" href="{h(questionnaire_link(member_id) if status["is_due"] else "/fitnessplan")}" style="margin-top: 0.75rem;">{h(status["button_label"])}</a>
            </article>
            <article class="card area-strength">
              <h3>Körperwerte</h3>
              <p class="subtle">{h(avatar.get("height_cm", "-"))} cm · {h(avatar.get("weight_kg", "-"))} kg · {h(bmi_label_text)}</p>
              <p class="subtle">Körperbau: {h(avatar.get("body_label", "offen"))}</p>
            </article>
          </div>
        </div>
      </article>
    """


def render_start_daily_plan(state: dict, rpg: dict, member_id: str) -> str:
    completions = rpg.get("completed_quests", {})
    quests = rpg.get("daily_quests", [])
    done_count = sum(1 for quest in quests if rpg_completion_key(rpg["daily_date"], member_id, quest["id"]) in completions)
    total = max(1, len(quests))
    next_quest = next(
        (
            quest
            for quest in quests
            if rpg_completion_key(rpg["daily_date"], member_id, quest["id"]) not in completions
        ),
        quests[0] if quests else {},
    )
    assignments = [
        item
        for item in state.get("assignments", [])
        if item.get("to_member") == member_id and item.get("status") != "done"
    ][:2]
    assignment_cards = ""
    for item in assignments:
        category = item.get("category", "team")
        assignment_cards += f"""
        <article class="card {area_class(category)}">
          <span class="tag {area_class(category)}">{h(AREA_LABELS.get(category, "Teamgeist"))}</span>
          <h3 style="margin-top: 0.55rem;">{h(item.get("title", "Aufgabe"))}</h3>
          <p class="subtle">bis {h(item.get("due", "Diese Woche"))} · {h(item.get("xp", 0))} XP</p>
        </article>
        """
    boss = rpg.get("daily_boss", {})
    max_hp = max(1, int(boss.get("max_hp", 1)))
    hp = max(0, int(boss.get("hp", max_hp)))
    journey = health_journey_status(state, member_id)
    journey_lesson = journey["lesson"]
    if journey["is_complete"]:
        journey_title = "Gesundheitsreise abgeschlossen"
        journey_note = "Alle aktuellen Etappen sind erledigt."
    elif journey["locked"]:
        journey_title = journey_lesson["title"]
        journey_note = f'Nächste Lektion ab {journey["next_unlock_at"]}.'
    else:
        journey_title = journey_lesson["title"]
        journey_note = "Heute lesen und abschließen."
    return f"""
      <article class="panel">
        <div class="row">
          <div>
            <p class="eyebrow">Tagesplan</p>
            <h2>Heute erledigen</h2>
            <p class="subtle">{h(rpg.get("daily_date", ""))} · {h(done_count)} von {h(total)} Quests geschafft</p>
          </div>
          <a class="button blue" href="/abenteuer">Zum Abenteuer</a>
        </div>
        <div style="margin-top: 0.85rem;">{progress_bar(int((done_count / total) * 100), "Tagesquests")}</div>
        <div class="grid two" style="margin-top: 1rem;">
          <article class="card {area_class(next_quest.get("area", "team"))}">
            <span class="tag {area_class(next_quest.get("area", "team"))}">{h(AREA_LABELS.get(next_quest.get("area", "team"), "Teamgeist"))}</span>
            <h3 style="margin-top: 0.55rem;">{h(next_quest.get("title", "Tagesquest auswählen"))}</h3>
            <p class="subtle">{h(next_quest.get("description", "Heute kleine Schritte sammeln und dranbleiben."))}</p>
          </article>
          <article class="card area-strength">
            <span class="tag area-strength">Tagesboss</span>
            <h3 style="margin-top: 0.55rem;">{h(boss.get("name", "Boss"))}</h3>
            <p class="subtle">{h(hp)} / {h(max_hp)} LP · Schwäche: {h(boss.get("weakness", "Konstanz"))}</p>
          </article>
        </div>
        <div class="grid two" style="margin-top: 1rem;">
          {assignment_cards or '<article class="card"><h3>Keine offenen Zuweisungen</h3><p class="subtle">Heute zählt dein eigener Plan.</p></article>'}
          <article class="card area-team">
            <div class="row">
              <span class="tag area-team">Gesundheitsreise</span>
              <span class="meta">{h(journey["completed_count"])} / {h(journey["total"])}</span>
            </div>
            <h3 style="margin-top: 0.55rem;">{h(journey_title)}</h3>
            <p class="subtle">{h(journey_note)}</p>
            <a class="button secondary" href="/reise" style="margin-top: 0.75rem;">Zur Reise</a>
          </article>
        </div>
      </article>
    """


def render_start_nutrition_summary(state: dict, member_id: str) -> str:
    plan = state.get("generated_plans", {}).get(member_id)
    if not plan:
        return f"""
          <article class="panel">
            <div class="row">
              <div>
                <p class="eyebrow">Ernährung</p>
                <h2>Noch kein Ernährungsplan</h2>
                <p class="subtle">Der Check-in erstellt Kalorienziel, Makros und Mahlzeitenstruktur.</p>
              </div>
              <a class="button blue" href="{h(questionnaire_link(member_id))}">Check-in starten</a>
            </div>
          </article>
        """
    calories = plan["calories"]
    macros = plan["macros"]
    meals = "".join(
        f"""
        <article class="card area-nutrition">
          <h3>{h(item["title"])}</h3>
          <p><strong>{h(item["target"])}</strong></p>
          <p class="subtle">{h(item["details"])}</p>
        </article>
        """
        for item in plan.get("nutrition", [])[:3]
    )
    return f"""
      <article class="panel">
        <div class="row">
          <div>
            <p class="eyebrow">Ernährung</p>
            <h2>Heute essen</h2>
            <p class="subtle">{h(calories["target"])} kcal · Protein {h(macros["protein_g"])} g · Kohlenhydrate {h(macros["carbs_g"])} g · Fett {h(macros["fat_g"])} g</p>
          </div>
          <a class="button green" href="/nahrung">Mahlzeit tracken</a>
        </div>
        <div class="grid three" style="margin-top: 1rem;">{meals}</div>
      </article>
    """


def render_start_training_summary(state: dict, member_id: str) -> str:
    plan = state.get("generated_plans", {}).get(member_id)
    if not plan:
        return f"""
          <article class="panel">
            <div class="row">
              <div>
                <p class="eyebrow">Training</p>
                <h2>Noch kein Trainingsplan</h2>
                <p class="subtle">Der Check-in erstellt Kraft, Ausdauer, Regeneration und Progression.</p>
              </div>
              <a class="button blue" href="{h(questionnaire_link(member_id))}">Check-in starten</a>
            </div>
          </article>
        """
    training_cards = []
    for item in plan.get("training", [])[:2]:
        training_type = item.get("type", "Kraft")
        training_area = training_type_area(training_type)
        exercises = item.get("exercises", [])
        first_exercise = exercises[0] if exercises else {}
        training_cards.append(
            f"""
            <article class="card {area_class(training_area)}">
              <div class="row">
                <span class="tag {area_class(training_area)}">{h(training_type)}</span>
                <span class="meta">{h(item.get("duration", "heute"))}</span>
              </div>
              <h3 style="margin-top: 0.55rem;">{h(item.get("title", "Training"))}</h3>
              <p class="subtle">{h(item.get("details", ""))}</p>
              <p class="subtle" style="margin-top: 0.45rem;"><strong>Start:</strong> {h(first_exercise.get("name", "Übungen ansehen"))}</p>
            </article>
            """
        )
    progression = plan.get("progression", [{}])[0]
    return f"""
      <article class="panel">
        <div class="row">
          <div>
            <p class="eyebrow">Training</p>
            <h2>Heute bewegen</h2>
            <p class="subtle">{h(len(plan.get("training", [])))} Trainingseinheiten pro Woche · {h(len(plan.get("regeneration", [])))} Regenerationsblöcke</p>
          </div>
          <a class="button blue" href="/fitnessplan">Plan öffnen</a>
        </div>
        <div class="grid two" style="margin-top: 1rem;">{"".join(training_cards)}</div>
        <article class="card area-team" style="margin-top: 1rem;">
          <h3>{h(progression.get("title", "Progression"))}</h3>
          <p class="subtle">{h(progression.get("details", "Sauber bewegen, Belastung dokumentieren und langsam steigern."))}</p>
        </article>
      </article>
    """


def render_journey_map(status: dict) -> str:
    completed_count = int(status["completed_count"])
    cards = []
    for index, lesson in enumerate(HEALTH_JOURNEY_LESSONS):
        if index < completed_count:
            label = "Abgeschlossen"
            tag_class = "area-team"
        elif index == completed_count and status["locked"]:
            label = f'ab {status["next_unlock_at"]}'
            tag_class = "area-team"
        elif index == completed_count:
            label = "Heute offen"
            tag_class = area_class(lesson["area"])
        else:
            label = "Gesperrt"
            tag_class = "area-team"
        cards.append(
            f"""
            <article class="card {area_class(lesson["area"])}">
              <div class="row">
                <span class="tag {area_class(lesson["area"])}">Tag {h(index + 1)}</span>
                <span class="tag {tag_class}">{h(label)}</span>
              </div>
              <h3 style="margin-top: 0.55rem;">{h(lesson["title"])}</h3>
              <p class="subtle">{h(lesson["summary"])}</p>
            </article>
            """
        )
    return "".join(cards)


def render_journey_history(status: dict) -> str:
    history = list(reversed(status.get("history", [])[-5:]))
    if not history:
        return '<article class="card"><p class="subtle">Noch keine Lektion abgeschlossen. Heute beginnt die Reise.</p></article>'
    return "".join(
        f"""
        <article class="card area-team">
          <div class="row">
            <div>
              <h3>{h(item["lesson"]["title"])}</h3>
              <p class="subtle">abgeschlossen am {h(item["completed_at"])}</p>
            </div>
            <span class="tag area-team">+{h(item["xp"])} XP</span>
          </div>
        </article>
        """
        for item in history
    )


def render_journey_lesson(status: dict) -> str:
    lesson = status["lesson"]
    if status["is_complete"]:
        return """
          <article class="panel">
            <p class="eyebrow">Reise abgeschlossen</p>
            <h2>Alle aktuellen Gesundheitsthemen sind gelesen</h2>
            <p class="subtle">Neue Etappen können später ergänzt werden. Bis dahin zählt Wiederholung im Alltag.</p>
          </article>
        """

    if status["locked"]:
        return f"""
          <article class="panel">
            <p class="eyebrow">Nächste Etappe</p>
            <h2>{h(lesson["title"])}</h2>
            <p class="subtle">Du hast heute bereits eine Lektion abgeschlossen. Diese Etappe wird am {h(status["next_unlock_at"])} freigeschaltet.</p>
            <div style="margin-top: 1rem;">{progress_bar(status["progress_percent"], "Reisefortschritt")}</div>
          </article>
        """

    body = "".join(f"<p>{h(paragraph)}</p>" for paragraph in lesson["body"])
    takeaways = "".join(f"<li>{h(item)}</li>" for item in lesson["takeaways"])
    return f"""
      <article class="panel">
        <div class="row">
          <div>
            <p class="eyebrow">Heutige Gesundheitsreise</p>
            <h2>{h(lesson["title"])}</h2>
            <p class="subtle">{h(lesson["read_minutes"])} Minuten Lesen · +{h(lesson["xp"])} XP · {h(AREA_LABELS[lesson["area"]])}</p>
          </div>
          <span class="tag {area_class(lesson["area"])}">Tag {h(status["completed_count"] + 1)} / {h(status["total"])}</span>
        </div>
        <div class="list" style="margin-top: 1rem;">
          <article class="card {area_class(lesson["area"])}">
            <h3>Worum es geht</h3>
            <p class="subtle">{h(lesson["summary"])}</p>
          </article>
          <article class="card">
            <h3>Lektion</h3>
            <div class="subtle list">{body}</div>
          </article>
          <article class="card area-team">
            <h3>Merken</h3>
            <ul class="cue-list">{takeaways}</ul>
          </article>
          <article class="card area-nutrition">
            <h3>Heute anwenden</h3>
            <p class="subtle">{h(lesson["action"])}</p>
          </article>
        </div>
        <form data-api-form data-endpoint="/api/journey/complete" style="margin-top: 1rem;">
          <input type="hidden" name="lesson_id" value="{h(lesson["id"])}">
          <button class="button blue" type="submit">Gelesen und abgeschlossen</button>
        </form>
      </article>
    """


def render_login_page(error: str = "", next_url: str = "/") -> str:
    state = load_state()
    member_options = "\n".join(
        f'<option value="{h(member["id"])}">{h(member["name"])}{" - Passwort erstellen" if not password_is_configured(state, member["id"]) else ""}</option>'
        for member in state["members"]
    )
    error_html = f'<p class="login-error" role="alert">{h(error)}</p>' if error else ""
    return f"""
      <!doctype html>
      <html lang="de">
        <head>
          <meta charset="utf-8">
          <meta name="viewport" content="width=device-width, initial-scale=1">
          <title>Bea Anmeldung</title>
          <style>
            :root {{
              color-scheme: light;
              --ink: #172033;
              --muted: #64748b;
              --line: #d8e1ef;
              --blue: #2563eb;
              --green: #16a34a;
              --gold: #f59e0b;
              --paper: #f8fbff;
            }}
            * {{ box-sizing: border-box; }}
            body {{
              margin: 0;
              min-height: 100vh;
              display: grid;
              place-items: center;
              font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
              background:
                radial-gradient(circle at top left, rgb(37 99 235 / 18%), transparent 34rem),
                radial-gradient(circle at bottom right, rgb(22 163 74 / 16%), transparent 30rem),
                var(--paper);
              color: var(--ink);
              padding: 1rem;
            }}
            main {{
              width: min(100%, 440px);
              background: white;
              border: 1px solid var(--line);
              border-radius: 8px;
              box-shadow: 0 24px 70px rgb(23 32 51 / 14%);
              padding: 1.25rem;
            }}
            .brand {{ display: flex; align-items: center; gap: 0.55rem; margin-bottom: 1rem; font-weight: 900; font-size: 1.3rem; }}
            .brand-mark {{ display: grid; place-items: center; width: 38px; height: 38px; border-radius: 8px; background: #0f172a; color: white; }}
            h1 {{ margin: 0; font-size: 1.55rem; }}
            p {{ color: var(--muted); line-height: 1.55; }}
            form {{ display: grid; gap: 0.85rem; margin-top: 1rem; }}
            label {{ display: grid; gap: 0.35rem; color: var(--ink); font-weight: 750; }}
            input, select {{
              width: 100%;
              min-height: 44px;
              border: 1px solid var(--line);
              border-radius: 8px;
              padding: 0.65rem 0.75rem;
              font: inherit;
            }}
            button {{
              min-height: 46px;
              border: 0;
              border-radius: 8px;
              background: linear-gradient(135deg, var(--blue), var(--green));
              color: white;
              font-weight: 900;
              cursor: pointer;
            }}
            .hint {{
              border-left: 4px solid var(--gold);
              background: #fff7ed;
              padding: 0.75rem;
              border-radius: 8px;
              color: #7c2d12;
              margin-top: 1rem;
            }}
            .login-error {{
              border-left: 4px solid #dc2626;
              background: #fef2f2;
              color: #991b1b;
              padding: 0.75rem;
              border-radius: 8px;
            }}
          </style>
        </head>
        <body>
          <main>
            <div class="brand"><span class="brand-mark">B</span><span>ea</span></div>
            <h1>Anmelden</h1>
            <p>Wähle dein Mitglied aus. Beim ersten Anmelden erstellst du ein persönliches Passwort; danach bleiben Daten und Fotos hinter deiner Anmeldung geschützt.</p>
            {error_html}
            <form method="post" action="/api/login">
              <input type="hidden" name="next" value="{h(safe_next_url(next_url))}">
              <label>
                Mitglied
                <select name="member_id">{member_options}</select>
              </label>
              <label>
                Passwort
                <input name="password" type="password" autocomplete="current-password" required minlength="12">
              </label>
              <label>
                Passwort bestätigen, nur beim ersten Anmelden
                <input name="password_confirm" type="password" autocomplete="new-password" minlength="12">
              </label>
              <button type="submit">Sicher anmelden</button>
            </form>
            <p class="hint">Sicheres Passwort: mindestens 12 Zeichen und mehrere Arten von Zeichen. Passwörter werden nur als Salt + Hash gespeichert.</p>
          </main>
        </body>
      </html>
    """


@app.get("/login", response_class=HTMLResponse)
def login_page(next: str = "/") -> str:
    return render_login_page(next_url=next)


@app.post("/api/login")
async def api_login(request: Request):
    payload = parse_form_body(await request.body())
    state = load_state()
    member_id = str(payload.get("member_id") or "")
    password = str(payload.get("password") or "")
    password_confirm = str(payload.get("password_confirm") or "")
    next_url = safe_next_url(str(payload.get("next") or "/"))

    try:
        if not password_is_configured(state, member_id):
            if password != password_confirm:
                raise ValueError("Bitte Passwort beim ersten Anmelden identisch bestätigen.")
            set_member_password(state, member_id, password)
            save_state(state)
        elif not verify_member_password(state, member_id, password):
            raise ValueError("Mitglied oder Passwort stimmt nicht.")
    except ValueError as exc:
        return HTMLResponse(render_login_page(str(exc), next_url), status_code=400)

    response = RedirectResponse(next_url, status_code=303)
    set_session_cookie(response, request, create_session(member_id))
    return response


@app.post("/logout")
async def logout(request: Request):
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        SESSIONS.pop(token, None)
    response = RedirectResponse("/login", status_code=303)
    clear_session_cookie(response, request)
    return response


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request) -> str:
    state = load_state()
    rpg = ensure_rpg_state(state)
    member_id = dashboard_member_id(state, request)
    member_label = member_name(state, member_id)
    totals = team_totals(state)
    level_cards = "".join(level_meter(AREA_LABELS[area], totals[area], area) for area in AREAS)
    challenges = "".join(render_challenge_card(state, challenge) for challenge in state["challenges"][:3])
    plan_hint = render_dashboard_checkin_prompt(state)
    motivations = "".join(
        f"""
        <article class="card">
          <p>{h(item["message"])}</p>
          <p class="subtle">{h(member_name(state, item["from_member"]))} an {h(member_name(state, item["to_member"]))}</p>
        </article>
        """
        for item in state["motivations"][:3]
    )

    body = f"""
      <section class="page-heading">
        <div>
          <p class="eyebrow">Startseite</p>
          <h1>Hallo {h(member_label)}</h1>
        </div>
        <div class="quick-actions" aria-label="Schnellaktionen">
          <a class="quick-link gold" href="/abenteuer">Abenteuer</a>
          <a class="quick-link gold" href="/reise">Reise lernen</a>
          <a class="quick-link red" href="/avatar">Avatar bauen</a>
          <a class="quick-link blue" href="/fortschritt">Fortschritt</a>
          <a class="quick-link green" href="/gruppen">Gruppen</a>
          <a class="quick-link blue" href="/sport">Sport erfassen</a>
          <a class="quick-link gold" href="/mindset">Mindset üben</a>
          <a class="quick-link green" href="/nahrung">Mahlzeit tracken</a>
          <a class="quick-link gold" href="/challenges">Challenge ansehen</a>
          <a class="quick-link red" href="/fotos">Fotovergleich</a>
        </div>
      </section>

      {plan_hint}

      <section class="grid two">
        {render_start_avatar_panel(state, member_id, rpg)}
        {render_start_daily_plan(state, rpg, member_id)}
      </section>

      <section class="grid" style="margin-top: 1rem;">
        {render_start_nutrition_summary(state, member_id)}
      </section>

      <section class="grid" style="margin-top: 1rem;">
        {render_start_training_summary(state, member_id)}
      </section>

      <section class="grid four" style="margin-top: 1rem;">
        {stat_cards(state)}
      </section>
      <section class="grid two" style="margin-top: 1rem;">
        <div class="panel">
          <h2>Rangliste</h2>
          {render_leaderboard(state, 5)}
        </div>
        <div class="panel">
          <h2>Team-Level</h2>
          <div class="grid two">
            {level_cards}
          </div>
        </div>
      </section>

      <section class="grid two" style="margin-top: 1rem;">
        <div class="panel">
          <h2>Aktive Challenges</h2>
          <div class="list">{challenges}</div>
        </div>
        <div class="panel">
          <h2>Motivation</h2>
          <div class="list">{motivations}</div>
        </div>
      </section>
    """
    return render_layout("/", "Dashboard", body)


@app.get("/abenteuer", response_class=HTMLResponse)
def adventure_page() -> str:
    state = load_state()
    rpg = ensure_rpg_state(state)
    quest_cards = "".join(render_daily_quest_card(state, rpg, quest) for quest in rpg["daily_quests"])
    completed_today = sum(
        1
        for key in rpg.get("completed_quests", {})
        if key.startswith(f'{rpg["daily_date"]}:')
    )
    total_daily_slots = len(state["members"]) * len(rpg["daily_quests"])

    body = f"""
      <section class="page-heading">
        <div>
          <p class="eyebrow">Rollenspiel</p>
          <h1>Charakter-Abenteuer</h1>
        </div>
        <p class="subtle">Dein Charakter bist du selbst: Training, Nahrung und Teamgeist werden zu Quests, Schaden und Leveln.</p>
      </section>

      <section class="grid four">
        <article class="stat-card">
          <span>Datum</span>
          <strong>{h(rpg["daily_date"])}</strong>
        </article>
        <article class="stat-card">
          <span>Quests heute</span>
          <strong>{h(completed_today)} / {h(total_daily_slots)}</strong>
        </article>
        <article class="stat-card">
          <span>Tagesboss LP</span>
          <strong>{h(rpg["daily_boss"]["hp"])}</strong>
        </article>
        <article class="stat-card">
          <span>Wochenboss LP</span>
          <strong>{h(rpg["weekly_boss"]["hp"])}</strong>
        </article>
      </section>

      <section class="grid two" style="margin-top: 1rem;">
        {render_rpg_boss_card(rpg["daily_boss"])}
        {render_rpg_boss_card(rpg["weekly_boss"])}
      </section>

      <section class="grid two" style="margin-top: 1rem;">
        <div class="panel">
          <h2>Tägliche Aufgaben</h2>
          <div class="list">{quest_cards}</div>
        </div>
        <div class="panel">
          <h2>Charaktere</h2>
          <div class="list">{render_character_cards(state)}</div>
        </div>
      </section>

      <section class="panel" style="margin-top: 1rem;">
        <h2>Kampfprotokoll</h2>
        <div class="list">{render_battle_log(state, rpg)}</div>
      </section>
    """
    return render_layout("/abenteuer", "Abenteuer", body)


@app.get("/reise", response_class=HTMLResponse)
def journey_page(request: Request) -> str:
    state = load_state()
    member_id = dashboard_member_id(state, request)
    member_label = member_name(state, member_id)
    status = health_journey_status(state, member_id)
    lesson = status["lesson"]
    current_title = "Reise abgeschlossen" if status["is_complete"] else lesson["title"]
    unlock_label = (
        "Alle Etappen erledigt"
        if status["is_complete"]
        else f'ab {status["next_unlock_at"]}' if status["locked"] else "heute verfügbar"
    )
    xp_label = "-" if status["is_complete"] else f'+{lesson["xp"]} XP'

    body = f"""
      <section class="page-heading">
        <div>
          <p class="eyebrow">Gesundheitsreise</p>
          <h1>Täglich etwas Neues lernen</h1>
        </div>
        <p class="subtle">Eine kurze Etappe pro Tag. Nach dem Abschluss wird die nächste Lektion erst am Folgetag freigeschaltet.</p>
      </section>

      <section class="grid four">
        <article class="stat-card">
          <span>Teilnehmer</span>
          <strong>{h(member_label)}</strong>
        </article>
        <article class="stat-card">
          <span>Fortschritt</span>
          <strong>{h(status["completed_count"])} / {h(status["total"])}</strong>
        </article>
        <article class="stat-card">
          <span>Aktuelle Etappe</span>
          <strong>{h(current_title)}</strong>
        </article>
        <article class="stat-card">
          <span>Freischaltung</span>
          <strong>{h(unlock_label)}</strong>
        </article>
      </section>

      <section class="panel" style="margin-top: 1rem;">
        <div class="row">
          <div>
            <h2>Reisefortschritt</h2>
            <p class="subtle">Gesundheitswissen wird als tägliche Quest behandelt und stärkt deinen Charakter.</p>
          </div>
          <span class="tag area-team">{h(xp_label)}</span>
        </div>
        <div style="margin-top: 1rem;">{progress_bar(status["progress_percent"], "Gesundheitsreise")}</div>
      </section>

      <section class="grid two" style="margin-top: 1rem;">
        {render_journey_lesson(status)}
        <article class="panel">
          <h2>Letzte Etappen</h2>
          <div class="list" style="margin-top: 1rem;">{render_journey_history(status)}</div>
        </article>
      </section>

      <section class="panel" style="margin-top: 1rem;">
        <h2>Reisekarte</h2>
        <div class="grid two" style="margin-top: 1rem;">{render_journey_map(status)}</div>
      </section>
    """
    return render_layout("/reise", "Reise", body)


@app.get("/avatar", response_class=HTMLResponse)
def avatar_page() -> str:
    state = load_state()
    profiles = [avatar_profile_for_member(state, member["id"]) for member in state["members"]]
    default_profile = avatar_profile_for_member(state, "bea")
    avatar_cards = "".join(render_avatar_card(profile) for profile in profiles)
    default_bmi = default_profile.get("bmi")

    body = f"""
      <section class="page-heading">
        <div>
          <p class="eyebrow">Avatar Studio</p>
          <h1>Dein Charakter</h1>
        </div>
        <p class="subtle">Masse, Frisur, Kleidung und private Ganzkörperbilder formen deinen Charakter.</p>
      </section>

      <section class="grid two">
        <div class="panel">
          <h2>Avatar-Galerie</h2>
          <div class="grid two">{avatar_cards}</div>
        </div>
        <div class="panel">
          <h2>Avatar erstellen</h2>
          <form class="form-grid" id="avatar-form">
            <label>
              Mitglied
              <select name="member_id">{render_member_options(state, "bea")}</select>
            </label>
            <label>
              Foto-PIN
              <input name="pin" type="password" autocomplete="current-password">
            </label>
            <div class="form-section-title">
              <h3>Wichtige Masse</h3>
              <p class="subtle">Diese Werte bestimmen Körperform, Proportionen und BMI des Avatars.</p>
            </div>
            <label>
              Größe in cm
              <input name="height_cm" id="avatar-height" type="number" min="120" max="230" value="{h(default_profile["height_cm"])}">
            </label>
            <label>
              Gewicht in kg
              <input name="weight_kg" id="avatar-weight" type="number" min="35" max="250" value="{h(default_profile.get("weight_kg", 70))}">
            </label>
            <label>
              BMI
              <input id="avatar-bmi" type="text" value="{h(default_bmi if default_bmi is not None else "-")}" readonly>
            </label>
            <label>
              Hals in cm
              <input name="neck_cm" type="number" min="25" max="60" value="{h(default_profile.get("neck_cm", 36))}">
            </label>
            <label>
              Schulter in cm
              <input name="shoulder_width" type="number" min="60" max="140" value="{h(default_profile["shoulder_width"])}">
            </label>
            <label>
              Brust in cm
              <input name="chest_cm" type="number" min="60" max="180" value="{h(default_profile.get("chest_cm", 96))}">
            </label>
            <label>
              Taille in cm
              <input name="waist_width" type="number" min="55" max="150" value="{h(default_profile["waist_width"])}">
            </label>
            <label>
              Hüfte in cm
              <input name="hip_width" type="number" min="60" max="150" value="{h(default_profile["hip_width"])}">
            </label>
            <label>
              Oberschenkel links in cm
              <input name="thigh_left_cm" type="number" min="35" max="100" value="{h(default_profile.get("thigh_left_cm", 56))}">
            </label>
            <label>
              Oberschenkel rechts in cm
              <input name="thigh_right_cm" type="number" min="35" max="100" value="{h(default_profile.get("thigh_right_cm", 56))}">
            </label>

            <div class="form-section-title">
              <h3>Stil</h3>
              <p class="subtle">Frisur, Kleidung und Farben machen den Avatar persönlicher.</p>
            </div>
            <label>
              Frisur
              <select name="hair_style">{render_options(AVATAR_HAIR_STYLES, str(default_profile.get("hair_style", "short")))}</select>
            </label>
            <label>
              Kleidung
              <select name="clothing_style">{render_options(AVATAR_CLOTHING_STYLES, str(default_profile.get("clothing_style", "training")))}</select>
            </label>
            <label>
              Frontbild
              <input name="front_photo_file" type="file" accept="image/jpeg,image/png,image/webp">
            </label>
            <label class="full">
              Seitenbild
              <input name="side_photo_file" type="file" accept="image/jpeg,image/png,image/webp">
            </label>

            <label>
              Muskel-Feintuning <span id="avatar-muscle-value"></span>
              <input name="muscle" type="range" min="0" max="100" value="{h(default_profile["muscle"])}" data-output="#avatar-muscle-value">
            </label>
            <label>
              Form-Feintuning <span id="avatar-fat-value"></span>
              <input name="body_fat" type="range" min="0" max="100" value="{h(default_profile["body_fat"])}" data-output="#avatar-fat-value">
            </label>

            <div class="swatch-row full">
              <label>
                Haut
                <input name="skin_color" type="color" value="{h(default_profile["skin_color"])}">
              </label>
              <label>
                Haare
                <input name="hair_color" type="color" value="{h(default_profile["hair_color"])}">
              </label>
              <label>
                Outfit
                <input name="outfit_color" type="color" value="{h(default_profile["outfit_color"])}">
              </label>
            </div>

            <button class="button blue full" type="submit">Avatar speichern</button>
          </form>
        </div>
      </section>
    """
    return render_layout("/avatar", "Avatar", body)


@app.get("/fortschritt", response_class=HTMLResponse)
def progress_page(member_id: str = "bea") -> str:
    state = load_state()
    members = {member["id"]: member for member in state["members"]}
    if member_id not in members:
        member_id = "bea" if "bea" in members else state["members"][0]["id"]
    member = members[member_id]
    profile = state.get("profiles", {}).get(member_id, {})
    weight = latest_weight_for_member(state, member_id)
    height = profile.get("height_cm")
    bmi = bmi_value(weight, height)
    balance_7 = progress_activity_balance(state, member_id, 7)
    balance_30 = progress_activity_balance(state, member_id, 30)
    all_member_cards = "".join(render_progress_member_card(state, item) for item in leaderboard(state))
    weight_form_value = f"{weight:.1f}" if weight else "70.0"

    body = f"""
      <section class="page-heading">
        <div>
          <p class="eyebrow">Fortschritt</p>
          <h1>Bilanz & Ausblick</h1>
        </div>
        <p class="subtle">Vergangene Aktivität, BMI, Gewicht und Plan-Projektion auf einer Seite.</p>
      </section>

      <section class="grid four">
        <article class="stat-card">
          <span>Mitglied</span>
          <strong>{h(member["name"])}</strong>
        </article>
        <article class="stat-card">
          <span>Gewicht</span>
          <strong>{h(f"{weight:.1f} kg" if weight else "offen")}</strong>
        </article>
        <article class="stat-card">
          <span>BMI</span>
          <strong>{h(bmi if bmi is not None else "-")}</strong>
        </article>
        <article class="stat-card">
          <span>BMI-Einordnung</span>
          <strong>{h(bmi_label(bmi))}</strong>
        </article>
      </section>

      <section class="grid two" style="margin-top: 1rem;">
        <div class="panel">
          <div class="row">
            <div>
              <h2>Mitglied auswählen</h2>
              <p class="subtle">Die Bilanz wird für die gewählte Person berechnet.</p>
            </div>
          </div>
          <form class="form-grid" action="/fortschritt" method="get">
            <label class="full">
              Mitglied
              <select name="member_id">{render_member_options(state, member_id)}</select>
            </label>
            <button class="button blue full" type="submit">Bilanz anzeigen</button>
          </form>
        </div>

        <div class="panel">
          <h2>Gewicht eintragen</h2>
          <form class="form-grid" data-api-form data-endpoint="/api/weight">
            <label>
              Mitglied
              <select name="member_id">{render_member_options(state, member_id)}</select>
            </label>
            <label>
              Datum
              <input name="entry_date" type="date" value="{h(date.today().isoformat())}">
            </label>
            <label>
              Gewicht in kg
              <input name="weight_kg" type="number" min="35" max="250" step="0.1" value="{h(weight_form_value)}">
            </label>
            <label>
              Notiz
              <input name="note" placeholder="z.B. morgens, nach Ruhetag">
            </label>
            <button class="button full" type="submit">Gewicht speichern</button>
          </form>
        </div>
      </section>

      <section class="grid two" style="margin-top: 1rem;">
        <div class="panel">
          <h2>Bilanz letzte 7 Tage</h2>
          {render_balance_table(balance_7)}
        </div>
        <div class="panel">
          <h2>Bilanz letzte 30 Tage</h2>
          {render_balance_table(balance_30)}
        </div>
      </section>

      <section class="grid two" style="margin-top: 1rem;">
        <div class="panel">
          <h2>Zielverfolgung</h2>
          {render_goal_tracking_summary(state, member_id)}
        </div>
        <div class="panel">
          <h2>Plan-Ausblick</h2>
          {render_plan_outlook(state, member_id)}
        </div>
      </section>

      <section class="grid" style="margin-top: 1rem;">
        <div class="panel">
          <h2>Gewichtsverlauf</h2>
          {render_weight_history(state, member_id)}
          <p class="subtle" style="margin-top: 0.75rem;">BMI und Ausblick sind Orientierung und ersetzen keine medizinische Beratung.</p>
        </div>
      </section>

      <section class="panel" style="margin-top: 1rem;">
        <h2>Team-Übersicht</h2>
        <div class="grid two">{all_member_cards}</div>
      </section>
    """
    return render_layout("/fortschritt", "Fortschritt", body)


@app.get("/fragebogen", response_class=HTMLResponse)
def questionnaire_page(member_id: str = "") -> str:
    state = load_state()
    member_ids = {member["id"] for member in state["members"]}
    due_member_ids = [member["id"] for member in state["members"] if questionnaire_status(state, member["id"])["is_due"]]
    selected_member_id = member_id if member_id in member_ids else due_member_ids[0] if due_member_ids else "bea"
    if selected_member_id not in member_ids:
        selected_member_id = state["members"][0]["id"]
    profile = state.get("profiles", {}).get(selected_member_id, {})
    status = questionnaire_status(state, selected_member_id)
    status_cards = render_questionnaire_status_cards(state)
    form_title = "Anmeldung" if status["state"] == "onboarding" else "3-Monats-Check-in" if status["is_due"] else "Plan aktualisieren"
    submit_label = "Startplan erstellen" if status["state"] == "onboarding" else "Check-in speichern und Plan anpassen"

    def profile_value(key: str, default: object = "") -> object:
        value = profile.get(key)
        return default if value in (None, "") else value

    def profile_text(key: str) -> str:
        return str(profile.get(key) or "")

    sex_options = {"female": "weiblich", "male": "männlich", "neutral": "neutral / Durchschnitt"}
    experience_options = {
        "beginner": "Einsteiger",
        "intermediate": "Fortgeschritten",
        "advanced": "Sehr erfahren",
    }
    target_date_default = str(profile_value("target_date", (date.today() + timedelta(days=90)).isoformat()))
    target_weight_value = profile_value("target_weight_kg", "")
    body = f"""
      <section class="page-heading">
        <div>
          <p class="eyebrow">Onboarding & Quartals-Check-in</p>
          <h1>{h(form_title)}</h1>
        </div>
        <p class="subtle">Der Fragebogen erscheint beim ersten Anmelden und danach alle 90 Tage. Aus den Antworten werden Trainingsplan, Ernährungsplan und Progression neu berechnet.</p>
      </section>

      <section class="panel" style="margin-bottom: 1rem;">
        <div class="row">
          <div>
            <h2>Check-in Status</h2>
            <p class="subtle">Fällige Mitglieder beantworten den Check-in; alle anderen behalten ihren aktuellen Plan bis zum nächsten Termin.</p>
          </div>
        </div>
        <div class="grid two" style="margin-top: 1rem;">{status_cards}</div>
      </section>

      <section class="grid two">
        <div class="panel">
          <h2>{h(form_title)} für {h(member_name(state, selected_member_id))}</h2>
          <form class="form-grid" data-api-form data-endpoint="/api/questionnaire">
            <div class="form-section-title">
              <h3>Person & Ziel</h3>
              <p class="subtle">Hier entsteht der Hauptauftrag für dein Abenteuer.</p>
            </div>
            <label>
              Mitglied
              <select name="member_id">{render_member_options(state, selected_member_id)}</select>
            </label>
            <label>
              Ziel
              <select name="goal">{render_options(GOAL_LABELS, str(profile_value("goal", "maintain")))}</select>
            </label>
            <label>
              Alter
              <input name="age" type="number" min="13" max="90" value="{h(profile_value("age", 30))}">
            </label>
            <label>
              Formel
              <select name="sex">{render_options(sex_options, str(profile_value("sex", "neutral")))}</select>
            </label>
            <label>
              Körpergröße in cm
              <input name="height_cm" type="number" min="120" max="230" value="{h(profile_value("height_cm", 170))}">
            </label>
            <label>
              Gewicht in kg
              <input name="weight_kg" type="number" min="35" max="250" step="0.1" value="{h(profile_value("weight_kg", 70))}">
            </label>
            <label class="full">
              Hauptziel als Satz
              <textarea name="primary_goal_text" placeholder="z.B. Ich will in 12 Wochen fitter, leichter und konsequenter trainieren.">{h(profile_text("primary_goal_text"))}</textarea>
            </label>
            <label>
              Zielmessung
              <select name="goal_metric">{render_options(GOAL_METRIC_LABELS, str(profile_value("goal_metric", "habit")))}</select>
            </label>
            <label>
              Trackingrhythmus
              <select name="tracking_frequency">{render_options(TRACKING_FREQUENCY_LABELS, str(profile_value("tracking_frequency", "weekly")))}</select>
            </label>
            <label>
              Zielgewicht in kg
              <input name="target_weight_kg" type="number" min="35" max="250" step="0.1" value="{h(target_weight_value)}" placeholder="optional">
            </label>
            <label>
              Zieldatum
              <input name="target_date" type="date" value="{h(target_date_default)}">
            </label>

            <div class="form-section-title">
              <h3>Alltag, Arbeit & Hobbies</h3>
              <p class="subtle">Der Plan soll zu deinem echten Tagesablauf passen.</p>
            </div>
            <label>
              Aktivitätslevel
              <select name="activity">{render_options(ACTIVITY_LABELS, str(profile_value("activity", "moderate")))}</select>
            </label>
            <label>
              Arbeitsalltag
              <select name="work_style">{render_options(WORK_STYLE_LABELS, str(profile_value("work_style", "mixed")))}</select>
            </label>
            <label>
              Arbeitsrhythmus
              <input name="work_schedule" value="{h(profile_text("work_schedule"))}" placeholder="z.B. 9-17 Uhr, Schicht, viele Termine">
            </label>
            <label>
              Schritte pro Tag
              <input name="daily_steps" type="number" min="0" max="40000" value="{h(profile_value("daily_steps", 6000))}">
            </label>
            <label class="full">
              Hobbies & Interessen
              <textarea name="hobbies" placeholder="z.B. Wandern, Tanzen, Gaming, Kochen, Garten, Teamsport">{h(profile_text("hobbies"))}</textarea>
            </label>

            <div class="form-section-title">
              <h3>Training & Regeneration</h3>
              <p class="subtle">Belastung und Erholung werden gemeinsam geplant.</p>
            </div>
            <label>
              Trainingstage pro Woche
              <input name="workouts_per_week" type="number" min="2" max="6" value="{h(profile_value("workouts_per_week", 4))}">
            </label>
            <label>
              Trainingsort
              <select name="training_location">{render_options(TRAINING_LABELS, str(profile_value("training_location", "mixed")))}</select>
            </label>
            <label>
              Ausdauer
              <select name="endurance_preference">{render_options(ENDURANCE_LABELS, str(profile_value("endurance_preference", "mixed")))}</select>
            </label>
            <label>
              Trainingserfahrung
              <select name="experience">{render_options(experience_options, str(profile_value("experience", "beginner")))}</select>
            </label>
            <label>
              Trainingsfokus
              <select name="training_focus">{render_options(TRAINING_FOCUS_LABELS, str(profile_value("training_focus", "balanced")))}</select>
            </label>
            <div class="full">
              <label>Körperbereiche, die du besonders trainieren möchtest</label>
              <div class="choice-grid" style="margin-top: 0.45rem;">
                {render_checkbox_options(BODY_FOCUS_LABELS, "focus_areas", tuple(profile.get("focus_areas") or ("full_body", "core")))}
              </div>
              <p class="subtle" style="margin-top: 0.45rem;">Wenn du nichts änderst, nutzt Bea diese Auswahl plus Zielvorschläge.</p>
            </div>
            <div class="full">
              <label>Vergangene Verletzungen oder sensible Bereiche</label>
              <div class="choice-grid" style="margin-top: 0.45rem;">
                {render_checkbox_options(INJURY_AREA_LABELS, "injury_areas", tuple(profile.get("injury_areas") or ("none",)))}
              </div>
            </div>
            <label class="full">
              Verletzungsnotizen
              <textarea name="injury_notes" placeholder="z.B. rechtes Knie nach Laufbelastung, Schulter beim Überkopfdrücken, Bandscheibenvorfall 2021">{h(profile_text("injury_notes"))}</textarea>
            </label>
            <label>
              Regenerationsstil
              <select name="recovery_style">{render_options(RECOVERY_LABELS, str(profile_value("recovery_style", "balanced")))}</select>
            </label>
            <label>
              Schlafstunden
              <input name="sleep_hours" type="number" min="3" max="12" step="0.5" value="{h(profile_value("sleep_hours", 7))}">
            </label>
            <label>
              Schlafqualität
              <select name="sleep_quality">{render_options(SLEEP_QUALITY_LABELS, str(profile_value("sleep_quality", "okay")))}</select>
            </label>
            <label>
              Stresslevel
              <select name="stress_level">{render_options(STRESS_LABELS, str(profile_value("stress_level", "medium")))}</select>
            </label>
            <label>
              Regenerationstage pro Woche
              <input name="recovery_days_per_week" type="number" min="1" max="4" value="{h(profile_value("recovery_days_per_week", 2))}">
            </label>
            <label>
              Mobility-Minuten
              <input name="mobility_minutes" type="number" min="0" max="60" value="{h(profile_value("mobility_minutes", 12))}">
            </label>

            <div class="form-section-title">
              <h3>Ernährung</h3>
              <p class="subtle">Die Mahlzeiten sollen zu Ziel, Alltag und Vorlieben passen.</p>
            </div>
            <label>
              Mahlzeiten pro Tag
              <input name="meals_per_day" type="number" min="2" max="6" value="{h(profile_value("meals_per_day", 3))}">
            </label>
            <label class="full">
              Ernährungsform
              <select name="diet_style">{render_options(DIET_LABELS, str(profile_value("diet_style", "mixed")))}</select>
            </label>
            <label class="full">
              Unverträglichkeiten, Ausschlüsse oder Notizen
              <textarea name="restrictions" placeholder="z.B. laktosefrei, kein Fisch, wenig Zeit morgens">{h(profile_text("restrictions"))}</textarea>
            </label>

            <div class="form-section-title">
              <h3>Abenteuer-Charakter</h3>
              <p class="subtle">Du spielst dich selbst, aber mit Klasse, Herkunft und Motivation.</p>
            </div>
            <label>
              Charaktername
              <input name="character_name" value="{h(profile_text("character_name"))}" placeholder="optional, sonst Mitgliedsname">
            </label>
            <label>
              Rolle
              <select name="adventure_role">{render_options(ADVENTURE_ROLE_LABELS, str(profile_value("adventure_role", "guardian")))}</select>
            </label>
            <label>
              Motivation
              <select name="motivation_style">{render_options(MOTIVATION_STYLE_LABELS, str(profile_value("motivation_style", "story")))}</select>
            </label>
            <label class="full">
              Herkunft & Erklärung
              <textarea name="character_origin" placeholder="z.B. Büro-Heldin mit Wanderlust, die ihren Schlafrhythmus zur Superkraft macht.">{h(profile_text("character_origin"))}</textarea>
            </label>
            <button class="button blue full" type="submit">{h(submit_label)}</button>
          </form>
        </div>

        <div class="panel">
          <h2>Was daraus entsteht</h2>
          <div class="list">
            <article class="card">
              <span class="tag area-team">Zielpfad</span>
              <p class="subtle" style="margin-top: 0.65rem;">Etappen, Check-ins, Zielmarken und Plan-Ausblick für die Fortschrittsseite.</p>
            </article>
            <article class="card">
              <span class="tag area-strength">Training</span>
              <p class="subtle" style="margin-top: 0.65rem;">Konkrete Übungen, Sätze, Wiederholungen, Ausführung und Alternativen.</p>
            </article>
            <article class="card">
              <span class="tag area-strength">Fokus</span>
              <p class="subtle" style="margin-top: 0.65rem;">Körperbereiche werden mit Zielvorschlägen abgeglichen, damit der Plan sinnvoll bleibt.</p>
            </article>
            <article class="card">
              <span class="tag area-team">Sicherheit</span>
              <p class="subtle" style="margin-top: 0.65rem;">Vergangene Verletzungen steuern Übungsauswahl, Technikhinweise und Schonvarianten.</p>
            </article>
            <article class="card">
              <span class="tag area-nutrition">Ernährung</span>
              <p class="subtle" style="margin-top: 0.65rem;">Protein, Fett, Kohlenhydrate und Mahlzeitenstruktur für den Alltag.</p>
            </article>
            <article class="card">
              <span class="tag area-team">Abenteuer</span>
              <p class="subtle" style="margin-top: 0.65rem;">Charakterrolle, Herkunft, Motivation und Avatar-Hinweise für das Rollenspiel-System.</p>
            </article>
            <article class="card">
              <span class="tag area-endurance">Alltag</span>
              <p class="subtle" style="margin-top: 0.65rem;">Hobbies, Arbeit, Schritte und Schlaf erklären, warum dein Plan genau so aufgebaut ist.</p>
            </article>
          </div>
        </div>
      </section>

      <section class="grid" style="margin-top: 1rem;">
        {render_plan_collection(state)}
      </section>
    """
    return render_layout("/fragebogen", "Fragebogen", body)


@app.get("/freunde", response_class=HTMLResponse)
def friends_page() -> str:
    state = load_state()
    member_cards = []
    for member in leaderboard(state):
        member_total = total_xp(member)
        level = level_for_xp(member_total)
        meters = "".join(level_meter(AREA_LABELS[area], int(member["xp"].get(area, 0)), area) for area in AREAS)
        member_cards.append(
            f"""
            <article class="card">
              <div class="row">
                <div>
                  <h3>{h(member["name"])}</h3>
                  <p class="subtle">{h(member["focus"])} · Serie {h(member["streak"])} Tage</p>
                </div>
                <span class="tag area-team">Level {level["level"]}</span>
              </div>
              <div class="grid two" style="margin-top: 0.8rem;">{meters}</div>
            </article>
            """
        )

    assignments = "".join(render_assignment_card(state, item) for item in state["assignments"][:8])
    body = f"""
      <section class="page-heading">
        <div>
          <p class="eyebrow">Freunde</p>
          <h1>Teamvergleich</h1>
        </div>
      </section>

      <section class="grid two">
        <div class="panel">
          <h2>Motivieren</h2>
          <form class="form-grid" data-api-form data-endpoint="/api/motivations">
            <label>
              Von
              <select name="from_member">{render_member_options(state, "bea")}</select>
            </label>
            <label>
              An
              <select name="to_member">{render_member_options(state, "mara")}</select>
            </label>
            <label class="full">
              Nachricht
              <textarea name="message" placeholder="Heute nur ein kleiner Schritt, aber ein echter."></textarea>
            </label>
            <button class="button full" type="submit">Motivation senden</button>
          </form>
        </div>
        <div class="panel">
          <h2>Übung zuweisen</h2>
          <form class="form-grid" data-api-form data-endpoint="/api/assignments">
            <label>
              Von
              <select name="from_member">{render_member_options(state, "bea")}</select>
            </label>
            <label>
              An
              <select name="to_member">{render_member_options(state, "jonas")}</select>
            </label>
            <label>
              Bereich
              <select name="category">{render_category_options("strength")}</select>
            </label>
            <label>
              Fällig
              <input name="due" value="Diese Woche">
            </label>
            <label class="full">
              Aufgabe
              <input name="title" placeholder="3x12 Kniebeugen">
            </label>
            <label class="full">
              Details
              <textarea name="details" placeholder="Tempo, Gewicht, Ziel oder kurze Notiz"></textarea>
            </label>
            <button class="button blue full" type="submit">Aufgabe zuweisen</button>
          </form>
        </div>
      </section>

      <section class="grid two" style="margin-top: 1rem;">
        <div class="panel">
          <h2>Mitglieder</h2>
          <div class="list">{"".join(member_cards)}</div>
        </div>
        <div class="panel">
          <h2>Aufgaben</h2>
          <div class="list">{assignments}</div>
        </div>
      </section>
    """
    return render_layout("/freunde", "Freunde", body)


@app.get("/gruppen", response_class=HTMLResponse)
def groups_page() -> str:
    state = load_state()
    group_cards = "".join(render_group_card(state, group) for group in groups(state))
    membership_rows = []
    for member in state["members"]:
        joined = groups_for_member(state, member["id"])
        membership_rows.append(
            f"""
            <tr>
              <td>{h(member["name"])}</td>
              <td>{h(len(joined))}</td>
              <td>{h(", ".join(group["name"] for group in joined) if joined else "Noch keine Gruppe")}</td>
            </tr>
            """
        )

    body = f"""
      <section class="page-heading">
        <div>
          <p class="eyebrow">Gruppen</p>
          <h1>Squads finden</h1>
        </div>
        <p class="subtle">Tritt passenden Gruppen bei und startet eigene Challenges für genau diese Crew.</p>
      </section>

      <section class="grid two">
        <div class="panel">
          <h2>Gruppe erstellen</h2>
          <form class="form-grid" data-api-form data-endpoint="/api/groups/create">
            <label>
              Erstellt von
              <select name="created_by">{render_member_options(state, "bea")}</select>
            </label>
            <label>
              Fokus
              <input name="focus" placeholder="z.B. Laufen, Kraft, Meal Prep">
            </label>
            <label class="full">
              Gruppenname
              <input name="name" placeholder="Afterwork Athletes">
            </label>
            <label class="full">
              Beschreibung
              <textarea name="description" placeholder="Worum geht es in dieser Gruppe?"></textarea>
            </label>
            <button class="button blue full" type="submit">Gruppe erstellen</button>
          </form>
        </div>

        <div class="panel">
          <h2>Mitgliedschaften</h2>
          <table>
            <thead>
              <tr>
                <th>Mitglied</th>
                <th>Gruppen</th>
                <th>Beigetreten</th>
              </tr>
            </thead>
            <tbody>{"".join(membership_rows)}</tbody>
          </table>
        </div>
      </section>

      <section class="panel" style="margin-top: 1rem;">
        <h2>Verfügbare Gruppen</h2>
        <div class="grid three">{group_cards}</div>
      </section>
    """
    return render_layout("/gruppen", "Gruppen", body)


@app.get("/challenges", response_class=HTMLResponse)
def challenges_page() -> str:
    state = load_state()
    challenge_cards = "".join(render_challenge_card(state, challenge, True) for challenge in state["challenges"])
    body = f"""
      <section class="page-heading">
        <div>
          <p class="eyebrow">Challenges</p>
          <h1>Gemeinsam ziehen</h1>
        </div>
        <a class="button blue" href="/gruppen">Gruppen verwalten</a>
      </section>

      <section class="panel" style="margin-bottom: 1rem;">
        <h2>Challenge erstellen</h2>
        <form class="form-grid" data-api-form data-endpoint="/api/challenges/create">
          <label>
            Erstellt von
            <select name="created_by">{render_member_options(state, "bea")}</select>
          </label>
          <label>
            Gruppe
            <select name="group_id">{render_group_options(state, "", True)}</select>
          </label>
          <label>
            Bereich
            <select name="category">{render_options(AREA_LABELS, "team")}</select>
          </label>
          <label>
            Zielwert
            <input name="goal" type="number" min="1" value="10">
          </label>
          <label>
            Einheit
            <input name="unit" placeholder="Minuten, Tage, Einheiten" value="Punkte">
          </label>
          <label>
            Bonus XP
            <input name="xp" type="number" min="10" max="1000" value="100">
          </label>
          <label class="full">
            Titel
            <input name="title" placeholder="7 Tage Protein treffen">
          </label>
          <label class="full">
            Beschreibung
            <textarea name="description" placeholder="Was zählt und wie sammelt die Gruppe Fortschritt?"></textarea>
          </label>
          <button class="button blue full" type="submit">Challenge erstellen</button>
        </form>
      </section>

      <section class="grid two">
        {challenge_cards}
      </section>
    """
    return render_layout("/challenges", "Challenges", body)


@app.get("/sport", response_class=HTMLResponse)
def sport_page() -> str:
    state = load_state()
    rows = []
    for entry in state["sport_entries"][:14]:
        rows.append(
            f"""
            <tr>
              <td>{h(entry["created_at"])}</td>
              <td>{h(member_name(state, entry["member_id"]))}</td>
              <td><span class="tag {area_class(entry["sport_type"])}">{h(AREA_LABELS[entry["sport_type"]])}</span></td>
              <td>{h(entry["title"])}</td>
              <td>{h(entry["amount"])}</td>
              <td>{h(entry["duration"])} min</td>
              <td>{h(entry["xp"])} XP</td>
              <td>{'<a class="tag area-team" href="' + h(entry.get("youtube_url", "")) + '" target="_blank" rel="noopener">Video</a>' if entry.get("youtube_url") else ''}</td>
            </tr>
            """
        )

    body = f"""
      <section class="page-heading">
        <div>
          <p class="eyebrow">Sport</p>
          <h1>Ausdauer & Kraft</h1>
        </div>
      </section>

      <section class="grid two">
        <div class="panel">
          <h2>Ausdauer eintragen</h2>
          <form class="form-grid" data-api-form data-endpoint="/api/sport">
            <input type="hidden" name="sport_type" value="endurance">
            <label>
              Mitglied
              <select name="member_id">{render_member_options(state, "bea")}</select>
            </label>
            <label>
              Belastung
              <select name="effort">
                <option value="2">Locker</option>
                <option value="3" selected>Mittel</option>
                <option value="4">Hart</option>
                <option value="5">Maximum</option>
              </select>
            </label>
            <label>
              Einheit
              <input name="title" placeholder="Lauf, Rad, Schwimmen">
            </label>
            <label>
              Menge
              <input name="amount" placeholder="5 km">
            </label>
            <label class="full">
              Dauer in Minuten
              <input name="duration" type="number" min="1" value="30">
            </label>
            <label class="full">
              YouTube-Link, optional
              <input name="youtube_url" placeholder="https://www.youtube.com/watch?v=...">
            </label>
            <button class="button blue full" type="submit">Ausdauer speichern</button>
          </form>
        </div>

        <div class="panel">
          <h2>Kraft eintragen</h2>
          <form class="form-grid" data-api-form data-endpoint="/api/sport">
            <input type="hidden" name="sport_type" value="strength">
            <label>
              Mitglied
              <select name="member_id">{render_member_options(state, "bea")}</select>
            </label>
            <label>
              Belastung
              <select name="effort">
                <option value="2">Locker</option>
                <option value="3">Mittel</option>
                <option value="4" selected>Hart</option>
                <option value="5">Maximum</option>
              </select>
            </label>
            <label>
              Übung
              <input name="title" placeholder="Bankdrücken, Kniebeugen">
            </label>
            <label>
              Umfang
              <input name="amount" placeholder="4x8">
            </label>
            <label class="full">
              Dauer in Minuten
              <input name="duration" type="number" min="1" value="45">
            </label>
            <label class="full">
              YouTube-Link, optional
              <input name="youtube_url" placeholder="https://www.youtube.com/watch?v=...">
            </label>
            <button class="button red full" type="submit">Kraft speichern</button>
          </form>
        </div>
      </section>

      <section class="grid two" style="margin-top: 1rem;">
        <div class="panel">
          <h2>YouTube Training anhängen</h2>
          <form class="form-grid" data-api-form data-endpoint="/api/youtube">
            <input type="hidden" name="context" value="training">
            <label>
              Mitglied
              <select name="member_id">{render_member_options(state, "bea")}</select>
            </label>
            <label>
              Titel
              <input name="title" placeholder="Technik Kniebeuge">
            </label>
            <label class="full">
              YouTube-Link
              <input name="youtube_url" placeholder="https://www.youtube.com/watch?v=...">
            </label>
            <label class="full">
              Notiz
              <textarea name="note" placeholder="Wofür ist das Video hilfreich?"></textarea>
            </label>
            <button class="button blue full" type="submit">Trainingsvideo speichern</button>
          </form>
        </div>
        <div class="panel">
          <h2>Trainingsvideos</h2>
          <div class="grid">{render_youtube_links(state, "training")}</div>
        </div>
      </section>

      <section class="panel" style="margin-top: 1rem;">
        <h2>Letzte Sporteinträge</h2>
        <table>
          <thead>
            <tr>
              <th>Datum</th>
              <th>Mitglied</th>
              <th>Bereich</th>
              <th>Einheit</th>
              <th>Menge</th>
              <th>Dauer</th>
              <th>XP</th>
              <th>Video</th>
            </tr>
          </thead>
          <tbody>{"".join(rows)}</tbody>
        </table>
      </section>
    """
    return render_layout("/sport", "Sport", body)


@app.get("/mindset", response_class=HTMLResponse)
def mindset_page(request: Request) -> str:
    state = load_state()
    member_id = dashboard_member_id(state, request)
    member_label = member_name(state, member_id)
    entries = [
        entry
        for entry in state.setdefault("mindset_entries", [])
        if entry.get("member_id") == member_id
    ]
    total_minutes = sum(int(entry.get("duration", 0)) for entry in entries)
    total_xp = sum(int(entry.get("xp", 0)) for entry in entries)
    latest = entries[0] if entries else {}
    exercise_options = "\n".join(
        f'<option value="{h(key)}">{h(item["label"])}</option>'
        for key, item in MINDSET_EXERCISES.items()
    )
    exercise_cards = "".join(
        f"""
        <article class="card area-mindset">
          <div class="row">
            <h3>{h(item["label"])}</h3>
            <span class="tag area-mindset">+{h(item["base_xp"])} Basis-XP</span>
          </div>
          <p class="subtle">{h(item["description"])}</p>
          <p class="subtle" style="margin-top: 0.45rem;"><strong>Impuls:</strong> {h(item["prompt"])}</p>
        </article>
        """
        for item in MINDSET_EXERCISES.values()
    )
    rows = "".join(
        f"""
        <tr>
          <td>{h(entry["created_at"])}</td>
          <td><span class="tag area-mindset">{h(MINDSET_EXERCISES.get(entry.get("exercise_type"), {}).get("label", "Mindset"))}</span></td>
          <td>{h(entry.get("title", "Mindset"))}</td>
          <td>{h(entry.get("duration", 0))} min</td>
          <td>{h(entry.get("mood_before", "-"))}</td>
          <td>{h(entry.get("mood_after", "-"))}</td>
          <td>{h(entry.get("xp", 0))} XP</td>
        </tr>
        """
        for entry in entries[:14]
    )
    if not rows:
        rows = '<tr><td colspan="7">Noch keine Mindset-Übung eingetragen.</td></tr>'

    body = f"""
      <section class="page-heading">
        <div>
          <p class="eyebrow">Mindset</p>
          <h1>Innere Werte leveln</h1>
        </div>
        <p class="subtle">Meditation, Atemarbeit und Reflexion geben deinem Charakter eigene Mindset-XP.</p>
      </section>

      <section class="grid four">
        <article class="stat-card">
          <span>Charakter</span>
          <strong>{h(member_label)}</strong>
        </article>
        <article class="stat-card">
          <span>Übungen</span>
          <strong>{h(len(entries))}</strong>
        </article>
        <article class="stat-card">
          <span>Minuten</span>
          <strong>{h(total_minutes)}</strong>
        </article>
        <article class="stat-card">
          <span>Mindset-XP</span>
          <strong>{h(total_xp)}</strong>
        </article>
      </section>

      <section class="grid two" style="margin-top: 1rem;">
        <div class="panel">
          <h2>Mindset-Übung eintragen</h2>
          <form class="form-grid" data-api-form data-endpoint="/api/mindset">
            <label>
              Übung
              <select name="exercise_type">{exercise_options}</select>
            </label>
            <label>
              Intensität
              <select name="effort">
                <option value="1">Sehr ruhig</option>
                <option value="2" selected>Ruhig</option>
                <option value="3">Fokussiert</option>
                <option value="4">Tief</option>
                <option value="5">Sehr intensiv</option>
              </select>
            </label>
            <label>
              Titel
              <input name="title" placeholder="Morgenmeditation">
            </label>
            <label>
              Dauer in Minuten
              <input name="duration" type="number" min="1" max="180" value="5">
            </label>
            <label>
              Vorher
              <input name="mood_before" placeholder="angespannt, müde, unruhig">
            </label>
            <label>
              Nachher
              <input name="mood_after" placeholder="ruhiger, klarer, geerdet">
            </label>
            <label class="full">
              Reflexion
              <textarea name="note" placeholder="Was hast du bemerkt? Was nimmst du mit?"></textarea>
            </label>
            <button class="button blue full" type="submit">Mindset-XP sammeln</button>
          </form>
        </div>

        <div class="panel">
          <h2>Heute sinnvoll</h2>
          <div class="list" style="margin-top: 1rem;">
            <article class="card area-mindset">
              <h3>{h(latest.get("title", "5 Minuten bewusst werden"))}</h3>
              <p class="subtle">{h(latest.get("note", "Starte klein: 5 Minuten atmen, meditieren oder drei Gedanken notieren."))}</p>
            </article>
            <article class="card area-team">
              <h3>Level-Regel</h3>
              <p class="subtle">Mindset-XP zählt wie Ausdauer, Kraft und Nahrung in dein Gesamtlevel. Kleine tägliche Einheiten sind wertvoller als seltene perfekte Sessions.</p>
            </article>
          </div>
        </div>
      </section>

      <section class="panel" style="margin-top: 1rem;">
        <h2>Übungsauswahl</h2>
        <div class="grid two" style="margin-top: 1rem;">{exercise_cards}</div>
      </section>

      <section class="panel" style="margin-top: 1rem;">
        <h2>Mindset-Verlauf</h2>
        <table>
          <thead>
            <tr>
              <th>Datum</th>
              <th>Übung</th>
              <th>Titel</th>
              <th>Dauer</th>
              <th>Vorher</th>
              <th>Nachher</th>
              <th>XP</th>
            </tr>
          </thead>
          <tbody>{rows}</tbody>
        </table>
      </section>
    """
    return render_layout("/mindset", "Mindset", body)


@app.get("/nahrung", response_class=HTMLResponse)
def nutrition_page() -> str:
    state = load_state()
    rows = []
    for entry in state["nutrition_entries"][:14]:
        rows.append(
            f"""
            <tr>
              <td>{h(entry["created_at"])}</td>
              <td>{h(member_name(state, entry["member_id"]))}</td>
              <td>{h(MEAL_LABELS.get(entry.get("meal_type", "snack"), "Snack"))}</td>
              <td>{h(entry["meal"])}</td>
              <td>{h(entry.get("source", "Manuell"))}</td>
              <td>{h(entry["protein"])} g</td>
              <td>{h(entry.get("carbs", 0))} g</td>
              <td>{h(entry.get("fat", 0))} g</td>
              <td>{h(entry["calories"])} kcal</td>
              <td>{h(entry["water"])} l</td>
              <td>{h(entry["xp"])} XP</td>
              <td>{'<a class="tag area-team" href="' + h(entry.get("youtube_url", "")) + '" target="_blank" rel="noopener">Video</a>' if entry.get("youtube_url") else ''}</td>
            </tr>
            """
        )

    protein_total = sum(int(entry["protein"]) for entry in state["nutrition_entries"])
    water_total = sum(float(entry["water"]) for entry in state["nutrition_entries"])
    idea_cards = "".join(
        f"""
        <article class="card">
          <div class="row">
            <span class="tag area-nutrition">{h(MEAL_LABELS[item["meal_type"]])}</span>
            <strong>{h(item["calories"])} kcal</strong>
          </div>
          <h3>{h(item["title"])}</h3>
          <p class="subtle">{h(item["description"])}</p>
          <p class="subtle">{h(item["protein"])} g Protein - {h(item["carbs"])} g KH - {h(item["fat"])} g Fett</p>
        </article>
        """
        for item in meal_ideas(state)[:6]
    )
    catalog_rows = "".join(
        f"""
        <tr>
          <td>{h(item["name"])}</td>
          <td>{h(FOOD_CATEGORIES.get(item["category"], "Sonstiges"))}</td>
          <td>{h(item["calories"])}</td>
          <td>{h(item["protein"])} g</td>
          <td>{h(item["carbs"])} g</td>
          <td>{h(item["fat"])} g</td>
        </tr>
        """
        for item in food_items(state)[:18]
    )

    body = f"""
      <section class="page-heading">
        <div>
          <p class="eyebrow">Nahrung</p>
          <h1>Fuel Score</h1>
        </div>
      </section>

      <section class="grid three">
        <article class="stat-card">
          <span>Protein</span>
          <strong>{h(protein_total)} g</strong>
        </article>
        <article class="stat-card">
          <span>Wasser</span>
          <strong>{h(round(water_total, 1))} l</strong>
        </article>
        <article class="stat-card">
          <span>Einträge</span>
          <strong>{h(len(state["nutrition_entries"]))}</strong>
        </article>
      </section>

      <section class="grid two" style="margin-top: 1rem;">
        <div class="panel">
          <h2>Gericht auswählen</h2>
          <form class="form-grid" data-api-form data-endpoint="/api/nutrition">
            <label>
              Mitglied
              <select name="member_id">{render_member_options(state, "bea")}</select>
            </label>
            <label>
              Gericht
              <select name="meal_idea_id">{render_meal_idea_options(state)}</select>
            </label>
            <label>
              Wasser in l
              <input name="water" type="number" min="0" step="0.1" value="0.5">
            </label>
            <label>
              YouTube-Link, optional
              <input name="youtube_url" placeholder="https://www.youtube.com/watch?v=...">
            </label>
            <button class="button full" type="submit">Gericht speichern</button>
          </form>
        </div>
        <div class="panel">
          <h2>Lebensmittel eintragen</h2>
          <form class="form-grid" data-api-form data-endpoint="/api/nutrition">
            <label>
              Mitglied
              <select name="member_id">{render_member_options(state, "bea")}</select>
            </label>
            <label>
              Mahlzeit
              <select name="meal_type">{render_options(MEAL_LABELS, "breakfast")}</select>
            </label>
            <label class="full">
              Lebensmittel
              <select name="food_id">{render_food_options(state)}</select>
            </label>
            <label>
              Menge in g/ml
              <input name="grams" type="number" min="1" value="100">
            </label>
            <label>
              Wasser in l
              <input name="water" type="number" min="0" step="0.1" value="0.5">
            </label>
            <label class="full">
              YouTube-Link, optional
              <input name="youtube_url" placeholder="https://www.youtube.com/watch?v=...">
            </label>
            <button class="button blue full" type="submit">Lebensmittel speichern</button>
          </form>
        </div>
      </section>

      <section class="grid two" style="margin-top: 1rem;">
        <div class="panel">
          <h2>Manuell eintragen</h2>
          <form class="form-grid" data-api-form data-endpoint="/api/nutrition">
            <label>
              Mitglied
              <select name="member_id">{render_member_options(state, "bea")}</select>
            </label>
            <label>
              Mahlzeit
              <select name="meal_type">{render_options(MEAL_LABELS, "snack")}</select>
            </label>
            <label class="full">
              Name
              <input name="meal" placeholder="Quark Bowl">
            </label>
            <label>
              Protein in g
              <input name="protein" type="number" min="0" value="30">
            </label>
            <label>
              Kohlenhydrate in g
              <input name="carbs" type="number" min="0" value="45">
            </label>
            <label>
              Fett in g
              <input name="fat" type="number" min="0" value="12">
            </label>
            <label>
              Kalorien
              <input name="calories" type="number" min="0" value="550">
            </label>
            <label>
              Wasser in l
              <input name="water" type="number" min="0" step="0.1" value="0.5">
            </label>
            <label class="full">
              YouTube-Link, optional
              <input name="youtube_url" placeholder="https://www.youtube.com/watch?v=...">
            </label>
            <button class="button full" type="submit">Manuell speichern</button>
          </form>
        </div>
        <div class="panel">
          <h2>Lebensmittel zur Datenbank</h2>
          <form class="form-grid" data-api-form data-endpoint="/api/foods">
            <label class="full">
              Name
              <input name="name" placeholder="Hummus">
            </label>
            <label>
              Kategorie
              <select name="category">{render_options(FOOD_CATEGORIES, "other")}</select>
            </label>
            <label>
              kcal / 100g
              <input name="calories" type="number" min="0" value="200">
            </label>
            <label>
              Protein / 100g
              <input name="protein" type="number" min="0" step="0.1" value="8">
            </label>
            <label>
              Kohlenhydrate / 100g
              <input name="carbs" type="number" min="0" step="0.1" value="14">
            </label>
            <label>
              Fett / 100g
              <input name="fat" type="number" min="0" step="0.1" value="10">
            </label>
            <button class="button secondary full" type="submit">Lebensmittel speichern</button>
          </form>
        </div>
      </section>

      <section class="grid two" style="margin-top: 1rem;">
        <div class="panel">
          <h2>Gerichte zur Auswahl</h2>
          <div class="grid two">{idea_cards}</div>
        </div>
        <div class="panel">
          <h2>YouTube Mahlzeit anhängen</h2>
          <form class="form-grid" data-api-form data-endpoint="/api/youtube">
            <input type="hidden" name="context" value="meal">
            <label>
              Mitglied
              <select name="member_id">{render_member_options(state, "bea")}</select>
            </label>
            <label>
              Titel
              <input name="title" placeholder="Meal Prep Bowl">
            </label>
            <label class="full">
              YouTube-Link
              <input name="youtube_url" placeholder="https://www.youtube.com/watch?v=...">
            </label>
            <label class="full">
              Notiz
              <textarea name="note" placeholder="Warum passt dieses Gericht?"></textarea>
            </label>
            <button class="button full" type="submit">Mahlzeitenvideo speichern</button>
          </form>
        </div>
      </section>

      <section class="grid two" style="margin-top: 1rem;">
        <div class="panel">
          <h2>Nahrungs-Level</h2>
          <div class="grid two">
            {"".join(level_meter(member["name"], int(member["xp"].get("nutrition", 0)), "nutrition") for member in leaderboard(state))}
          </div>
        </div>
        <div class="panel">
          <h2>Mahlzeitenvideos</h2>
          <div class="grid">{render_youtube_links(state, "meal")}</div>
        </div>
      </section>

      <section class="panel" style="margin-top: 1rem;">
        <h2>Lebensmittel-Datenbank</h2>
        <table>
          <thead>
            <tr>
              <th>Lebensmittel</th>
              <th>Kategorie</th>
              <th>kcal / 100g</th>
              <th>Protein</th>
              <th>KH</th>
              <th>Fett</th>
            </tr>
          </thead>
          <tbody>{catalog_rows}</tbody>
        </table>
      </section>

      <section class="panel" style="margin-top: 1rem;">
        <h2>Letzte Nahrungseinträge</h2>
        <table>
          <thead>
            <tr>
              <th>Datum</th>
              <th>Mitglied</th>
              <th>Typ</th>
              <th>Mahlzeit</th>
              <th>Quelle</th>
              <th>Protein</th>
              <th>KH</th>
              <th>Fett</th>
              <th>Kalorien</th>
              <th>Wasser</th>
              <th>XP</th>
              <th>Video</th>
            </tr>
          </thead>
          <tbody>{"".join(rows)}</tbody>
        </table>
      </section>
    """
    return render_layout("/nahrung", "Nahrung", body)


def render_public_photo_card(state: dict, photo: dict) -> str:
    return f"""
      <article class="photo-card">
        <div class="photo-frame">
          <img src="{h(photo["image_data"])}" alt="{h(photo["title"])}">
        </div>
        <div class="photo-body">
          <div class="row">
            <strong>{h(photo["title"])}</strong>
            <span class="tag area-team">Community</span>
          </div>
          <p class="subtle">{h(member_name(state, photo["member_id"]))} · {h(photo["photo_type"])} · {h(photo["published_at"] or photo["created_at"])}</p>
          <p class="subtle">{h(photo["note"])}</p>
        </div>
      </article>
    """


@app.get("/fotos", response_class=HTMLResponse)
def photos_page() -> str:
    state = load_state()
    pin_status = []
    for member in state["members"]:
        status = "PIN eingerichtet" if photo_pin_is_set(state, member["id"]) else "PIN fehlt"
        status_class = "connected" if photo_pin_is_set(state, member["id"]) else "missing"
        pin_status.append(
            f"""
            <article class="card">
              <div class="row">
                <div>
                  <h3>{h(member["name"])}</h3>
                  <p class="subtle">{h(member["focus"])}</p>
                </div>
                <span class="integration-status {status_class}">{status}</span>
              </div>
            </article>
            """
        )

    public_cards = "".join(render_public_photo_card(state, photo) for photo in public_photos(state))
    if not public_cards:
        public_cards = """
          <article class="card">
            <p class="subtle">Noch keine Community-Fotos veröffentlicht.</p>
          </article>
        """

    body = f"""
      <section class="page-heading">
        <div>
          <p class="eyebrow">Vergleichsfotos</p>
          <h1>Privat zuerst</h1>
        </div>
        <p class="subtle">Fotos sind PIN-geschützt und werden erst sichtbar, wenn du sie selbst in die Community stellst.</p>
      </section>

      <section class="grid two">
        <div class="panel">
          <h2>Foto-PIN einrichten</h2>
          <form class="form-grid" data-api-form data-endpoint="/api/photos/pin">
            <label>
              Mitglied
              <select name="member_id">{render_member_options(state, "bea")}</select>
            </label>
            <label>
              Neuer PIN
              <input name="pin" type="password" minlength="4" autocomplete="new-password">
            </label>
            <label class="full">
              Aktueller PIN, nur beim Ändern
              <input name="current_pin" type="password" autocomplete="current-password">
            </label>
            <button class="button full" type="submit">PIN speichern</button>
          </form>
          <div class="list" style="margin-top: 1rem;">{"".join(pin_status)}</div>
        </div>

        <div class="panel">
          <h2>Privates Foto hochladen</h2>
          <form class="form-grid" id="photo-upload-form">
            <label>
              Mitglied
              <select name="member_id">{render_member_options(state, "bea")}</select>
            </label>
            <label>
              Foto-PIN
              <input name="pin" type="password" autocomplete="current-password">
            </label>
            <label>
              Titel
              <input name="title" placeholder="Check-in Juni">
            </label>
            <label>
              Perspektive
              <select name="photo_type">
                <option>Front</option>
                <option>Seite</option>
                <option>Rücken</option>
                <option>Avatar Ganzkörper Front</option>
                <option>Avatar Ganzkörper Seite</option>
                <option selected>Check-in</option>
              </select>
            </label>
            <label class="full">
              Notiz
              <textarea name="note" placeholder="Training, Phase, Gewicht oder kurzer Kontext"></textarea>
            </label>
            <label class="full">
              Foto
              <input name="photo_file" type="file" accept="image/jpeg,image/png,image/webp">
            </label>
            <button class="button blue full" type="submit">Privat speichern</button>
          </form>
        </div>
      </section>

      <section class="panel" style="margin-top: 1rem;">
        <div class="row">
          <div>
            <h2>Private Galerie</h2>
            <p class="subtle">Die Fotos werden erst nach PIN-Prüfung geladen.</p>
          </div>
          <button class="button secondary" id="photo-compare-button" type="button">Auswahl vergleichen</button>
        </div>
        <form class="form-grid" id="photo-gallery-form" style="margin-top: 1rem;">
          <label>
            Mitglied
            <select name="member_id">{render_member_options(state, "bea")}</select>
          </label>
          <label>
            Foto-PIN
            <input name="pin" type="password" autocomplete="current-password">
          </label>
          <button class="button full" type="submit">Private Fotos laden</button>
        </form>
        <div class="compare-board" id="compare-board"></div>
        <div class="photo-grid" id="private-photo-gallery" style="margin-top: 1rem;">
          <article class="card">
            <p class="subtle">Wähle dein Mitglied aus und gib deinen PIN ein.</p>
          </article>
        </div>
      </section>

      <section class="panel" style="margin-top: 1rem;">
        <div class="row">
          <div>
            <h2>Community-Fotos</h2>
            <p class="subtle">Nur bewusst veröffentlichte Fotos erscheinen hier.</p>
          </div>
        </div>
        <div class="photo-grid" style="margin-top: 1rem;">{public_cards}</div>
      </section>
    """
    return render_layout("/fotos", "Fotos", body)


def render_weather_day(day: dict) -> str:
    plan = day["plan"]
    return f"""
      <article class="card">
        <div class="row">
          <div>
            <h3>{h(day["date"])}</h3>
            <p class="subtle">{h(day["label"])}</p>
          </div>
          <span class="recommendation {h(plan["level"])}">{h(plan["activity"])}</span>
        </div>
        <div class="grid four" style="margin-top: 0.8rem;">
          <div>
            <p class="eyebrow">Temperatur</p>
            <strong>{h(day["temp_min"])} - {h(day["temp_max"])} °C</strong>
          </div>
          <div>
            <p class="eyebrow">Regen</p>
            <strong>{h(day["rain"])} %</strong>
          </div>
          <div>
            <p class="eyebrow">Wind</p>
            <strong>{h(day["wind"])} km/h</strong>
          </div>
          <div>
            <p class="eyebrow">Plan</p>
            <strong>{h("Outdoor" if plan["level"] == "outdoor" else "Studio")}</strong>
          </div>
        </div>
        <p class="subtle" style="margin-top: 0.8rem;">{h(plan["reason"])}</p>
      </article>
    """


@app.get("/fitnessplan", response_class=HTMLResponse)
def fitness_plan_page() -> str:
    state = load_state()
    settings = state.get("settings", {})
    forecast = fetch_forecast(settings)
    weather_cards = "".join(render_weather_day(day) for day in forecast["days"])
    if not weather_cards:
        weather_cards = f"""
          <article class="card">
            <h3>Wetter gerade nicht erreichbar</h3>
            <p class="subtle">{h(forecast["error"] or "Bitte später erneut prüfen.")}</p>
          </article>
        """

    body = f"""
      <section class="page-heading">
        <div>
          <p class="eyebrow">Fitnessplan</p>
          <h1>Wetter entscheidet mit</h1>
        </div>
        <p class="subtle">Die Vorhersage hilft bei der Wahl zwischen Fahrrad, Laufen, Wandern und Laufband.</p>
      </section>

      <section class="grid two">
        <div class="panel">
          <h2>Standort</h2>
          <form class="form-grid" data-api-form data-endpoint="/api/settings/location">
            <label class="full">
              Name
              <input name="location_label" value="{h(settings.get("location_label", "Berlin"))}">
            </label>
            <label>
              Breitengrad
              <input name="latitude" type="number" step="0.000001" value="{h(settings.get("latitude", 52.52))}">
            </label>
            <label>
              Längengrad
              <input name="longitude" type="number" step="0.000001" value="{h(settings.get("longitude", 13.405))}">
            </label>
            <button class="button full" type="submit">Standort speichern</button>
          </form>
        </div>
        <div class="panel">
          <h2>Planungslogik</h2>
          <div class="list">
            <article class="card">
              <span class="recommendation outdoor">Outdoor</span>
              <p class="subtle" style="margin-top: 0.65rem;">Wenig Regen, moderater Wind und angenehme Temperaturen bevorzugen Fahrrad, Laufen oder Wandern.</p>
            </article>
            <article class="card">
              <span class="recommendation studio">Studio</span>
              <p class="subtle" style="margin-top: 0.65rem;">Starker Regen, Wind, Gewitter oder extreme Temperaturen schieben die Einheit aufs Laufband.</p>
            </article>
          </div>
        </div>
      </section>

      <section class="panel" style="margin-top: 1rem;">
        <div class="row">
          <div>
            <h2>Vorhersage für {h(settings.get("location_label", "Berlin"))}</h2>
            <p class="subtle">Quelle: Open-Meteo, 5-Tage-Prognose</p>
          </div>
        </div>
        <div class="list" style="margin-top: 1rem;">{weather_cards}</div>
      </section>

      <section class="grid" style="margin-top: 1rem;">
        {render_plan_collection(state)}
      </section>
    """
    return render_layout("/fitnessplan", "Fitnessplan", body)


def strava_redirect_uri(request: Request) -> str:
    override = os.getenv("STRAVA_REDIRECT_URI", "").strip()
    if override:
        return override
    return str(request.url_for("strava_callback"))


@app.get("/integrationen", response_class=HTMLResponse)
def integrations_page(request: Request) -> str:
    state = load_state()
    strava_configured = strava_is_configured()
    strava = state.get("integrations", {}).get("strava", {})
    connections = strava.get("connections", {})
    last_sync = strava.get("last_sync", {})

    status_cards = []
    for member in state["members"]:
        connection = connections.get(member["id"])
        if connection:
            status = f"""
              <span class="integration-status connected">Verbunden</span>
              <p class="subtle">Strava: {h(connection.get("athlete_name", "Athlete"))} · letzter Sync {h(last_sync.get(member["id"], "noch nie"))}</p>
            """
        else:
            status = """
              <span class="integration-status missing">Nicht verbunden</span>
              <p class="subtle">Dieses Mitglied kann Strava noch verbinden.</p>
            """
        status_cards.append(
            f"""
            <article class="card">
              <div class="row">
                <div>
                  <h3>{h(member["name"])}</h3>
                  {status}
                </div>
              </div>
            </article>
            """
        )

    if strava_configured:
        strava_action = f"""
          <form class="form-grid" action="/integrationen/strava/start" method="get">
            <label class="full">
              Mitglied
              <select name="member_id">{render_member_options(state, "bea")}</select>
            </label>
            <button class="button blue full" type="submit">Mit Strava verbinden</button>
          </form>
          <form class="form-grid" data-api-form data-endpoint="/api/integrations/strava/sync" style="margin-top: 0.8rem;">
            <label class="full">
              Aktivitäten importieren für
              <select name="member_id">{render_member_options(state, "bea")}</select>
            </label>
            <button class="button full" type="submit">Strava synchronisieren</button>
          </form>
        """
    else:
        strava_action = f"""
          <article class="card">
            <span class="integration-status missing">Konfiguration fehlt</span>
            <p class="subtle" style="margin-top: 0.65rem;">Setze auf dem Raspberry Pi `STRAVA_CLIENT_ID` und `STRAVA_CLIENT_SECRET`. Redirect URI: {h(strava_redirect_uri(request))}</p>
          </article>
        """

    body = f"""
      <section class="page-heading">
        <div>
          <p class="eyebrow">Integrationen</p>
          <h1>Apps verbinden</h1>
        </div>
        <p class="subtle">Ausdauereinheiten können aus verbundenen Apps in den Sportbereich importiert werden.</p>
      </section>

      <section class="grid two">
        <div class="panel">
          <div class="row">
            <div>
              <h2>Strava</h2>
              <p class="subtle">Importiert Läufe, Fahrten, Wanderungen und weitere Aktivitäten.</p>
            </div>
            <span class="integration-status {"connected" if strava_configured else "missing"}">{h("Bereit" if strava_configured else "Setup")}</span>
          </div>
          {strava_action}
        </div>
        <div class="panel">
          <h2>Weitere Apps</h2>
          <div class="list">
            <article class="card">
              <h3>Garmin Connect</h3>
              <p class="subtle">Als nächste Integrationskarte vorbereitet.</p>
            </article>
            <article class="card">
              <h3>Apple Health / Google Fit</h3>
              <p class="subtle">Kann später über Export oder API-Sync angebunden werden.</p>
            </article>
          </div>
        </div>
      </section>

      <section class="panel" style="margin-top: 1rem;">
        <h2>Verbindungsstatus</h2>
        <div class="grid two">{"".join(status_cards)}</div>
      </section>
    """
    return render_layout("/integrationen", "Integrationen", body)


@app.get("/impressum", response_class=HTMLResponse)
def imprint_page() -> str:
    body = """
      <section class="page-heading">
        <div>
          <p class="eyebrow">Rechtliches</p>
          <h1>Impressum</h1>
        </div>
        <p class="subtle">Fiktives Muster für dieses Projekt.</p>
      </section>

      <section class="grid two">
        <article class="panel">
          <h2>Angaben gemäß Paragraf 5 DDG</h2>
          <div class="list">
            <article class="card">
              <h3>Betreiber</h3>
              <p>
                Bea Fitness Community<br>
                vertreten durch Bea Beispiel<br>
                Trainingsweg 10<br>
                10115 Berlin<br>
                Deutschland
              </p>
            </article>
            <article class="card">
              <h3>Kontakt</h3>
              <p>
                Telefon: +49 30 12345678<br>
                E-Mail: impressum@bea-fitness.example
              </p>
            </article>
            <article class="card">
              <h3>Verantwortlich für Inhalte</h3>
              <p>
                Bea Beispiel<br>
                Trainingsweg 10<br>
                10115 Berlin
              </p>
              <p class="subtle">Verantwortlich nach Paragraf 18 Abs. 2 MStV.</p>
            </article>
          </div>
        </article>

        <article class="panel">
          <h2>Hinweise</h2>
          <div class="list">
            <article class="card area-nutrition">
              <h3>Fiktives Muster</h3>
              <p class="subtle">Dieses Impressum ist frei erfunden und dient nur als Platzhalter. Vor einer echten Veröffentlichung müssen Name, Anschrift, Kontakt, Verantwortliche und weitere Pflichtangaben durch echte Daten ersetzt und rechtlich geprüft werden.</p>
            </article>
            <article class="card area-endurance">
              <h3>Umsatzsteuer</h3>
              <p class="subtle">Keine Umsatzsteuer-ID hinterlegt, da dieses Projekt aktuell als privates Musterprojekt geführt wird.</p>
            </article>
            <article class="card area-team">
              <h3>Streitbeilegung</h3>
              <p class="subtle">Wir sind weder verpflichtet noch bereit, an Streitbeilegungsverfahren vor einer Verbraucherschlichtungsstelle teilzunehmen.</p>
            </article>
          </div>
        </article>
      </section>
    """
    return render_layout("/impressum", "Impressum", body)


async def read_json_payload(request: Request) -> dict:
    try:
        payload = await request.json()
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail={"message": "Ungültige Anfrage."}) from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail={"message": "Ungültige Anfrage."})
    return payload


def save_action(action, payload: dict, message: str) -> dict[str, str]:
    state = load_state()
    try:
        action(state, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"message": str(exc)}) from exc
    save_state(state)
    return {"message": message}


@app.post("/api/questionnaire")
async def api_questionnaire(request: Request) -> dict[str, str]:
    state = load_state()
    try:
        plan = create_personal_plan(state, await read_json_payload(request))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"message": str(exc)}) from exc
    save_state(state)
    return {"message": f"{plan.get('plan_reason', 'Check-in')} gespeichert. Trainingsplan und Ernährungsplan wurden angepasst."}


@app.post("/api/sport")
async def api_add_sport(request: Request) -> dict[str, str]:
    return save_action(add_sport_entry, await read_json_payload(request), "Sporteintrag gespeichert.")


@app.post("/api/mindset")
async def api_add_mindset(request: Request) -> dict[str, str]:
    payload = await read_json_payload(request)
    member_id = current_member_id(request)
    if not member_id:
        raise HTTPException(status_code=401, detail={"message": "Bitte anmelden, bevor Mindset-Übungen gespeichert werden."})
    payload["member_id"] = member_id
    return save_action(add_mindset_entry, payload, "Mindset-Übung gespeichert. XP wurden gutgeschrieben.")


@app.post("/api/nutrition")
async def api_add_nutrition(request: Request) -> dict[str, str]:
    return save_action(add_nutrition_entry, await read_json_payload(request), "Nahrung gespeichert.")


@app.post("/api/weight")
async def api_add_weight(request: Request) -> dict[str, str]:
    return save_action(add_weight_entry, await read_json_payload(request), "Gewicht gespeichert.")


@app.post("/api/foods")
async def api_add_food(request: Request) -> dict[str, str]:
    return save_action(add_food_item, await read_json_payload(request), "Lebensmittel gespeichert.")


@app.post("/api/youtube")
async def api_add_youtube(request: Request) -> dict[str, str]:
    return save_action(add_youtube_link, await read_json_payload(request), "YouTube-Video gespeichert.")


@app.post("/api/assignments")
async def api_add_assignment(request: Request) -> dict[str, str]:
    return save_action(add_assignment, await read_json_payload(request), "Aufgabe zugewiesen.")


@app.post("/api/assignments/complete")
async def api_complete_assignment(request: Request) -> dict[str, str]:
    payload = await read_json_payload(request)
    state = load_state()
    try:
        complete_assignment(state, str(payload.get("assignment_id") or ""))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"message": str(exc)}) from exc
    save_state(state)
    return {"message": "Aufgabe erledigt."}


@app.post("/api/motivations")
async def api_add_motivation(request: Request) -> dict[str, str]:
    return save_action(add_motivation, await read_json_payload(request), "Motivation gesendet.")


@app.post("/api/groups/create")
async def api_create_group(request: Request) -> dict[str, str]:
    state = load_state()
    try:
        group = create_group(state, await read_json_payload(request))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"message": str(exc)}) from exc
    save_state(state)
    return {"message": f"Gruppe {group['name']} erstellt."}


@app.post("/api/groups/join")
async def api_join_group(request: Request) -> dict[str, str]:
    state = load_state()
    payload = await read_json_payload(request)
    try:
        group = join_group(state, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"message": str(exc)}) from exc
    save_state(state)
    return {"message": f"{member_name(state, payload.get('member_id', ''))} ist jetzt in {group['name']}."}


@app.post("/api/challenges/create")
async def api_create_challenge(request: Request) -> dict[str, str]:
    state = load_state()
    try:
        challenge = create_challenge(state, await read_json_payload(request))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"message": str(exc)}) from exc
    save_state(state)
    return {"message": f"Challenge {challenge['title']} erstellt."}


@app.post("/api/challenges/progress")
async def api_add_challenge_progress(request: Request) -> dict[str, str]:
    return save_action(add_challenge_progress, await read_json_payload(request), "Challenge aktualisiert.")


@app.post("/api/rpg/quests/complete")
async def api_complete_rpg_quest(request: Request) -> dict[str, str]:
    state = load_state()
    try:
        result = complete_daily_quest(state, await read_json_payload(request))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"message": str(exc)}) from exc
    save_state(state)

    messages = [
        f'{result["character"]["name"]} hat die Quest abgeschlossen.',
        f'{result["daily_result"]["damage"]} Schaden am Tagesboss.',
        f'{result["weekly_result"]["damage"]} Schaden am Wochenboss.',
    ]
    if result["daily_result"]["defeated"]:
        messages.append("Tagesboss besiegt.")
    if result["weekly_result"]["defeated"]:
        messages.append("Wochenboss besiegt.")
    return {"message": " ".join(messages)}


@app.post("/api/journey/complete")
async def api_complete_journey_lesson(request: Request) -> dict[str, str]:
    payload = await read_json_payload(request)
    state = load_state()
    member_id = current_member_id(request)
    if not member_id:
        raise HTTPException(status_code=401, detail={"message": "Bitte anmelden, bevor eine Lektion abgeschlossen wird."})
    try:
        result = complete_health_journey_lesson(state, member_id, str(payload.get("lesson_id") or ""))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"message": str(exc)}) from exc
    save_state(state)
    lesson = result["lesson"]
    return {"message": f"Lektion abgeschlossen: {lesson['title']}. Morgen wird die nächste Etappe freigeschaltet."}


@app.post("/api/settings/location")
async def api_update_location(request: Request) -> dict[str, str]:
    return save_action(update_settings, await read_json_payload(request), "Standort gespeichert.")


@app.get("/integrationen/strava/start")
def strava_start(request: Request, member_id: str = "bea") -> RedirectResponse:
    if not strava_is_configured():
        raise HTTPException(
            status_code=400,
            detail={"message": "Strava ist noch nicht konfiguriert."},
        )

    state = load_state()
    oauth_state = secrets.token_urlsafe(24)
    try:
        strava_store_pending(state, oauth_state, member_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"message": str(exc)}) from exc
    save_state(state)

    return RedirectResponse(
        strava_authorization_url(strava_redirect_uri(request), oauth_state),
        status_code=303,
    )


@app.get("/integrationen/strava/callback", name="strava_callback")
def strava_callback(request: Request) -> RedirectResponse:
    error = request.query_params.get("error")
    if error:
        raise HTTPException(
            status_code=400,
            detail={"message": f"Strava-Verbindung abgebrochen: {error}"},
        )

    code = request.query_params.get("code", "")
    oauth_state = request.query_params.get("state", "")
    if not code or not oauth_state:
        raise HTTPException(
            status_code=400,
            detail={"message": "Strava Callback ist unvollständig."},
        )

    state = load_state()
    try:
        member_id = strava_consume_pending(state, oauth_state)
        token_payload = exchange_strava_code(code)
        strava_set_connection(state, member_id, token_payload)
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail={"message": f"Strava konnte nicht verbunden werden: {exc}"},
        ) from exc

    save_state(state)
    return RedirectResponse("/integrationen", status_code=303)


@app.post("/api/integrations/strava/sync")
async def api_strava_sync(request: Request) -> dict[str, str]:
    if not strava_is_configured():
        raise HTTPException(
            status_code=400,
            detail={"message": "Strava ist noch nicht konfiguriert."},
        )

    payload = await read_json_payload(request)
    member_id = str(payload.get("member_id") or "")
    state = load_state()
    connection = strava_get_connection(state, member_id)
    if not connection:
        raise HTTPException(
            status_code=400,
            detail={"message": "Dieses Mitglied hat Strava noch nicht verbunden."},
        )

    try:
        access_token, refreshed = strava_access_token(connection)
        if refreshed:
            strava_update_connection(state, member_id, refreshed)
        activities = fetch_strava_activities(access_token)
        imported = 0
        for activity in activities:
            entry = add_external_sport_entry(state, strava_activity_payload(activity, member_id))
            if entry:
                imported += 1
        strava_set_last_sync(state, member_id)
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail={"message": f"Strava Sync fehlgeschlagen: {exc}"},
        ) from exc

    save_state(state)
    return {"message": f"Strava synchronisiert: {imported} neue Aktivitäten importiert."}


@app.post("/api/photos/pin")
async def api_set_photo_pin(request: Request) -> dict[str, str]:
    payload = await read_json_payload(request)
    state = load_state()
    try:
        set_photo_pin(
            state,
            str(payload.get("member_id") or ""),
            str(payload.get("pin") or ""),
            str(payload.get("current_pin") or ""),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"message": str(exc)}) from exc
    save_state(state)
    return {"message": "Foto-PIN gespeichert."}


@app.post("/api/avatar")
async def api_save_avatar(request: Request) -> dict[str, str]:
    payload = await read_json_payload(request)
    state = load_state()
    member_id = str(payload.get("member_id") or "")
    pin = str(payload.get("pin") or "")

    try:
        require_photo_pin(state, member_id, pin)
        photo_ids = {}
        if payload.get("front_image_data"):
            photo = add_private_photo(
                state,
                {
                    "member_id": member_id,
                    "pin": pin,
                    "image_data": payload.get("front_image_data"),
                    "title": f"Avatar Front {member_name(state, member_id)}",
                    "photo_type": "Avatar Ganzkörper Front",
                    "note": "Privates Kalibrierfoto für den Avatar.",
                },
            )
            photo_ids["front_photo_id"] = photo["id"]
        if payload.get("side_image_data"):
            photo = add_private_photo(
                state,
                {
                    "member_id": member_id,
                    "pin": pin,
                    "image_data": payload.get("side_image_data"),
                    "title": f"Avatar Seite {member_name(state, member_id)}",
                    "photo_type": "Avatar Ganzkörper Seite",
                    "note": "Privates Kalibrierfoto für den Avatar.",
                },
            )
            photo_ids["side_photo_id"] = photo["id"]
        profile = save_avatar_profile(state, payload, photo_ids)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"message": str(exc)}) from exc

    save_state(state)
    return {"message": f"Avatar gespeichert: Körperbau {profile['body_label']}. Kalibrierfotos bleiben privat."}


@app.post("/api/photos/upload")
async def api_upload_photo(request: Request) -> dict[str, str]:
    payload = await read_json_payload(request)
    state = load_state()
    try:
        add_private_photo(state, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"message": str(exc)}) from exc
    save_state(state)
    return {"message": "Vergleichsfoto privat gespeichert."}


@app.post("/api/photos/private")
async def api_private_photos(request: Request) -> dict[str, object]:
    payload = await read_json_payload(request)
    state = load_state()
    try:
        photos = private_photos_for_member(
            state,
            str(payload.get("member_id") or ""),
            str(payload.get("pin") or ""),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"message": str(exc)}) from exc
    return {"message": f"{len(photos)} private Fotos geladen.", "photos": photos}


@app.post("/api/photos/publish")
async def api_publish_photo(request: Request) -> dict[str, str]:
    payload = await read_json_payload(request)
    state = load_state()
    try:
        publish_photo(
            state,
            str(payload.get("member_id") or ""),
            str(payload.get("pin") or ""),
            str(payload.get("photo_id") or ""),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"message": str(exc)}) from exc
    save_state(state)
    return {"message": "Foto ist jetzt in der Community sichtbar."}


@app.post("/update")
def update_from_github() -> dict[str, str]:
    git = shutil.which("git")
    if git is None:
        raise HTTPException(
            status_code=500,
            detail={"message": "Git ist auf diesem System nicht installiert."},
        )

    try:
        result = subprocess.run(
            [git, "pull", "--ff-only"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise HTTPException(
            status_code=500,
            detail={"message": "GitHub Update hat zu lange gedauert.", "output": str(exc)},
        ) from exc

    output = _combined_output(result)
    if result.returncode != 0:
        raise HTTPException(
            status_code=500,
            detail={"message": "GitHub Update fehlgeschlagen.", "output": output},
        )

    message = _restart_service_soon()
    return {"message": message, "output": output}
