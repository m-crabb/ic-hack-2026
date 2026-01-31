"""Fetch Open-Meteo forecast and derive agronomic metrics (temp, rain, soil moisture)."""

import pandas as pd

from agriguard.http_client import openmeteo, retry_session


def fetch_forecast_metrics(lat: float, lon: float) -> dict | None:
    """
    Fetch 24h hourly forecast and optional next-hour rain. Returns a metrics dict
    with avg_temp, min_temp, max_temp, total_rain, min_soil, rain_next_hour_mm.
    Returns None on failure.
    """
    url = "https://api.open-meteo.com/v1/forecast"
    hourly_vars = ["temperature_2m", "soil_moisture_3_to_9cm", "precipitation"]
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": hourly_vars,
        "forecast_days": 1,
        "timezone": "auto",
    }
    try:
        responses = openmeteo.weather_api(url, params=params)
        response = responses[0]
        hourly = response.Hourly()

        n_var = hourly.VariablesLength()
        hourly_data = {
            "date": pd.date_range(
                start=pd.to_datetime(hourly.Time(), unit="s", utc=True),
                end=pd.to_datetime(hourly.TimeEnd(), unit="s", utc=True),
                freq=pd.Timedelta(seconds=hourly.Interval()),
                inclusive="left",
            ),
            "temperature_2m": hourly.Variables(0).ValuesAsNumpy(),
        }
        if n_var > 1:
            hourly_data["soil_moisture_3_to_9cm"] = hourly.Variables(1).ValuesAsNumpy()
        if n_var > 2:
            hourly_data["precipitation"] = hourly.Variables(2).ValuesAsNumpy()

        df = pd.DataFrame(hourly_data)
        avg_temp = float(df["temperature_2m"].mean())
        min_temp = float(df["temperature_2m"].min())
        max_temp = float(df["temperature_2m"].max())
        total_rain = float(df["precipitation"].sum()) if "precipitation" in df else 0.0
        min_soil_raw = (
            float(df["soil_moisture_3_to_9cm"].min())
            if "soil_moisture_3_to_9cm" in df
            else None
        )
        min_soil_for_prompt = min_soil_raw if min_soil_raw is not None else 0.0

        rain_next_hour_mm = _rain_next_hour(lat, lon)

        return {
            "avg_temp": avg_temp,
            "min_temp": min_temp,
            "max_temp": max_temp,
            "total_rain": total_rain,
            "min_soil": min_soil_for_prompt,
            "rain_next_hour_mm": rain_next_hour_mm,
        }
    except Exception:
        return None


def _rain_next_hour(lat: float, lon: float) -> float | None:
    """Sum 15-minute precipitation for next hour (4 steps). Returns None on failure."""
    url = "https://api.open-meteo.com/v1/forecast"
    try:
        r = retry_session.get(
            url,
            params={
                "latitude": lat,
                "longitude": lon,
                "minutely_15": "precipitation",
                "forecast_days": 1,
                "timezone": "auto",
            },
            timeout=10,
        ).json()
        precip = (r.get("minutely_15") or {}).get("precipitation")
        if precip and len(precip) >= 4:
            return sum(precip[:4])
    except Exception:
        pass
    return None
