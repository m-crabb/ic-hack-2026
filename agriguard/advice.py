"""Generate agronomic advice from forecast metrics using Hugging Face Inference API."""

import os
import re

from huggingface_hub import InferenceClient


def get_advice(
    metrics: dict,
    location_name: str,
    *,
    model_id: str = "meta-llama/Llama-3.1-8B-Instruct",
) -> tuple[list[str] | None, str | None]:
    """
    Call Hugging Face Inference API for 3–5 bullet-point advice.
    Returns (advice_list, None) on success; (None, None) if no token; (None, error_msg) on API failure.
    """
    token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")
    if not token:
        return None, None

    rain_1h = metrics.get("rain_next_hour_mm")
    rain_1h_line = (
        f"- Rain in next hour: {rain_1h:.1f} mm (immediate threat if >0.5 mm)\n        "
        if rain_1h is not None
        else ""
    )
    prompt = f"""You are an expert agronomist advising smallholder farmers. Use ONLY the numbers below. Give 3–5 short, actionable bullet points for TODAY. Be specific and practical (what to do, when, and why). Prioritise by urgency. No preamble.

Location: {location_name}

Forecast (use these exact figures):
- Temperature: min {metrics["min_temp"]:.1f}°C, max {metrics["max_temp"]:.1f}°C, average {metrics["avg_temp"]:.1f}°C
- Total precipitation (next 24h): {metrics["total_rain"]:.1f} mm
        {rain_1h_line}- Soil moisture (3–9 cm, 0–1 scale): {metrics["min_soil"]:.2f} (low if <0.2, critical if <0.15)

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
        lines = [
            re.sub(r"^[\s\-*•\d.)]+", "", line).strip()
            for line in text.strip().splitlines()
            if line.strip()
        ]
        advice = [line for line in lines if line]
        return (
            (advice, None)
            if advice
            else (None, "Model returned no parseable advice")
        )
    except Exception as e:
        return None, str(e)
