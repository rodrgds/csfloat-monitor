import httpx
import time
import random
from python_ntfy import NtfyClient

from config import (
    build_headers, 
    BASE_INTERVAL, 
    JITTER_RANGE, 
    MIN_DISCOUNT_PERCENT, 
    LONG_DELAY_INTERVAL, 
    NTFY_TOPIC, 
    NTFY_SERVER,
    PROXY_URL,
    logger
)
from api import fetch_listings
from database import init_db, is_seen, is_notified, mark_as_seen, mark_as_notified, cleanup_old_items


def monitor_listings():
    init_db()
    logger.info("🚀 CSFloat Monitor Optimized Started")
    
    last_seen_ids = set()
    last_cleanup = time.time()
    
    # Adaptive state
    current_limit = 30
    sleep_time = BASE_INTERVAL
    consecutive_empty_overlaps = 0
    ntfy_client = NtfyClient(topic=NTFY_TOPIC, server=NTFY_SERVER)
    
    with httpx.Client(
        http2=True, 
        headers=build_headers(), 
        timeout=15.0,
        proxy=PROXY_URL
    ) as client:
        while True:
            try:
                # --- OPTIMIZATION 1: Jitter is good, but keep limit robust ---
                # We prioritize a safe limit (min 25) to catch bursts even if we sleep longer.
                effective_limit = max(25, min(50, current_limit + random.randint(-1, 3)))
                
                params = {
                    "sort_by": "most_recent",
                    "limit": effective_limit,
                    "type": "buy_now",
                    "min_price": 500,
                }
                
                listings, remaining = fetch_listings(client, params)
                
                # Count NEW items vs REPEATS
                new_items_count = 0
                overlaps_found = 0
                
                for listing in listings:
                    # Check our local memory first (faster than DB)
                    if listing.id in last_seen_ids:
                        overlaps_found += 1
                        continue 

                    # Double check DB for persistence (in case of restart)
                    if is_seen(listing.id):
                        overlaps_found += 1
                        last_seen_ids.add(listing.id) # Sync local cache
                        continue 

                    # --- NEW ITEM FOUND ---
                    new_items_count += 1
                    mark_as_seen(listing.id)
                    last_seen_ids.add(listing.id)
                    
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
                
                # Maintain local cache size
                if len(last_seen_ids) > 2000:
                    # Keep the newest 1000 IDs (approximate by list conversion)
                    last_seen_ids = set(list(last_seen_ids)[-1000:])

                # --- OPTIMIZATION 2: The "Elastic Buffer" Logic ---
                # Ideally, we want to see roughly 3-5 repeats.
                target_overlap = 4
                
                if overlaps_found == 0 and len(listings) > 0:
                    # DANGER: We missed the connection to previous fetch!
                    consecutive_empty_overlaps += 1
                    logger.warning(f"⚠️ CHAIN BROKEN ({consecutive_empty_overlaps}x): 0 repeats found. Potential miss!")
                    
                    # REACTION: Panic mode. Max limit, Min sleep.
                    current_limit = 50
                    sleep_time = BASE_INTERVAL * 0.5
                else:
                    consecutive_empty_overlaps = 0
                    
                    if new_items_count > 10:
                        # 🔥 BURST: Market is flooding
                        logger.info(f"� High Velocity ({new_items_count} new): Speeding up!")
                        current_limit = min(50, current_limit + 5)
                        sleep_time = BASE_INTERVAL
                        
                    elif overlaps_found < target_overlap:
                        # ⚡ FAST: We are barely keeping up (overlap is too thin)
                        logger.info(f"⚡ Fast Market (Overlap {overlaps_found}/{target_overlap}): Widening net.")
                        current_limit = min(45, current_limit + 2)
                        sleep_time = max(BASE_INTERVAL, sleep_time * 0.9)
                        
                    elif overlaps_found > (target_overlap * 3):
                        # 🐢 SLOW: We are fetching way too many duplicates (e.g. 20 repeats)
                        logger.info(f"🐢 Slow Market (Overlap {overlaps_found}): Sleeping longer.")
                        current_limit = max(25, current_limit - 1) 
                        sleep_time = min(45.0, sleep_time * 1.2) 
                        
                    else:
                        logger.info(f"⚖️ Optimized State ({new_items_count} new, {overlaps_found} safe): Maintaining.")
                        if current_limit > 30: current_limit -= 1
                        if current_limit < 30: current_limit += 1

                # --- OPTIMIZATION 3: Rate Limit Protection ---
                if remaining < 5:
                    logger.critical("🛑 Rate limit critical! Engaging emergency brakes.")
                    sleep_time = 60.0
                elif remaining < 20:
                    logger.warning(f"⚠️ Rate limit low ({remaining}). Adding delay.")
                    sleep_time = max(sleep_time, 15.0)

                final_sleep = sleep_time + random.uniform(0.5, 2.0)
                
                # Periodic database cleanup (once every 24 hours)
                if time.time() - last_cleanup > 86400:
                    logger.info("🧹 Cleaning up old database entries")
                    cleanup_old_items(days=7)
                    last_cleanup = time.time()

                time.sleep(final_sleep)
            except Exception as e:
                logger.error(f"Crash detected: {e}")
                time.sleep(10)


if __name__ == "__main__":
    monitor_listings()
