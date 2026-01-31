"""AgriGuard: weather-based agronomic alerts. Composes geocode, weather, and advice modules."""

from datetime import datetime

from agriguard.advice import get_advice
from agriguard.geocode import geocode
from agriguard.weather import fetch_forecast_metrics


class AgriGuard:
    """Weather-based agronomic alerts. Use either lat/lon or city name."""

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
            self.lat, self.lon = geocode(city_name)
        else:
            raise ValueError("Provide either (latitude, longitude) or city_name.")

    def get_ai_agri_advice(self):
        """24-hour forecast and agronomic advice from Hugging Face open model. Requires HF_TOKEN."""
        if self.lat is None:
            return ["Location Error"]

        metrics = fetch_forecast_metrics(self.lat, self.lon)
        if metrics is None:
            return ["⚠️ Forecast unavailable."]

        advice, api_error = get_advice(metrics, self._display_name)
        if advice is not None:
            return advice
        if api_error:
            return [f"⚠️ AI advice unavailable: {api_error}"]
        return [
            "⚠️ Set HF_TOKEN (or HUGGING_FACE_HUB_TOKEN) in .env or environment and retry."
        ]

    def print_display(self, advice: list[str]) -> None:
        """Print advice summary (e.g. console / SMS-style)."""
        print("\n" + "=" * 45)
        print(f"🌾 AGRIGUARD: {self._display_name.upper()} — TODAY'S ADVICE")
        print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print("-" * 45)
        for line in advice:
            print(f"• {line}")
        print("=" * 45 + "\n")
