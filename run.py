"""Demo: run AgriGuard for a location (city or lat/lon). Loads .env from project root."""

import os

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

from agriguard import AgriGuard

if __name__ == "__main__":
    # Option 1: by city name
    app = AgriGuard(city_name="London")

    # Option 2: by latitude / longitude (e.g. Berlin)
    # app = AgriGuard(latitude=52.52, longitude=13.41)

    if app.lat is not None:
        advice = app.get_ai_agri_advice()
        app.print_display(advice)
