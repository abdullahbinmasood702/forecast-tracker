"""Fill in what actually happened for past forecast dates.

Uses Open-Meteo's archive (reanalysis) data, which lags a few days.
Dates that are not available yet come back empty and are retried next run.
"""
from datetime import date, timedelta

import requests
from psycopg2.extras import execute_values

from config import CITIES, DAILY_VARS
from db import get_conn

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
MIN_AGE_DAYS = 3  # don't even ask for dates newer than this


def fetch_actuals(lat, lon, start, end):
    r = requests.get(
        ARCHIVE_URL,
        params={
            "latitude": lat,
            "longitude": lon,
            "start_date": start,
            "end_date": end,
            "daily": ",".join(DAILY_VARS),
            "timezone": "auto",
        },
        timeout=60,
    )
    r.raise_for_status()
    return r.json()["daily"]


def main():
    cutoff = date.today() - timedelta(days=MIN_AGE_DAYS)
    conn = get_conn()
    total = 0
    try:
        with conn, conn.cursor() as cur:
            # Which (city, date) pairs have forecasts but no actuals yet?
            cur.execute(
                """
                SELECT f.city, MIN(f.target_date), MAX(f.target_date)
                FROM forecasts f
                LEFT JOIN actuals a
                  ON a.city = f.city AND a.date = f.target_date
                WHERE f.target_date <= %s AND a.date IS NULL
                GROUP BY f.city
                """,
                (cutoff,),
            )
            todo = cur.fetchall()

            for city, start, end in todo:
                if city not in CITIES:
                    continue
                lat, lon = CITIES[city]
                d = fetch_actuals(lat, lon, start.isoformat(), end.isoformat())
                rows = []
                for i, day in enumerate(d["time"]):
                    tmax = d["temperature_2m_max"][i]
                    if tmax is None:  # not available yet
                        continue
                    rows.append((
                        city, day, tmax,
                        d["temperature_2m_min"][i],
                        d["precipitation_sum"][i],
                        d["wind_speed_10m_max"][i],
                    ))
                if rows:
                    execute_values(
                        cur,
                        """
                        INSERT INTO actuals
                          (city, date, temp_max, temp_min, precip_sum, wind_max)
                        VALUES %s
                        ON CONFLICT (city, date) DO NOTHING
                        """,
                        rows,
                    )
                    total += len(rows)
    finally:
        conn.close()
    print(f"Stored {total} actual rows.")


if __name__ == "__main__":
    main()
