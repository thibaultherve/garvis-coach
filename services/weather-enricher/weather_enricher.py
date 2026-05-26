#!/usr/bin/env python3
"""
Weather Enricher Sidecar for garvis-coach.

Polls InfluxDB for activities that have GPS data but no weather record yet.
Fetches historical weather from Open-Meteo Archive API and writes an
ActivityWeather measurement per activity.

Runs as a cron or loop alongside garmin-fetch-data.
No Garmin credentials needed — reads from InfluxDB only.
"""

import os
import time
import math
import logging
import requests
from datetime import datetime, timezone
from influxdb import InfluxDBClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s [weather] %(message)s")
log = logging.getLogger(__name__)

INFLUXDB_HOST = os.getenv("INFLUXDB_HOST", "influxdb")
INFLUXDB_PORT = int(os.getenv("INFLUXDB_PORT", 8086))
INFLUXDB_USER = os.getenv("INFLUXDB_USERNAME", "influxdb_user")
INFLUXDB_PASS = os.getenv("INFLUXDB_PASSWORD", "influxdb_password")
INFLUXDB_DB = os.getenv("INFLUXDB_DATABASE", "GarminStats")
POLL_INTERVAL = int(os.getenv("WEATHER_POLL_INTERVAL", 600))
LOOKBACK_DAYS = int(os.getenv("WEATHER_LOOKBACK_DAYS", 7))
OPEN_METEO_URL = "https://archive-api.open-meteo.com/v1/archive"


def get_client():
    return InfluxDBClient(
        host=INFLUXDB_HOST, port=INFLUXDB_PORT,
        username=INFLUXDB_USER, password=INFLUXDB_PASS,
        database=INFLUXDB_DB,
    )


def find_activities_without_weather(client, lookback_days=7):
    """Find ActivitySelectors that have GPS data but no ActivityWeather yet."""
    gps_q = (
        f'SELECT DISTINCT("ActivitySelector") AS "sel" '
        f'FROM "ActivityGPS" WHERE time > now() - {lookback_days}d '
        f'AND "Latitude" > 0'
    )
    gps_result = client.query(gps_q)
    gps_selectors = set()
    for row in gps_result.get_points():
        if row.get("sel"):
            gps_selectors.add(row["sel"])

    if not gps_selectors:
        return []

    weather_q = (
        f'SELECT DISTINCT("ActivitySelector") AS "sel" '
        f'FROM "ActivityWeather" WHERE time > now() - {lookback_days + 2}d'
    )
    weather_result = client.query(weather_q)
    weather_selectors = set()
    for row in weather_result.get_points():
        if row.get("sel"):
            weather_selectors.add(row["sel"])

    missing = gps_selectors - weather_selectors
    return list(missing)


def get_activity_start_point(client, activity_selector):
    """Get first GPS point (lat, lon, timestamp) for an activity."""
    q = (
        f'SELECT FIRST("Latitude") AS "lat", "Longitude" AS "lon" '
        f'FROM "ActivityGPS" '
        f'WHERE "ActivitySelector" = \'{activity_selector}\' '
        f'AND "Latitude" > 0 AND "Longitude" IS NOT NULL'
    )
    result = client.query(q)
    points = list(result.get_points())
    if not points:
        return None

    row = points[0]
    lat = row.get("lat")
    lon = row.get("lon")
    ts = row.get("time")

    if lat is None or lon is None or ts is None:
        return None

    return {"lat": lat, "lon": lon, "time": ts, "selector": activity_selector}


def get_activity_duration_hours(client, activity_selector):
    """Get activity duration to know how many hours of weather to fetch."""
    q = (
        f'SELECT MAX("DurationSeconds") AS "dur" FROM "ActivityGPS" '
        f'WHERE "ActivitySelector" = \'{activity_selector}\''
    )
    result = client.query(q)
    points = list(result.get_points())
    if points and points[0].get("dur"):
        return max(1, math.ceil(points[0]["dur"] / 3600))
    return 1


