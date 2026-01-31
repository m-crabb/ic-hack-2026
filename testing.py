import os
import re
import pandas as pd
import openmeteo_requests
import requests_cache
from datetime import datetime
from huggingface_hub import InferenceClient
from retry_requests import retry

from dotenv import load_dotenv

# Load .env from the directory containing this script (so it works regardless of cwd)
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

# Open-Meteo API client with cache (1h) and retry on error
_cache_session = requests_cache.CachedSession(".cache", expire_after=3600)
_retry_session = retry(_cache_session, retries=5, backoff_factor=0.2)
openmeteo = openmeteo_requests.Client(session=_retry_session)


class AgriGuard:
    """AgriGuard: weather-based agronomic alerts. Use either lat/lon or city name."""

    def __init__(self, *, city_name=None, latitude=None, longitude=None):
        """
        Args:
            city_name: Optional. City/region name for geocoding (e.g. "Lodwar", "Porto").
            latitude: Optional. Latitude in degrees (-90 to 90). Use with longitude.
            longitude: Optional. Longitude in degrees (-180 to 180). Use with latitude.

        Either (latitude and longitude) or city_name must be provided.
        """
        if latitude is not None and longitude is not None:
            self.lat = float(latitude)
            self.lon = float(longitude)
            self._display_name = f"{self.lat:.2f}°N, {self.lon:.2f}°E"
        elif city_name:
            self._display_name = city_name
            self.lat, self.lon = self._geocode(city_name)
        else:
            raise ValueError("Provide either (latitude, longitude) or city_name.")

    def _geocode(self, city_name):
        """Resolve city name to lat/lon via Open-Meteo Geocoding."""
        url = "https://geocoding-api.open-meteo.com/v1/search"
        params = {"name": city_name, "count": 1, "language": "en", "format": "json"}
        try:
            res = _retry_session.get(url, params=params, timeout=10).json()
            if res.get("error"):
                raise Exception(res.get("reason", "Geocoding API error"))
            if "results" in res and res["results"]:
                loc = res["results"][0]
                print(f"📍 Location: {loc['name']}, {loc['country']}")
                return loc["latitude"], loc["longitude"]
            raise Exception(f"No coordinates found for '{city_name}'")
        except Exception as e:
            print(f"❌ Geocoding: {e}")
            return None, None

    def _advice_from_llm(self, metrics, model_id="meta-llama/Llama-3.1-8B-Instruct"):
        """Call Hugging Face Inference API (open model) for agronomic advice.
        Returns (advice_list, None) on success, (None, None) if no token, (None, error_msg) on API failure.
        """
        token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")
        if not token:
            return None, None

        location = getattr(self, "_display_name", f"{self.lat:.2f}, {self.lon:.2f}")
        rain_1h = metrics.get("rain_next_hour_mm")
        rain_1h_line = f"- Rain in next hour: {rain_1h:.1f} mm (immediate threat if >0.5 mm)\n        " if rain_1h is not None else ""
        prompt = f"""You are an expert agronomist advising smallholder farmers. Use ONLY the numbers below. Give 3–5 short, actionable bullet points for TODAY. Be specific and practical (what to do, when, and why). Prioritise by urgency. No preamble.

Location: {location}

Forecast (use these exact figures):
- Temperature: min {metrics['min_temp']:.1f}°C, max {metrics['max_temp']:.1f}°C, average {metrics['avg_temp']:.1f}°C
- Total precipitation (next 24h): {metrics['total_rain']:.1f} mm
        {rain_1h_line}- Soil moisture (3–9 cm, 0–1 scale): {metrics['min_soil']:.2f} (low if <0.2, critical if <0.15)

Rules: Base advice only on the data above. Mention heat stress / shade if max temp is high; irrigation if soil is dry; drainage / delay fieldwork if rain is significant; immediate rain in next hour if >0.5 mm. One line per point, label briefly (e.g. "Heat:", "Irrigation:", "Rain:"). Reply with only the bullet points."""

        try:
            client = InferenceClient()
            completion = client.chat.completions.create(
                model=model_id,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=256,
                temperature=0.3,
            )
            text = completion.choices[0].message.content
            if not text:
                return None, "Model returned empty response"
            # Parse into list: split on newlines, strip bullet prefixes
            lines = [
                re.sub(r"^[\s\-*•\d.)]+", "", line).strip()
                for line in text.strip().splitlines()
                if line.strip()
            ]
            advice = [line for line in lines if line]
            return (advice, None) if advice else (None, "Model returned no parseable advice")
        except Exception as e:
            return None, str(e)

    def get_ai_agri_advice(self):
        """24-hour forecast and agronomic advice from Hugging Face open model. Requires HF_TOKEN."""
        if self.lat is None:
            return ["Location Error"]

        url = "https://api.open-meteo.com/v1/forecast"
        hourly_vars = ["temperature_2m", "soil_moisture_3_to_9cm", "precipitation"]
        params = {
            "latitude": self.lat,
            "longitude": self.lon,
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

            # Next-hour rain (for immediate threat in advice)
            rain_next_hour_mm = None
            try:
                r = _retry_session.get(
                    url,
                    params={
                        "latitude": self.lat,
                        "longitude": self.lon,
                        "minutely_15": "precipitation",
                        "forecast_days": 1,
                        "timezone": "auto",
                    },
                    timeout=10,
                ).json()
                precip = (r.get("minutely_15") or {}).get("precipitation")
                if precip and len(precip) >= 4:
                    rain_next_hour_mm = sum(precip[:4])
            except Exception:
                pass

            metrics = {
                "avg_temp": avg_temp,
                "min_temp": min_temp,
                "max_temp": max_temp,
                "total_rain": total_rain,
                "min_soil": min_soil_for_prompt,
                "rain_next_hour_mm": rain_next_hour_mm,
            }
            advice, api_error = self._advice_from_llm(metrics)
            if advice is not None:
                return advice
            if api_error:
                return [f"⚠️ AI advice unavailable: {api_error}"]
            return ["⚠️ Set HF_TOKEN (or HUGGING_FACE_HUB_TOKEN) in .env or environment and retry."]
        except Exception as e:
            return [f"⚠️ AI Forecast Unavailable: {e}"]

    def print_display(self, advice):
        """Print advice summary (e.g. console / SMS-style)."""
        print("\n" + "=" * 45)
        print(f"🌾 AGRIGUARD: {self._display_name.upper()} — TODAY'S ADVICE")
        print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print("-" * 45)
        for line in advice:
            print(f"• {line}")
        print("=" * 45 + "\n")


# --- TEST ---
if __name__ == "__main__":
    # Option 1: by city name
    app = AgriGuard(city_name="London")

    # Option 2: by latitude / longitude (e.g. Berlin)
    #app = AgriGuard(latitude=52.52, longitude=13.41)

    if app.lat is not None:
        advice = app.get_ai_agri_advice()
        app.print_display(advice)
