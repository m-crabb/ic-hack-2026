"""Resolve city/region name to latitude and longitude via Open-Meteo Geocoding API."""

from agriguard.http_client import retry_session


def geocode(city_name: str, *, verbose: bool = True) -> tuple[float | None, float | None]:
    """
    Resolve city name to (lat, lon). Returns (None, None) on failure.

    Args:
        city_name: City or region name (e.g. "Lodwar", "Porto").
        verbose: If True, print resolved location or error to stdout.
    """
    url = "https://geocoding-api.open-meteo.com/v1/search"
    params = {"name": city_name, "count": 1, "language": "en", "format": "json"}
    try:
        res = retry_session.get(url, params=params, timeout=10).json()
        if res.get("error"):
            raise Exception(res.get("reason", "Geocoding API error"))
        if "results" in res and res["results"]:
            loc = res["results"][0]
            if verbose:
                print(f"📍 Location: {loc['name']}, {loc['country']}")
            return loc["latitude"], loc["longitude"]
        raise Exception(f"No coordinates found for '{city_name}'")
    except Exception as e:
        if verbose:
            print(f"❌ Geocoding: {e}")
        return None, None
