from __future__ import annotations

import json
import urllib.parse
import urllib.request

WEATHER_LABELS = {
    0: "Klar",
    1: "Ueberwiegend klar",
    2: "Teilweise bewoelkt",
    3: "Bewoelkt",
    45: "Nebel",
    48: "Raureifnebel",
    51: "Leichter Nieselregen",
    53: "Nieselregen",
    55: "Starker Nieselregen",
    61: "Leichter Regen",
    63: "Regen",
    65: "Starker Regen",
    71: "Leichter Schnee",
    73: "Schnee",
    75: "Starker Schnee",
    80: "Leichte Schauer",
    81: "Schauer",
    82: "Starke Schauer",
    95: "Gewitter",
    96: "Gewitter mit Hagel",
    99: "Starkes Gewitter mit Hagel",
}

SEVERE_CODES = {65, 75, 82, 95, 96, 99}


def fetch_forecast(settings: dict) -> dict:
    latitude = float(settings.get("latitude", 52.52))
    longitude = float(settings.get("longitude", 13.405))
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "daily": ",".join(
            (
                "weather_code",
                "temperature_2m_max",
                "temperature_2m_min",
                "precipitation_probability_max",
                "wind_speed_10m_max",
            )
        ),
        "timezone": "Europe/Berlin",
        "forecast_days": 5,
        "wind_speed_unit": "kmh",
    }
    url = f"https://api.open-meteo.com/v1/forecast?{urllib.parse.urlencode(params)}"

    try:
        with urllib.request.urlopen(url, timeout=8) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as exc:  # Network or remote API issues should not break the app.
        return {"days": [], "error": str(exc), "url": url}

    daily = payload.get("daily", {})
    days = []
    for index, day in enumerate(daily.get("time", [])):
        code = int((daily.get("weather_code") or [0])[index])
        forecast_day = {
            "date": day,
            "code": code,
            "label": WEATHER_LABELS.get(code, "Wetterlage"),
            "temp_max": round(float((daily.get("temperature_2m_max") or [0])[index]), 1),
            "temp_min": round(float((daily.get("temperature_2m_min") or [0])[index]), 1),
            "rain": int((daily.get("precipitation_probability_max") or [0])[index]),
            "wind": round(float((daily.get("wind_speed_10m_max") or [0])[index]), 1),
        }
        forecast_day["plan"] = recommend_activity(forecast_day)
        days.append(forecast_day)

    return {"days": days, "error": None, "url": url}


def recommend_activity(day: dict) -> dict[str, str]:
    rain = int(day["rain"])
    wind = float(day["wind"])
    temp_max = float(day["temp_max"])
    temp_min = float(day["temp_min"])
    code = int(day["code"])

    if code in SEVERE_CODES or rain >= 70 or wind >= 45 or temp_max >= 31 or temp_min <= -3:
        return {
            "activity": "Laufband im Fitnessstudio",
            "level": "studio",
            "reason": "Wetterrisiko ist hoch: drinnen trainierst du planbarer.",
        }

    if wind <= 24 and rain <= 35 and 8 <= temp_max <= 28:
        return {
            "activity": "Fahrrad draussen",
            "level": "outdoor",
            "reason": "Wind und Regenwahrscheinlichkeit passen gut fuer eine Radtour.",
        }

    if rain <= 45 and temp_min >= 0 and temp_max <= 29:
        return {
            "activity": "Laufen draussen",
            "level": "outdoor",
            "reason": "Gute Bedingungen fuer eine flexible Laufeinheit.",
        }

    if rain <= 40 and wind <= 35:
        return {
            "activity": "Wandern",
            "level": "outdoor",
            "reason": "Es ist nicht perfekt, aber fuer eine ruhige Ausdauereinheit draussen geeignet.",
        }

    return {
        "activity": "Laufband im Fitnessstudio",
        "level": "studio",
        "reason": "Outdoor geht, aber Studio ist heute die stressfreiere Wahl.",
    }
