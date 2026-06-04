from __future__ import annotations

import html
import json
import os
import shlex
import shutil
import signal
import subprocess
import threading
import time
from pathlib import Path

from fastapi import FastAPI
from fastapi import HTTPException
from fastapi import Request
from fastapi.responses import HTMLResponse

from app.state import AREA_LABELS
from app.state import AREAS
from app.state import add_assignment
from app.state import add_challenge_progress
from app.state import add_motivation
from app.state import add_nutrition_entry
from app.state import add_sport_entry
from app.state import complete_assignment
from app.state import leaderboard
from app.state import level_for_xp
from app.state import load_state
from app.state import member_name
from app.state import save_state
from app.state import team_totals
from app.state import total_xp

app = FastAPI(title="Bea")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SERVICE_NAME = os.getenv("BEA_SERVICE_NAME", "bea.service")

NAV_ITEMS = (
    ("/", "Dashboard"),
    ("/freunde", "Freunde"),
    ("/challenges", "Challenges"),
    ("/sport", "Sport"),
    ("/nahrung", "Nahrung"),
)


def h(value: object) -> str:
    return html.escape(str(value), quote=True)


def _combined_output(result: subprocess.CompletedProcess[str]) -> str:
    output = "\n".join(part for part in (result.stdout, result.stderr) if part)
    return output.strip() or "Kein Output."


def _restart_service_soon() -> None:
    def restart() -> None:
        time.sleep(1.5)

        restart_command = os.getenv("BEA_RESTART_COMMAND")
        if restart_command:
            command = shlex.split(restart_command)
        else:
            systemctl = shutil.which("systemctl")
            sudo = shutil.which("sudo")

            if systemctl and sudo:
                command = [sudo, "systemctl", "restart", SERVICE_NAME]
            elif systemctl:
                command = [systemctl, "restart", SERVICE_NAME]
            else:
                os.kill(os.getpid(), signal.SIGTERM)
                return

        subprocess.Popen(
            command,
            cwd=PROJECT_ROOT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )

    threading.Thread(target=restart, daemon=True).start()


def area_class(area: str) -> str:
    return {
        "endurance": "area-endurance",
        "strength": "area-strength",
        "nutrition": "area-nutrition",
        "team": "area-team",
    }.get(area, "area-team")


def render_member_options(state: dict, selected: str = "") -> str:
    return "\n".join(
        f'<option value="{h(member["id"])}" {"selected" if member["id"] == selected else ""}>{h(member["name"])}</option>'
        for member in state["members"]
    )


