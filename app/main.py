from fastapi import FastAPI
from fastapi.responses import HTMLResponse

app = FastAPI(title="Bea")


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
            background: #f6f1ea;
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
        </style>
      </head>
      <body>
        <main>
          <h1>Hallo Bea</h1>
        </main>
      </body>
    </html>
    """
