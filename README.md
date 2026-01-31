# AgriGuard

Communities in rural areas are disproportionately affected by extreme weather events. AgriGuard provides weather-based agronomic alerts for smallholder farmers: it fetches local forecast data (temperature, precipitation, soil moisture), then uses an open LLM to produce short, actionable advice for the day.

## Features

- **Location by city or coordinates** — Use a city/region name (e.g. "Lodwar", "Porto") or latitude/longitude.
- **Open-Meteo weather** — Hourly temperature, precipitation, and soil moisture (3–9 cm) plus optional 15‑minute precipitation for near-term rain.
- **LLM advice** — [Hugging Face Inference API](https://huggingface.co/inference-api) (e.g. Llama 3.1 8B) generates 3–5 bullet points (heat stress, irrigation, drainage, fieldwork timing) from the forecast.
- **Caching & retries** — Weather requests are cached for 1 hour with retries for reliability.

## Requirements

- Python 3.x
- Dependencies in `requirements.txt` (including `openmeteo-requests`, `requests-cache`, `retry-requests`, `huggingface_hub`, `python-dotenv`, `pandas`).

## Setup

1. **Clone and install**

   ```bash
   pip install -r requirements.txt
   ```

2. **Environment**

   Create a `.env` in the project root (or set variables in your environment):

   - **`HF_TOKEN`** or **`HUGGING_FACE_HUB_TOKEN`** — [Hugging Face access token](https://huggingface.co/settings/tokens) (required for LLM advice). Without it, the app will prompt you to set the token.

   Optional (for SMS in `outbound`):

   - Twilio account SID and auth token, plus a Twilio phone number (see `outbound/outbound.py`).

## Usage

**By city name**

```python
from testing import AgriGuard

app = AgriGuard(city_name="London")
if app.lat is not None:
    advice = app.get_ai_agri_advice()
    app.print_display(advice)
```

**By latitude/longitude**

```python
app = AgriGuard(latitude=52.52, longitude=13.41)
if app.lat is not None:
    advice = app.get_ai_agri_advice()
    app.print_display(advice)
```

**Run the built-in demo**

```bash
python testing.py
```

This uses `city_name="London"` by default; change the `AgriGuard(city_name="...")` line in `testing.py` to try other locations.

## Project layout

| Path | Description |
|------|-------------|
| `testing.py` | AgriGuard class: geocoding, Open-Meteo forecast fetch, LLM advice, and console output. |
| `outbound/outbound.py` | Twilio-based SMS client for sending messages (e.g. bulk alerts). |
| `requirements.txt` | Python dependencies. |
| `.env` | Local env vars (not committed); at least `HF_TOKEN` or `HUGGING_FACE_HUB_TOKEN` for LLM. |

## Data sources

- **Geocoding** — [Open-Meteo Geocoding API](https://open-meteo.com/en/docs/geocoding-api).
- **Weather** — [Open-Meteo Forecast API](https://open-meteo.com/en/docs) (no API key required).
- **Advice** — Hugging Face Inference API (e.g. `meta-llama/Llama-3.1-8B-Instruct`); token required.

## Licence

This project is free to use, modify, and distribute. No warranty; use at your own risk.
