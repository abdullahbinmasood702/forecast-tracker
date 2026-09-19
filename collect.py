"""Fetch today's forecasts (lead 0-7 days) for every city and store them."""
import requests
from psycopg2.extras import execute_values

from config import CITIES, DAILY_VARS, FORECAST_DAYS
from db import get_conn

URL = "https://api.open-meteo.com/v1/forecast"


def fetch_forecast(lat, lon):
    r = requests.get(
        URL,
        params={
            "latitude": lat,
            "longitude": lon,
            "daily": ",".join(DAILY_VARS),
            "forecast_days": FORECAST_DAYS,
            "timezone": "auto",  # dates come back in the city's local time
        },
        timeout=30,
    )
    r.raise_for_status()
    return r.json()["daily"]


def main():
    rows = []
    for city, (lat, lon) in CITIES.items():
        daily = fetch_forecast(lat, lon)
        issued = daily["time"][0]  # local "today" for this city
        for i, target in enumerate(daily["time"]):
            rows.append((
                city, issued, target, i,
                daily["temperature_2m_max"][i],
                daily["temperature_2m_min"][i],
                daily["precipitation_sum"][i],
                daily["wind_speed_10m_max"][i],
            ))

    conn = get_conn()
    try:
        with conn, conn.cursor() as cur:
            execute_values(
                cur,
                """
                INSERT INTO forecasts
                  (city, issued_date, target_date, lead_days,
                   temp_max, temp_min, precip_sum, wind_max)
                VALUES %s
                ON CONFLICT (city, issued_date, target_date) DO NOTHING
                """,
                rows,
            )
    finally:
        conn.close()
    print(f"Stored {len(rows)} forecast rows for {len(CITIES)} cities.")


if __name__ == "__main__":
    main()
