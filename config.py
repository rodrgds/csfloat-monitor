import os
import logging
import sys

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

MIN_DISCOUNT_PERCENT = 0.10
BASE_INTERVAL = 10.0
JITTER_RANGE = 2.0
LONG_DELAY_INTERVAL = 30.0
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
NTFY_TOPIC = os.getenv("NTFY_TOPIC", "csfloat-monitor")
NTFY_SERVER = os.getenv("NTFY_SERVER", "https://ntfy.sh")
PROXY_URL = os.getenv("PROXY_URL")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger()


def build_headers() -> dict:
    api_key = os.getenv("CSFLOAT_API_KEY")
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
        "Referer": "https://csfloat.com/",
        "Origin": "https://csfloat.com"
    }
    if api_key:
        headers["Authorization"] = api_key
    return headers