def fetch_weather(lat, lon, date_str, hours_needed=1):
    """Fetch hourly weather from Open-Meteo Archive API."""
    params = {
        "latitude": round(lat, 4),
        "longitude": round(lon, 4),
        "start_date": date_str,
        "end_date": date_str,
        "hourly": ",".join([
            "temperature_2m",
            "relative_humidity_2m",
            "dew_point_2m",
            "apparent_temperature",
            "wind_speed_10m",
            "wind_gusts_10m",
            "wind_direction_10m",
            "precipitation",
            "cloud_cover",
            "pressure_msl",
            "shortwave_radiation",
        ]),
        "timezone": "UTC",
    }

    resp = requests.get(OPEN_METEO_URL, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def compute_wbgt(temp_c, humidity_pct):
    """Simplified outdoor WBGT estimate (no globe thermometer)."""
    e = (humidity_pct / 100.0) * 6.105 * math.exp(17.27 * temp_c / (237.7 + temp_c))
    return round(0.567 * temp_c + 0.393 * e + 3.94, 1)


def extract_hour_data(weather_json, activity_hour_utc):
    """Extract the hourly slot matching the activity start hour."""
    hourly = weather_json.get("hourly", {})
    times = hourly.get("time", [])

    hour_str = activity_hour_utc.strftime("%Y-%m-%dT%H:00")
    if hour_str not in times:
        if times:
            idx = 0
        else:
            return None
    else:
        idx = times.index(hour_str)

    def val(key):
        arr = hourly.get(key, [])
        return arr[idx] if idx < len(arr) else None

    temp = val("temperature_2m")
    humidity = val("relative_humidity_2m")

    data = {
        "temperature_c": temp,
        "humidity_pct": humidity,
        "dew_point_c": val("dew_point_2m"),
        "apparent_temp_c": val("apparent_temperature"),
        "wind_speed_kmh": val("wind_speed_10m"),
        "wind_gust_kmh": val("wind_gusts_10m"),
        "wind_direction_deg": val("wind_direction_10m"),
        "precipitation_mm": val("precipitation"),
        "cloud_cover_pct": val("cloud_cover"),
        "pressure_hpa": val("pressure_msl"),
        "solar_radiation_wm2": val("shortwave_radiation"),
    }

    if temp is not None and humidity is not None:
        data["wbgt_estimated"] = compute_wbgt(temp, humidity)

    return data


def write_weather(client, activity_selector, timestamp_iso, weather_data):
    """Write ActivityWeather measurement to InfluxDB."""
    fields = {k: float(v) for k, v in weather_data.items() if v is not None}
    if not fields:
        return False

    point = {
        "measurement": "ActivityWeather",
        "tags": {
            "ActivitySelector": activity_selector,
        },
        "time": timestamp_iso,
        "fields": fields,
    }
    client.write_points([point])
    return True


def process_one(client, selector):
    """Process a single activity: fetch weather + write to InfluxDB."""
    start = get_activity_start_point(client, selector)
    if not start:
        log.warning("No GPS start point for %s, skipping", selector)
        return False

    ts = datetime.fromisoformat(start["time"].replace("Z", "+00:00"))
    date_str = ts.strftime("%Y-%m-%d")

    log.info(
        "Fetching weather for %s — %.4f, %.4f @ %s",
        selector, start["lat"], start["lon"], ts.isoformat(),
    )

    try:
        weather_json = fetch_weather(start["lat"], start["lon"], date_str)
    except Exception as exc:
        log.error("Open-Meteo API error for %s: %s", selector, exc)
        return False

    hour_data = extract_hour_data(weather_json, ts)
    if not hour_data:
        log.warning("No hourly data found for %s", selector)
        return False

    ok = write_weather(client, selector, start["time"], hour_data)
    if ok:
        t = hour_data.get("temperature_c", "?")
        h = hour_data.get("humidity_pct", "?")
        w = hour_data.get("wbgt_estimated", "?")
        log.info("  → %s°C, %s%% humidity, WBGT %s", t, h, w)
    return ok


def main_loop():
    log.info("Weather enricher starting (poll every %ds, lookback %dd)", POLL_INTERVAL, LOOKBACK_DAYS)

    while True:
        try:
            client = get_client()
            missing = find_activities_without_weather(client, LOOKBACK_DAYS)

            if missing:
                log.info("Found %d activities without weather data", len(missing))
                for selector in missing:
                    process_one(client, selector)
                    time.sleep(1)
            else:
                log.debug("All activities have weather data")

            client.close()
        except Exception as exc:
            log.error("Error in main loop: %s", exc)

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main_loop()
