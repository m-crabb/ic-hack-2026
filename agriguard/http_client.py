"""Shared HTTP client: cached session and Open-Meteo client with retries."""

import openmeteo_requests
import requests_cache
from retry_requests import retry

# 1-hour cache, 5 retries with backoff
_cache_session = requests_cache.CachedSession(".cache", expire_after=3600)
retry_session = retry(_cache_session, retries=5, backoff_factor=0.2)
openmeteo = openmeteo_requests.Client(session=retry_session)
