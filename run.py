#!/usr/bin/env python3
"""eBay Arbitrage Bot - Main entry point.

Usage:
    python run.py          # Run continuously with scheduler
    python run.py --once   # Single scan, then exit
"""

import sys
import time
import logging
import argparse

import yaml
import schedule

from src.scraper.ebay_de_sold import scrape_sold_items, aggregate_sold_items
from src.scraper.ebay_international import search_international
from src.scraper.helpers import normalize_title
from src.analyzer.profit_calculator import ProfitCalculator
from src.analyzer.product_matcher import find_matches
from src.database.db import get_connection, deal_exists, save_deal, update_search_history
from src.notifier.discord_webhook import send_deal_notification, send_summary

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("arbitrage-bot")


def load_config(path="config.yaml"):
    with open(path, "r") as f:
        return yaml.safe_load(f)


def run_scan(config):
    """Execute a full scan cycle."""
    logger.info("=" * 60)
    logger.info("Starting arbitrage scan...")
    logger.info("=" * 60)

    webhook_url = config["discord"]["webhook_url"]
    queries = config["search"]["queries"]
    min_sold = config["search"]["min_sold_count"]
    source_sites = config["markets"]["source_sites"]

    profit_calc = ProfitCalculator(config)
    conn = get_connection()

    total_deals = 0
    all_deals_summary = []

    for query in queries:
        logger.info("-" * 40)
        logger.info("Scanning query: '%s'", query)

        # Step 1: Scrape eBay.de sold items
        sold_items = scrape_sold_items(query, config)
        if not sold_items:
            logger.info("No sold items found for '%s', skipping", query)
            update_search_history(conn, query, 0)
            continue

        # Step 2: Aggregate by product (find items sold multiple times)
        products = aggregate_sold_items(sold_items, min_sold_count=min_sold)
        logger.info("Found %d products sold >= %d times for '%s'", len(products), min_sold, query)

        if not products:
            update_search_history(conn, query, 0)
            continue

        # Step 3: For each popular product, search internationally
        for product in products[:10]:  # Limit to top 10 per query
            logger.info(
                "Searching internationally for: %s (sold %dx, avg €%.2f)",
                product.title[:60], product.sold_count, product.avg_price,
            )

            # Search with the original title on international sites
            intl_listings = search_international(product.title, source_sites, config)

            if not intl_listings:
                # Try with a simplified search (fewer keywords)
                words = product.title.split()[:6]
                simplified = " ".join(words)
                logger.info("No results, trying simplified: '%s'", simplified)
                intl_listings = search_international(simplified, source_sites, config)

            if not intl_listings:
                logger.info("No international listings found")
                continue

            # Step 4: Find matches and calculate profit
            matches = find_matches(product, intl_listings, config, profit_calc)

            for listing, deal_info, similarity in matches[:5]:  # Top 5 matches per product
                norm = normalize_title(product.title)

                # Check if we already notified about this deal
                if deal_exists(conn, norm, listing.site_id, listing.url):
                    logger.info("Deal already notified, skipping")
                    continue

                # Step 5: Send Discord notification
                logger.info(
                    "DEAL FOUND: %s | Profit: €%.2f (%.1f%%)",
                    product.title[:50], deal_info["profit_eur"], deal_info["profit_percent"],
                )

                send_deal_notification(webhook_url, product, listing, deal_info)

                # Save to database
                save_deal(conn, {
                    "product_title": product.title,
                    "normalized_title": norm,
                    "source_site": listing.site_id,
                    "buy_price": listing.price,
                    "buy_currency": listing.currency,
                    "sell_price_eur": product.avg_price,
                    "profit_eur": deal_info["profit_eur"],
                    "profit_percent": deal_info["profit_percent"],
                    "buy_url": listing.url,
                    "sell_url": product.sample_url,
                })

                total_deals += 1
                all_deals_summary.append({
                    "title": product.title,
                    "profit": deal_info["profit_eur"],
                    "profit_pct": deal_info["profit_percent"],
                })

                # Small delay between Discord messages to avoid rate limiting
                time.sleep(1)

        update_search_history(conn, query, len(products))

    # Send summary
    send_summary(webhook_url, len(queries), total_deals, all_deals_summary)

    conn.close()
    logger.info("=" * 60)
    logger.info("Scan complete. Found %d deals.", total_deals)
    logger.info("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="eBay Arbitrage Bot")
    parser.add_argument("--once", action="store_true", help="Run once then exit")
    parser.add_argument("--config", default="config.yaml", help="Config file path")
    args = parser.parse_args()

    config = load_config(args.config)
    logger.info("Config loaded. %d search queries configured.", len(config["search"]["queries"]))

    if args.once:
        run_scan(config)
        return

    # Scheduled mode
    interval = config.get("scheduler", {}).get("interval_hours", 4)
    logger.info("Starting scheduler. Scanning every %d hours.", interval)

    # Run immediately on start
    run_scan(config)

    # Then schedule
    schedule.every(interval).hours.do(run_scan, config)

    while True:
        schedule.run_pending()
        time.sleep(60)


if __name__ == "__main__":
    main()
