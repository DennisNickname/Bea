from __future__ import annotations

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
from fastapi.responses import HTMLResponse

app = FastAPI(title="Bea")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SERVICE_NAME = os.getenv("BEA_SERVICE_NAME", "bea.service")


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


@app.get("/", response_class=HTMLResponse)
def home() -> str:
    return """
    <!doctype html>
    <html lang="de">
      <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>Bea</title>
        <style>
          :root {
            color-scheme: light;
            font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
          }

          body {
            margin: 0;
            min-height: 100vh;
            display: grid;
            place-items: center;
            background: #f4f6f2;
            color: #18202a;
          }

          main {
            text-align: center;
          }

          h1 {
            margin: 0;
            font-size: clamp(3rem, 10vw, 7rem);
            font-weight: 800;
            letter-spacing: 0;
          }

          .update-form {
            position: fixed;
            top: 1rem;
            right: 1rem;
          }

          .update-button {
            border: 0;
            border-radius: 0.5rem;
            padding: 0.75rem 1rem;
            background: #1f5c4d;
            color: #ffffff;
            font: inherit;
            font-weight: 700;
            cursor: pointer;
            box-shadow: 0 0.75rem 2rem rgb(24 32 42 / 18%);
          }

          .update-button:disabled {
            cursor: wait;
            opacity: 0.7;
          }

          .update-status {
            position: fixed;
            right: 1rem;
            bottom: 1rem;
            max-width: min(24rem, calc(100vw - 2rem));
            border-radius: 0.5rem;
            padding: 0.85rem 1rem;
            background: #18202a;
            color: #ffffff;
            font-size: 0.95rem;
            line-height: 1.4;
            opacity: 0;
            transform: translateY(0.5rem);
            transition: opacity 160ms ease, transform 160ms ease;
            pointer-events: none;
          }

          .update-status.is-visible {
            opacity: 1;
            transform: translateY(0);
          }
        </style>
      </head>
      <body>
        <form class="update-form" id="update-form">
          <button class="update-button" id="update-button" type="submit">GitHub Update</button>
        </form>
        <main>
          <h1>Hallo Bea</h1>
        </main>
        <p class="update-status" id="update-status" role="status" aria-live="polite"></p>
        <script>
          const form = document.querySelector("#update-form");
          const button = document.querySelector("#update-button");
          const status = document.querySelector("#update-status");

          function showStatus(message) {
            status.textContent = message;
            status.classList.add("is-visible");
          }

          form.addEventListener("submit", async (event) => {
            event.preventDefault();
            button.disabled = true;
            button.textContent = "Aktualisiere...";
            showStatus("Update wird geladen.");

            try {
              const response = await fetch("/update", { method: "POST" });
              const payload = await response.json();
              if (!response.ok) {
                const detail = payload.detail || {};
                throw new Error(detail.message || payload.message || "Update fehlgeschlagen.");
              }
              showStatus(payload.message || "Update geladen. Dienst wird neu gestartet.");
              window.setTimeout(() => window.location.reload(), 4500);
            } catch (error) {
              showStatus(error.message || "Update fehlgeschlagen.");
              button.disabled = false;
              button.textContent = "GitHub Update";
            }
          });
        </script>
      </body>
    </html>
    """


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
