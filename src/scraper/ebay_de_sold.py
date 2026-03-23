"""Scraper for eBay.de sold items (Verkaufte Artikel)."""

import logging
import re
from difflib import SequenceMatcher
from urllib.parse import quote_plus
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

from bs4 import BeautifulSoup

from .helpers import fetch_page, parse_price, normalize_title

logger = logging.getLogger(__name__)


@dataclass
class SoldItem:
    title: str
    price: float
    currency: str
    url: str
    image_url: str = ""
    sold_date: str = ""
    condition: str = ""


@dataclass
class AggregatedProduct:
    """A product that has been sold multiple times on eBay.de."""
    title: str
    normalized_title: str
    avg_price: float
    min_price: float
    max_price: float
    sold_count: int
    currency: str
    sample_url: str
    sample_image: str
    sold_items: list = field(default_factory=list)


def build_sold_url(query, page=1):
    """Build eBay.de URL for sold items search."""
    encoded = quote_plus(query)
    # LH_Complete=1&LH_Sold=1 = Verkaufte Artikel
    # _sop=13 = sort by newest first
    url = (
        f"https://www.ebay.de/sch/i.html"
        f"?_nkw={encoded}"
        f"&LH_Complete=1&LH_Sold=1"
        f"&_sop=13"
        f"&rt=nc"
        f"&_ipg=240"
    )
    if page > 1:
        url += f"&_pgn={page}"
    return url


def parse_sold_page(html):
    """Parse a single eBay.de sold items search results page."""
    soup = BeautifulSoup(html, "html.parser")
    items = []

    for item_div in soup.select("li.s-item, div.s-item"):
        title_el = item_div.select_one(".s-item__title span, .s-item__title")
        if not title_el:
            continue
        title = title_el.get_text(strip=True)
        if not title or title.lower() in ("shop on ebay", "ergebnisse", "results"):
            continue

        # Price
        price_el = item_div.select_one(".s-item__price")
        price_text = price_el.get_text(strip=True) if price_el else ""

        # Handle price ranges like "EUR 50,00 bis EUR 100,00"
        if "bis" in price_text or "to" in price_text:
            parts = re.split(r'\s+bis\s+|\s+to\s+', price_text)
            prices = [parse_price(p) for p in parts]
            prices = [p for p in prices if p is not None]
            price = sum(prices) / len(prices) if prices else None
        else:
            price = parse_price(price_text)

        if price is None or price <= 0:
            continue

        # Determine currency
        currency = "EUR"
        if "$" in price_text or "USD" in price_text:
            currency = "USD"
        elif "£" in price_text or "GBP" in price_text:
            currency = "GBP"

        # URL
        link_el = item_div.select_one("a.s-item__link")
        url = link_el["href"] if link_el and link_el.has_attr("href") else ""
        # Clean tracking params from URL
        if "?" in url:
            url = url.split("?")[0]

        # Image
        img_el = item_div.select_one("img.s-item__image-img, .s-item__image img")
        image_url = ""
        if img_el:
            image_url = img_el.get("src", "") or img_el.get("data-src", "")

        # Sold date
        date_el = item_div.select_one(
            ".s-item__ended-date, .s-item__endedDate, "
            ".s-item__title--tagblock .POSITIVE, .s-item__detail--primary"
        )
        sold_date = date_el.get_text(strip=True) if date_el else ""

        # Condition
        cond_el = item_div.select_one(".SECONDARY_INFO")
        condition = cond_el.get_text(strip=True) if cond_el else ""

        items.append(SoldItem(
            title=title,
            price=price,
            currency=currency,
            url=url,
            image_url=image_url,
            sold_date=sold_date,
            condition=condition,
        ))

    return items


def scrape_sold_items(query, config):
    """Scrape eBay.de for sold items matching query."""
    max_pages = config.get("scraping", {}).get("max_pages", 10)
    delay_min = config.get("scraping", {}).get("delay_min", 1.5)
    delay_max = config.get("scraping", {}).get("delay_max", 4)
    proxy = config.get("scraping", {}).get("proxy", "") or None

    all_items = []

    for page in range(1, max_pages + 1):
        url = build_sold_url(query, page)
        logger.info("Scraping eBay.de sold page %d/%d for '%s'", page, max_pages, query)

        resp = fetch_page(url, proxy=proxy, delay_min=delay_min, delay_max=delay_max)
        if not resp:
            logger.warning("No response for page %d, stopping", page)
            break

        items = parse_sold_page(resp.text)
        if not items:
            logger.info("No more items on page %d, stopping", page)
            break

        all_items.extend(items)
        logger.info("Found %d items on page %d (total: %d)", len(items), page, len(all_items))

    logger.info("Total sold items found for '%s': %d", query, len(all_items))
    return all_items


def _title_similarity(title1, title2):
    """Calculate similarity between two normalized titles."""
    return SequenceMatcher(None, title1, title2).ratio()


def fuzzy_aggregate_sold_items(items, min_sold_count=2, similarity_threshold=0.60):
    """Group sold items by fuzzy title matching.

    Uses SequenceMatcher to group items with similar titles together,
    rather than requiring exact matches. This handles variations like:
    - "PSA 10 Charizard Base Set Holo #4" vs "Charizard PSA 10 Base Set 1999 Holo"
    - Different seller formatting of the same product
    """
    if not items:
        return []

    # Normalize all titles
    normalized = [(normalize_title(item.title), item) for item in items]

    # Group using fuzzy matching
    groups = []  # List of lists of (norm_title, item)
    used = set()

    for i, (norm_i, item_i) in enumerate(normalized):
        if i in used:
            continue

        group = [(norm_i, item_i)]
        used.add(i)

        for j, (norm_j, item_j) in enumerate(normalized):
            if j in used:
                continue

            # Check similarity against the first item in the group
            sim = _title_similarity(norm_i, norm_j)
            if sim >= similarity_threshold:
                group.append((norm_j, item_j))
                used.add(j)

        groups.append(group)

    # Convert groups to AggregatedProducts
    products = []
    for group in groups:
        if len(group) < min_sold_count:
            continue

        items_in_group = [item for _, item in group]
        prices = [item.price for item in items_in_group]

        # Use the most common title variant (or the first one)
        representative_title = items_in_group[0].title
        representative_norm = group[0][0]

        products.append(AggregatedProduct(
            title=representative_title,
            normalized_title=representative_norm,
            avg_price=sum(prices) / len(prices),
            min_price=min(prices),
            max_price=max(prices),
            sold_count=len(group),
            currency=items_in_group[0].currency,
            sample_url=items_in_group[0].url,
            sample_image=items_in_group[0].image_url,
            sold_items=items_in_group,
        ))

    # Sort by sold_count descending, then by avg_price descending
    products.sort(key=lambda p: (p.sold_count, p.avg_price), reverse=True)

    logger.info(
        "Fuzzy grouped %d items into %d products (>= %d sales each)",
        len(items), len(products), min_sold_count,
    )
    return products


# Keep old function as alias for backwards compatibility
def aggregate_sold_items(items, min_sold_count=2):
    """Group sold items - uses fuzzy matching."""
    return fuzzy_aggregate_sold_items(items, min_sold_count=min_sold_count)
