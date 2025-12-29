import httpx
import time
import random

from config import build_headers, BASE_INTERVAL, JITTER_RANGE, MIN_DISCOUNT_PERCENT, LONG_DELAY_INTERVAL, logger
from api import fetch_listings


def monitor_listings():
    headers = build_headers()
    params = {
        "sort_by": "most_recent",
        "limit": random.randint(45, 50),
        "type": "buy_now",
        "min_price": 500,
    }
    last_seen_ids = set()
    consecutive_empty_fetches = 0
    with httpx.Client(http2=True, timeout=10.0, headers=headers) as client:
        logger.info("🚀 CSFloat Monitor Optimized Started")
        while True:
            try:
                listings, remaining = fetch_listings(client, params)
                
                if not listings:
                    consecutive_empty_fetches += 1
                else:
                    consecutive_empty_fetches = 0

                for listing in listings:
                    if listing.id in last_seen_ids:
                        continue
                    last_seen_ids.add(listing.id)
                    if len(last_seen_ids) > 1000:
                        last_seen_ids = set(list(last_seen_ids)[-500:])
                    if not listing.reference:
                        continue
                    ref_price_cents = listing.reference.get_valid_price()
                    if not ref_price_cents:
                        continue
                    ref_price_usd = ref_price_cents / 100.0
                    target_price = ref_price_usd * (1.0 - MIN_DISCOUNT_PERCENT)
                    if listing.price_usd <= target_price:
                        discount_percent = ((ref_price_usd - listing.price_usd) / ref_price_usd) * 100
                        logger.info("🚨 DEAL FOUND 🚨")
                        logger.info(f"Item: {listing.item.market_hash_name}")
                        logger.info(f"Float: {listing.item.float_value}")
                        logger.info(f"Price: ${listing.price_usd:.2f} (Ref: ${ref_price_usd:.2f})")
                        logger.info(f"Discount: {discount_percent:.2f}%")
                        logger.info(f"Link: https://csfloat.com/item/{listing.id}")
                        logger.info("-" * 30)
                sleep_time = BASE_INTERVAL + random.uniform(0, JITTER_RANGE)
                
                # Dynamic delay based on rate limit remaining
                if remaining < 10:
                    logger.warning(f"⚠️ Rate limit low ({remaining}), applying long delay")
                    sleep_time = LONG_DELAY_INTERVAL + random.uniform(0, JITTER_RANGE)
                elif consecutive_empty_fetches >= 5:
                    # If we haven't seen new items for a while, slow down
                    logger.info("💤 No new items for a while, slowing down")
                    sleep_time = LONG_DELAY_INTERVAL / 2 + random.uniform(0, JITTER_RANGE)

                time.sleep(sleep_time)
            except Exception as e:
                logger.error(f"Crash detected: {e}")
                time.sleep(10)


if __name__ == "__main__":
    monitor_listings()
