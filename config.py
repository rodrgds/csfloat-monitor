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
USER_AGENT = "CSFloatMonitor/2.0 (Personal Project; +https://github.com/rodrgds)"
NTFY_TOPIC = os.getenv("NTFY_TOPIC", "csfloat-monitor")
NTFY_SERVER = os.getenv("NTFY_SERVER", "https://ntfy.sh")

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
    }
    if api_key:
        headers["Authorization"] = api_key
    return headers
