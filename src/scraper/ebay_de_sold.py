"""Scraper for eBay.de sold items (Verkaufte Artikel)."""

import logging
import re
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
        f"&_ipg=100"
    )
    if page > 1:
        url += f"&_pgn={page}"
    return url


def parse_sold_page(html):
    """Parse a single eBay.de sold items search results page."""
    soup = BeautifulSoup(html, "html.parser")
    items = []

    for item_div in soup.select("li.s-item"):
        # Skip the first "result" which is often a placeholder
        title_el = item_div.select_one(".s-item__title")
        if not title_el:
            continue
        title = title_el.get_text(strip=True)
        if title.lower() in ("shop on ebay", "ergebnisse", ""):
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

        if price is None:
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

        # Image
        img_el = item_div.select_one("img.s-item__image-img")
        image_url = ""
        if img_el:
            image_url = img_el.get("src", "") or img_el.get("data-src", "")

        # Sold date
        date_el = item_div.select_one(".s-item__ended-date, .s-item__endedDate, .POSITIVE")
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
    max_pages = config.get("scraping", {}).get("max_pages", 5)
    delay_min = config.get("scraping", {}).get("delay_min", 2)
    delay_max = config.get("scraping", {}).get("delay_max", 5)
    proxy = config.get("scraping", {}).get("proxy", "") or None

    all_items = []

    for page in range(1, max_pages + 1):
        url = build_sold_url(query, page)
        logger.info("Scraping eBay.de sold page %d for '%s'", page, query)

        resp = fetch_page(url, proxy=proxy, delay_min=delay_min, delay_max=delay_max)
        if not resp:
            logger.warning("No response for page %d", page)
            break

        items = parse_sold_page(resp.text)
        if not items:
            logger.info("No more items on page %d, stopping", page)
            break

        all_items.extend(items)
        logger.info("Found %d items on page %d", len(items), page)

    logger.info("Total sold items found for '%s': %d", query, len(all_items))
    return all_items


def aggregate_sold_items(items, min_sold_count=3):
    """Group sold items by normalized title and return products sold >= min_sold_count times."""
    groups = defaultdict(list)

    for item in items:
        key = normalize_title(item.title)
        groups[key].append(item)

    products = []
    for norm_title, group in groups.items():
        if len(group) < min_sold_count:
            continue

        prices = [i.price for i in group]
        products.append(AggregatedProduct(
            title=group[0].title,
            normalized_title=norm_title,
            avg_price=sum(prices) / len(prices),
            min_price=min(prices),
            max_price=max(prices),
            sold_count=len(group),
            currency=group[0].currency,
            sample_url=group[0].url,
            sample_image=group[0].image_url,
            sold_items=group,
        ))

    # Sort by sold_count descending (most popular first)
    products.sort(key=lambda p: p.sold_count, reverse=True)
    return products
