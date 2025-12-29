import httpx
import time
import random
from python_ntfy import NtfyClient

from config import build_headers, BASE_INTERVAL, JITTER_RANGE, MIN_DISCOUNT_PERCENT, LONG_DELAY_INTERVAL, NTFY_TOPIC, logger
from api import fetch_listings
from database import init_db, is_seen, is_notified, mark_as_seen, mark_as_notified, cleanup_old_items


def monitor_listings():
    init_db()
    logger.info("🚀 CSFloat Monitor Optimized Started")
    
    last_seen_ids = set()
    last_cleanup = time.time()
    
    # Adaptive state
    current_limit = 30
    ntfy_client = NtfyClient(topic=NTFY_TOPIC)
    
    with httpx.Client(http2=True, headers=build_headers(), timeout=15.0) as client:
        while True:
            try:
                # Add a small random jitter to the limit
                fetch_limit = max(10, min(50, current_limit + random.randint(-2, 2)))
                
                params = {
                    "sort_by": "most_recent",
                    "limit": fetch_limit,
                    "type": "buy_now",
                    "min_price": 500,
                }
                listings, remaining = fetch_listings(client, params)
                
                num_repeats = 0
                for listing in listings:
                    if is_seen(listing.id):
                        num_repeats += 1
                    mark_as_seen(listing.id)

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
                        # Check if we already notified for this listing
                        if is_notified(listing.id):
                            continue
                            
                        discount_percent = ((ref_price_usd - listing.price_usd) / ref_price_usd) * 100
                        
                        logger.info("🚨 DEAL FOUND 🚨")
                        logger.info(f"Item: {listing.item.market_hash_name}")
                        logger.info(f"Float: {listing.item.float_value}")
                        logger.info(f"Price: ${listing.price_usd:.2f} (Ref: ${ref_price_usd:.2f})")
                        logger.info(f"Discount: {discount_percent:.2f}%")
                        logger.info(f"Link: https://csfloat.com/item/{listing.id}")
                        logger.info("-" * 30)
                        
                        try:
                            # Sanitize strings for ntfy (which uses latin-1 for headers like title/message)
                            def safe_str(s: str) -> str:
                                return s.encode("latin-1", "replace").decode("latin-1").replace("?", "*")

                            market_name = listing.item.market_hash_name
                            message = (
                                f"Price: ${listing.price_usd:.2f} (Ref: ${ref_price_usd:.2f})\n"
                                f"Discount: {discount_percent:.2f}%\n"
                                f"Float: {listing.item.float_value or 'N/A'}"
                            )
                            
                            clean_title = safe_str(f"DEAL: {market_name}")
                            clean_message = safe_str(message)
                            
                            ntfy_client.send(
                                clean_message,
                                title=clean_title,
                                actions=[
                                    ntfy_client.ViewAction(
                                        label="View Listing",
                                        url=f"https://csfloat.com/item/{listing.id}"
                                    )
                                ]
                            )
                            # Only mark as notified if the notification was successful (or at least attempted)
                            mark_as_notified(listing.id)
                        except Exception as ne:
                            logger.error(f"Failed to send notification: {ne}")
                
                # Dynamic logic based on repeats
                total_fetched = len(listings)
                repeat_ratio = num_repeats / total_fetched if total_fetched > 0 else 1.0
                
                # Base sleep time
                sleep_time = BASE_INTERVAL + random.uniform(0, JITTER_RANGE)
                
                # Adjust state based on repeat ratio
                if repeat_ratio >= 0.85:
                    # Too many repeats: wait significantly longer and fetch fewer items next time
                    multiplier = 3.5 + random.uniform(0, 1.0) # 3.5x to 4.5x
                    sleep_time = (BASE_INTERVAL * multiplier)
                    current_limit = max(15, current_limit - 5)
                    logger.info(f"🐢 Very high repeats ({repeat_ratio:.1%}): slowing down, limit -> {current_limit}")
                elif repeat_ratio >= 0.6:
                    # High repeats: wait longer and reduce limit slightly
                    multiplier = 2.0 + random.uniform(0, 0.5) # 2.0x to 2.5x
                    sleep_time = (BASE_INTERVAL * multiplier)
                    current_limit = max(20, current_limit - 3)
                    logger.info(f"🔄 High repeats ({repeat_ratio:.1%}): waiting, limit -> {current_limit}")
                elif repeat_ratio <= 0.2 and total_fetched > 0:
                    # Low repeats: market is fast! Speed up and fetch more
                    sleep_time = BASE_INTERVAL # No extra multiplier
                    current_limit = min(50, current_limit + 5)
                    logger.info(f"⚡ Fast market ({repeat_ratio:.1%}): speeding up, limit -> {current_limit}")
                
                # Ensure we don't wait TOO long (cap at 90s) or too short
                sleep_time = max(BASE_INTERVAL, min(sleep_time, 90.0))
                
                # Dynamic delay based on rate limit remaining (priority)
                if remaining < 10:
                    logger.warning(f"⚠️ Rate limit low ({remaining}), applying long delay")
                    sleep_time = max(sleep_time, LONG_DELAY_INTERVAL + random.uniform(0, JITTER_RANGE))
                
                # Periodic database cleanup (once every 24 hours)
                if time.time() - last_cleanup > 86400:
                    logger.info("🧹 Cleaning up old database entries")
                    cleanup_old_items(days=7)
                    last_cleanup = time.time()

                time.sleep(sleep_time)
            except Exception as e:
                logger.error(f"Crash detected: {e}")
                time.sleep(10)


if __name__ == "__main__":
    monitor_listings()