def render_category_options(selected: str = "strength") -> str:
    return "\n".join(
        f'<option value="{h(area)}" {"selected" if area == selected else ""}>{h(AREA_LABELS[area])}</option>'
        for area in ("strength", "endurance", "nutrition")
    )


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
        <small>{xp} XP / naechstes Level bei {level["next_xp"]} XP</small>
      </article>
    """


def render_layout(active_path: str, title: str, body: str) -> str:
    nav = "\n".join(
        f'<a class="{"is-active" if path == active_path else ""}" href="{path}">{label}</a>'
        for path, label in NAV_ITEMS
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
            --ink: #17212b;
            --muted: #637083;
            --line: #d9e0df;
            --surface: #ffffff;
            --page: #f4f6f2;
            --green: #1f5c4d;
            --blue: #295d8f;
            --red: #a33a3a;
            --gold: #9a6b16;
          }}

          * {{
            box-sizing: border-box;
          }}

          body {{
            margin: 0;
            min-height: 100vh;
            background:
              linear-gradient(135deg, rgb(31 92 77 / 8%), transparent 28rem),
              linear-gradient(315deg, rgb(41 93 143 / 8%), transparent 24rem),
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

          .topbar {{
            position: sticky;
            top: 0;
            z-index: 5;
            display: grid;
            grid-template-columns: auto 1fr auto;
            gap: 1rem;
            align-items: center;
            padding: 0.85rem clamp(1rem, 3vw, 2.5rem);
            border-bottom: 1px solid var(--line);
            background: rgb(244 246 242 / 92%);
            backdrop-filter: blur(14px);
          }}

          .brand {{
            display: flex;
            align-items: center;
            gap: 0.65rem;
            font-weight: 850;
          }}

          .brand-mark {{
            display: grid;
            width: 2.25rem;
            height: 2.25rem;
            place-items: center;
            border-radius: 0.45rem;
            background: var(--ink);
            color: #fff;
          }}

          .nav {{
            display: flex;
            gap: 0.35rem;
            justify-content: center;
            overflow-x: auto;
          }}

          .nav a {{
            flex: 0 0 auto;
            border-radius: 0.45rem;
            padding: 0.65rem 0.85rem;
            color: var(--muted);
            font-weight: 700;
          }}

          .nav a.is-active {{
            background: var(--ink);
            color: #fff;
          }}

          .update-form {{
            margin: 0;
          }}

          .button,
          .update-button {{
            border: 0;
            border-radius: 0.5rem;
            padding: 0.72rem 0.95rem;
            background: var(--green);
            color: #ffffff;
            font-weight: 800;
            cursor: pointer;
          }}

          .button.secondary {{
            background: #e7ecea;
            color: var(--ink);
          }}

          .button.blue {{
            background: var(--blue);
          }}

          .button.red {{
            background: var(--red);
          }}

          .button:disabled,
          .update-button:disabled {{
            cursor: wait;
            opacity: 0.7;
          }}

          .page {{
            width: min(1180px, calc(100vw - 2rem));
            margin: 0 auto;
            padding: 1.35rem 0 3rem;
          }}

          .page-heading {{
            display: grid;
            grid-template-columns: minmax(0, 1fr) auto;
            gap: 1rem;
            align-items: end;
            margin: 0.4rem 0 1rem;
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
            font-size: clamp(2.4rem, 6vw, 5.25rem);
            line-height: 0.95;
            letter-spacing: 0;
          }}

          h2 {{
            margin-bottom: 0.8rem;
            font-size: 1.25rem;
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
            border: 1px solid var(--line);
            border-radius: 0.5rem;
            background: rgb(255 255 255 / 88%);
            box-shadow: 0 0.9rem 2.5rem rgb(23 33 43 / 8%);
          }}

          .panel {{
            padding: 1rem;
          }}

          .card {{
            padding: 0.95rem;
          }}

          .stat-card {{
            padding: 1rem;
          }}

          .stat-card strong {{
            display: block;
            font-size: 2rem;
            line-height: 1;
          }}

          .stat-card span,
          .level-meter small,
          .meta {{
            color: var(--muted);
            font-size: 0.9rem;
          }}

          .level-meter {{
            display: grid;
            gap: 0.65rem;
            padding: 1rem;
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
            height: 0.65rem;
            overflow: hidden;
            border-radius: 999px;
            background: #e3e8e5;
          }}

          .progress span {{
            display: block;
            height: 100%;
            border-radius: inherit;
            background: var(--green);
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

          .form-grid {{
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 0.75rem;
          }}

          .form-grid .full {{
            grid-column: 1 / -1;
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
            background: #fff;
            color: var(--ink);
          }}

          textarea {{
            min-height: 5.5rem;
            resize: vertical;
          }}

          table {{
            width: 100%;
            border-collapse: collapse;
          }}

          th,
          td {{
            padding: 0.75rem 0.5rem;
            border-bottom: 1px solid var(--line);
            text-align: left;
            vertical-align: top;
          }}

          th {{
            color: var(--muted);
            font-size: 0.78rem;
            text-transform: uppercase;
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

          .update-status.is-visible {{
            opacity: 1;
            transform: translateY(0);
          }}

          @media (max-width: 840px) {{
            .topbar,
            .page-heading {{
              grid-template-columns: 1fr;
              align-items: start;
            }}

            .nav {{
              justify-content: start;
            }}

            .grid.two,
            .grid.three,
            .grid.four,
            .form-grid {{
              grid-template-columns: 1fr;
            }}
          }}
        </style>
      </head>
      <body>
        <header class="topbar">
          <a class="brand" href="/">
            <span class="brand-mark">B</span>
            <span>Bea</span>
          </a>
          <nav class="nav" aria-label="Hauptnavigation">
            {nav}
          </nav>
          <form class="update-form" id="update-form">
            <button class="update-button" id="update-button" type="submit">GitHub Update</button>
          </form>
        </header>
        <main class="page">
          {body}
        </main>
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

          document.querySelectorAll("[data-api-form]").forEach((form) => {{
            form.addEventListener("submit", async (event) => {{
              event.preventDefault();
              const button = form.querySelector("button[type='submit']");
              if (button) {{
                button.disabled = true;
              }}
              try {{
                const payload = Object.fromEntries(new FormData(form).entries());
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

          const updateForm = document.querySelector("#update-form");
          const updateButton = document.querySelector("#update-button");
          updateForm.addEventListener("submit", async (event) => {{
            event.preventDefault();
            updateButton.disabled = true;
            updateButton.textContent = "Aktualisiere...";
            showStatus("Update wird geladen.");

            try {{
              const data = await postJson("/update", {{}});
              showStatus(data.message || "Update geladen. Dienst wird neu gestartet.");
              window.setTimeout(() => window.location.reload(), 4500);
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
        ("Eintraege", sport_count + meal_count),
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


def render_challenge_card(state: dict, challenge: dict, with_form: bool = False) -> str:
    total_progress = sum(int(value) for value in challenge.get("participants", {}).values())
    progress = int((total_progress / max(1, int(challenge["goal"]))) * 100)
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
              <select name="member_id">{render_member_options(state)}</select>
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
            <p class="subtle">{h(AREA_LABELS[challenge["category"]])} · Bonus {h(challenge["xp"])} XP</p>
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


@app.get("/", response_class=HTMLResponse)
def dashboard() -> str:
    state = load_state()
    totals = team_totals(state)
    level_cards = "".join(level_meter(AREA_LABELS[area], totals[area], area) for area in AREAS)
    challenges = "".join(render_challenge_card(state, challenge) for challenge in state["challenges"][:3])
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
          <p class="eyebrow">Team Dashboard</p>
          <h1>Hallo Bea</h1>
        </div>
        <p class="subtle">Gemeinsame Fortschritte, Level und Aufgaben auf einen Blick.</p>
      </section>

      <section class="grid four">
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
          <h2>Uebung zuweisen</h2>
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
              Faellig
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
              Uebung
              <input name="title" placeholder="Bankdruecken, Kniebeugen">
            </label>
            <label>
              Umfang
              <input name="amount" placeholder="4x8">
            </label>
            <label class="full">
              Dauer in Minuten
              <input name="duration" type="number" min="1" value="45">
            </label>
            <button class="button red full" type="submit">Kraft speichern</button>
          </form>
        </div>
      </section>

      <section class="panel" style="margin-top: 1rem;">
        <h2>Letzte Sporteintraege</h2>
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
            </tr>
          </thead>
          <tbody>{"".join(rows)}</tbody>
        </table>
      </section>
    """
    return render_layout("/sport", "Sport", body)


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
              <td>{h(entry["meal"])}</td>
              <td>{h(entry["protein"])} g</td>
              <td>{h(entry["calories"])} kcal</td>
              <td>{h(entry["water"])} l</td>
              <td>{h(entry["xp"])} XP</td>
            </tr>
            """
        )

    protein_total = sum(int(entry["protein"]) for entry in state["nutrition_entries"])
    water_total = sum(float(entry["water"]) for entry in state["nutrition_entries"])

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
          <span>Eintraege</span>
          <strong>{h(len(state["nutrition_entries"]))}</strong>
        </article>
      </section>

      <section class="grid two" style="margin-top: 1rem;">
        <div class="panel">
          <h2>Mahlzeit eintragen</h2>
          <form class="form-grid" data-api-form data-endpoint="/api/nutrition">
            <label>
              Mitglied
              <select name="member_id">{render_member_options(state, "bea")}</select>
            </label>
            <label>
              Mahlzeit
              <input name="meal" placeholder="Quark Bowl">
            </label>
            <label>
              Protein in g
              <input name="protein" type="number" min="0" value="30">
            </label>
            <label>
              Kalorien
              <input name="calories" type="number" min="0" value="550">
            </label>
            <label class="full">
              Wasser in l
              <input name="water" type="number" min="0" step="0.1" value="0.5">
            </label>
            <button class="button full" type="submit">Nahrung speichern</button>
          </form>
        </div>
        <div class="panel">
          <h2>Nahrungs-Level</h2>
          <div class="grid two">
            {"".join(level_meter(member["name"], int(member["xp"].get("nutrition", 0)), "nutrition") for member in leaderboard(state))}
          </div>
        </div>
      </section>

      <section class="panel" style="margin-top: 1rem;">
        <h2>Letzte Nahrungseintraege</h2>
        <table>
          <thead>
            <tr>
              <th>Datum</th>
              <th>Mitglied</th>
              <th>Mahlzeit</th>
              <th>Protein</th>
              <th>Kalorien</th>
              <th>Wasser</th>
              <th>XP</th>
            </tr>
          </thead>
          <tbody>{"".join(rows)}</tbody>
        </table>
      </section>
    """
    return render_layout("/nahrung", "Nahrung", body)


async def read_json_payload(request: Request) -> dict:
    try:
        payload = await request.json()
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail={"message": "Ungueltige Anfrage."}) from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail={"message": "Ungueltige Anfrage."})
    return payload


def save_action(action, payload: dict, message: str) -> dict[str, str]:
    state = load_state()
    try:
        action(state, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"message": str(exc)}) from exc
    save_state(state)
    return {"message": message}


@app.post("/api/sport")
async def api_add_sport(request: Request) -> dict[str, str]:
    return save_action(add_sport_entry, await read_json_payload(request), "Sporteintrag gespeichert.")


@app.post("/api/nutrition")
async def api_add_nutrition(request: Request) -> dict[str, str]:
    return save_action(add_nutrition_entry, await read_json_payload(request), "Nahrung gespeichert.")


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


@app.post("/api/challenges/progress")
async def api_add_challenge_progress(request: Request) -> dict[str, str]:
    return save_action(add_challenge_progress, await read_json_payload(request), "Challenge aktualisiert.")


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

    _restart_service_soon()
    return {"message": "Update geladen. Dienst wird neu gestartet.", "output": output}
