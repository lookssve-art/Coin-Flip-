"""Scraper for international eBay sites (US, JP, UK) to find cheaper listings."""

import logging
import re
from urllib.parse import quote_plus
from dataclasses import dataclass
from typing import Optional

from bs4 import BeautifulSoup

from .helpers import fetch_page, parse_price, normalize_title

logger = logging.getLogger(__name__)


@dataclass
class InternationalListing:
    title: str
    price: float
    currency: str
    url: str
    image_url: str = ""
    shipping_price: Optional[float] = None
    quantity_available: int = 1
    seller: str = ""
    site_id: str = ""
    is_bulk: bool = False


def build_search_url(base_url, query, page=1):
    """Build search URL for an international eBay site (active listings only)."""
    encoded = quote_plus(query)
    url = (
        f"{base_url}/sch/i.html"
        f"?_nkw={encoded}"
        f"&_sop=15"  # Sort by price + shipping lowest first
        f"&LH_BIN=1"  # Buy It Now only
        f"&rt=nc"
        f"&_ipg=100"
    )
    if page > 1:
        url += f"&_pgn={page}"
    return url


def parse_search_page(html, site_id, default_currency):
    """Parse a search results page from an international eBay site."""
    soup = BeautifulSoup(html, "html.parser")
    listings = []

    for item_div in soup.select("li.s-item"):
        title_el = item_div.select_one(".s-item__title")
        if not title_el:
            continue
        title = title_el.get_text(strip=True)
        if title.lower() in ("shop on ebay", "ergebnisse", ""):
            continue

        # Price
        price_el = item_div.select_one(".s-item__price")
        price_text = price_el.get_text(strip=True) if price_el else ""

        # Handle price ranges
        if "bis" in price_text or "to" in price_text:
            parts = re.split(r'\s+bis\s+|\s+to\s+', price_text)
            prices = [parse_price(p) for p in parts]
            prices = [p for p in prices if p is not None]
            price = min(prices) if prices else None  # Use lowest for buy comparison
        else:
            price = parse_price(price_text)

        if price is None:
            continue

        # Determine currency from price text
        currency = default_currency
        if "EUR" in price_text or "€" in price_text:
            currency = "EUR"
        elif "$" in price_text or "USD" in price_text:
            currency = "USD"
        elif "£" in price_text or "GBP" in price_text:
            currency = "GBP"
        elif "¥" in price_text or "JPY" in price_text:
            currency = "JPY"

        # URL
        link_el = item_div.select_one("a.s-item__link")
        url = link_el["href"] if link_el and link_el.has_attr("href") else ""

        # Image
        img_el = item_div.select_one("img.s-item__image-img")
        image_url = ""
        if img_el:
            image_url = img_el.get("src", "") or img_el.get("data-src", "")

        # Shipping
        shipping_el = item_div.select_one(".s-item__shipping, .s-item__freeXDays")
        shipping_text = shipping_el.get_text(strip=True) if shipping_el else ""
        shipping_price = None
        if "kostenlos" in shipping_text.lower() or "free" in shipping_text.lower():
            shipping_price = 0.0
        elif shipping_text:
            shipping_price = parse_price(shipping_text)

        # Quantity / Bulk detection
        qty_el = item_div.select_one(".s-item__quantitySold, .s-item__hotness")
        qty_text = qty_el.get_text(strip=True) if qty_el else ""
        quantity = 1
        is_bulk = False

        # Check title for bulk indicators
        title_lower = title.lower()
        lot_match = re.search(r'(\d+)\s*(?:x|lot|pcs|pieces|stueck|set of)', title_lower)
        if lot_match:
            quantity = int(lot_match.group(1))
            is_bulk = True

        # Seller
        seller_el = item_div.select_one(".s-item__seller-info-text, .s-item__seller-info")
        seller = seller_el.get_text(strip=True) if seller_el else ""

        listings.append(InternationalListing(
            title=title,
            price=price,
            currency=currency,
            url=url,
            image_url=image_url,
            shipping_price=shipping_price,
            quantity_available=quantity,
            seller=seller,
            site_id=site_id,
            is_bulk=is_bulk,
        ))

    return listings


def search_international(query, source_sites, config):
    """Search for a product across all configured international eBay sites."""
    delay_min = config.get("scraping", {}).get("delay_min", 2)
    delay_max = config.get("scraping", {}).get("delay_max", 5)
    proxy = config.get("scraping", {}).get("proxy", "") or None
    max_pages = min(config.get("scraping", {}).get("max_pages", 5), 3)  # Limit for intl

    all_listings = []

    for site in source_sites:
        site_id = site["id"]
        base_url = site["url"]
        currency = site["currency"]

        for page in range(1, max_pages + 1):
            url = build_search_url(base_url, query, page)
            logger.info("Searching %s page %d for '%s'", site_id, page, query)

            resp = fetch_page(url, proxy=proxy, delay_min=delay_min, delay_max=delay_max)
            if not resp:
                break

            listings = parse_search_page(resp.text, site_id, currency)
            if not listings:
                break

            all_listings.extend(listings)

    return all_listings
