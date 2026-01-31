import pandas as pd
from datetime import datetime

import openmeteo_requests
import requests_cache
from retry_requests import retry

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

    def get_nowcast_alert(self):
        """Immediate rain threat in the next ~60 mins (15-min data where available).
        Uses REST JSON (one request); openmeteo_requests client doesn't expose Minutely15."""
        if self.lat is None:
            return "Location Error"

        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": self.lat,
            "longitude": self.lon,
            "minutely_15": "precipitation",
            "forecast_days": 1,
            "timezone": "auto",
        }
        try:
            data = _retry_session.get(url, params=params, timeout=10).json()
            if data.get("error"):
                return f"⚠️ Nowcast Unavailable: {data.get('reason', 'API error')}"
            minutely = data.get("minutely_15") or {}
            precip = minutely.get("precipitation")
            if not precip:
                return "✅ Nowcast: No immediate rain data for this region."
            upcoming_rain = sum(precip[:4])
            if upcoming_rain > 0.5:
                return f"🚨 NOWCAST ALERT: Heavy rain ({upcoming_rain}mm) expected within the hour. Secure equipment!"
            return "✅ Nowcast: No immediate rain threats detected."
        except Exception as e:
            return f"⚠️ Nowcast Unavailable: {e}"

    def get_ai_agri_advice(self):
        """24-hour forecast and agronomic advice (temp, soil moisture, precipitation)."""
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
            avg_temp = df["temperature_2m"].mean()
            total_rain = df["precipitation"].sum() if "precipitation" in df else 0.0
            min_soil = (
                df["soil_moisture_3_to_9cm"].min()
                if "soil_moisture_3_to_9cm" in df
                else None
            )

            advice = []
            if avg_temp > 32:
                advice.append(
                    "🌡️ Heat Stress: Temperatures are high. Ensure livestock have shade."
                )
            if min_soil is not None and min_soil < 0.15:
                advice.append(
                    "💧 Irrigation: Soil is very dry. Priority watering needed."
                )
            if total_rain > 10:
                advice.append(
                    "🌧️ Flood Risk: Significant rainfall predicted today. Check drainage."
                )
            return (
                advice
                if advice
                else ["🌱 Forecast: Stable conditions. Proceed with planned field work."]
            )
        except Exception as e:
            return [f"⚠️ AI Forecast Unavailable: {e}"]

    def print_display(self, nowcast, advice):
        """Print summary (e.g. console / SMS-style)."""
        print("\n" + "=" * 45)
        print(f"🌾 AGRIGUARD AI: {self._display_name.upper()} UPDATE")
        print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print("-" * 45)
        print(nowcast)
        print("\nDAILY PLANNER:")
        for line in advice:
            print(f"- {line}")
        print("=" * 45 + "\n")


# --- TEST ---
if __name__ == "__main__":
    # Option 1: by city name
    # app = AgriGuard(city_name="Porto")

    # Option 2: by latitude / longitude (e.g. Berlin)
    app = AgriGuard(latitude=52.52, longitude=13.41)

    if app.lat is not None:
        n_alert = app.get_nowcast_alert()
        a_advice = app.get_ai_agri_advice()
        app.print_display(n_alert, a_advice)
