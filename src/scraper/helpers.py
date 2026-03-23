"""Shared scraping utilities: User-Agent rotation, delays, request helpers."""

import random
import time
import logging
import requests
from fake_useragent import UserAgent

logger = logging.getLogger(__name__)

_ua = UserAgent()


def get_random_headers():
    """Return headers with a random User-Agent."""
    return {
        "User-Agent": _ua.random,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "de-DE,de;q=0.9,en;q=0.5",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
    }


def random_delay(min_sec, max_sec):
    """Sleep for a random duration between min_sec and max_sec."""
    delay = random.uniform(min_sec, max_sec)
    time.sleep(delay)


def fetch_page(url, session=None, proxy=None, delay_min=2, delay_max=5):
    """Fetch a page with random headers and delay. Returns response or None."""
    random_delay(delay_min, delay_max)
    headers = get_random_headers()
    proxies = {"http": proxy, "https": proxy} if proxy else None

    try:
        requester = session or requests
        resp = requester.get(url, headers=headers, proxies=proxies, timeout=30)
        resp.raise_for_status()
        return resp
    except requests.RequestException as e:
        logger.warning("Failed to fetch %s: %s", url, e)
        return None


def parse_price(price_str):
    """Parse a price string like 'EUR 123,45' or '$1,234.56' into a float."""
    if not price_str:
        return None
    # Remove currency symbols and whitespace
    cleaned = price_str.strip()
    for symbol in ["EUR", "USD", "$", "£", "¥", "JPY", "GBP", "\xa0"]:
        cleaned = cleaned.replace(symbol, "")
    cleaned = cleaned.strip()

    # Handle German format (1.234,56) vs US format (1,234.56)
    if "," in cleaned and "." in cleaned:
        if cleaned.rindex(",") > cleaned.rindex("."):
            # German: 1.234,56
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:
            # US: 1,234.56
            cleaned = cleaned.replace(",", "")
    elif "," in cleaned:
        # Could be German decimal (123,45) or US thousands (1,234)
        parts = cleaned.split(",")
        if len(parts[-1]) == 2:
            cleaned = cleaned.replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")

    try:
        return float(cleaned)
    except ValueError:
        logger.warning("Could not parse price: %s", price_str)
        return None


def normalize_title(title):
    """Normalize a product title for comparison."""
    if not title:
        return ""
    import re
    # Lowercase, remove extra whitespace and special chars
    t = title.lower().strip()
    t = re.sub(r'[^\w\s]', ' ', t)
    t = re.sub(r'\s+', ' ', t)
    return t.strip()
