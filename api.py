import time
from typing import List, Tuple
from pydantic import ValidationError

from models import Listing
from config import logger


def fetch_listings(client, params) -> Tuple[List[Listing], int, int, int]:
    url = "https://csfloat.com/api/v1/listings"
    response = client.get(url, params=params)
    remaining = int(response.headers.get('X-RateLimit-Remaining', 50))
    if response.status_code == 429:
        reset_time = int(response.headers.get('X-RateLimit-Reset', 30))
        logger.warning(f"⛔ Rate Limit Hit! Cooldown {reset_time}s")
        return [], remaining, 429, reset_time
    if response.status_code != 200:
        logger.error(f"API Error {response.status_code}: {response.text}")
        return [], remaining, response.status_code, 0
    json_resp = response.json()
    raw_list = []
    if isinstance(json_resp, dict):
        raw_list = json_resp.get("data") or json_resp.get("listings") or []
        if not raw_list:
            logger.warning(f"Unexpected JSON structure keys: {json_resp.keys()}")
    try:
        listings = [Listing(**item) for item in raw_list]
    except ValidationError as e:
        logger.error(f"Validation Error: {e}")
        return [], remaining, 500, 0
    return listings, remaining, 200, 0
