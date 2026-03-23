"""Product matching logic: match eBay.de sold items with international listings."""

import re
import logging
from .profit_calculator import ProfitCalculator

logger = logging.getLogger(__name__)


# Grading systems that require exact match
GRADING_PATTERNS = [
    r'psa\s*\d+',
    r'bgs\s*[\d.]+',
    r'cgc\s*[\d.]+',
    r'wata\s*[\d.]+',
    r'vga\s*[\d.]+',
]


def extract_grading(title):
    """Extract grading info from title (e.g., 'PSA 10', 'WATA 9.8')."""
    title_lower = title.lower()
    for pattern in GRADING_PATTERNS:
        match = re.search(pattern, title_lower)
        if match:
            return match.group(0).strip()
    return None


def extract_keywords(title):
    """Extract important keywords from a product title."""
    title_lower = title.lower()
    # Remove common filler words
    stopwords = {
        'the', 'a', 'an', 'and', 'or', 'for', 'in', 'on', 'at', 'to',
        'de', 'der', 'die', 'das', 'und', 'oder', 'fuer', 'von', 'mit',
        'new', 'neu', 'sealed', 'mint', 'near', 'eur', 'usd', 'gbp',
        'free', 'shipping', 'versand', 'kostenlos',
    }
    words = re.findall(r'\w+', title_lower)
    return set(w for w in words if w not in stopwords and len(w) > 1)


def calculate_similarity(keywords1, keywords2):
    """Calculate Jaccard similarity between two keyword sets."""
    if not keywords1 or not keywords2:
        return 0.0
    intersection = keywords1 & keywords2
    union = keywords1 | keywords2
    return len(intersection) / len(union)


def find_matches(de_product, international_listings, config, profit_calc):
    """Find international listings that match a German sold product.

    Returns list of (listing, deal_info) tuples sorted by profit.
    """
    min_profit_pct = config.get("search", {}).get("min_profit_percent", 20)
    de_grading = extract_grading(de_product.title)
    de_keywords = extract_keywords(de_product.title)

    matches = []

    for listing in international_listings:
        # 1. If product has grading, the grading MUST match exactly
        listing_grading = extract_grading(listing.title)
        if de_grading:
            if not listing_grading or de_grading != listing_grading:
                continue

        # 2. Keyword similarity must be high enough
        listing_keywords = extract_keywords(listing.title)
        similarity = calculate_similarity(de_keywords, listing_keywords)

        # Require at least 60% keyword overlap
        if similarity < 0.6:
            continue

        # 3. Calculate profit
        deal = profit_calc.calculate_deal(
            sell_price_eur=de_product.avg_price,
            buy_price=listing.price,
            buy_currency=listing.currency,
            shipping_price=listing.shipping_price,
            quantity=listing.quantity_available,
        )

        if deal and deal["profit_percent"] >= min_profit_pct:
            matches.append((listing, deal, similarity))

    # Sort by profit percentage descending
    matches.sort(key=lambda x: x[1]["profit_percent"], reverse=True)
    return matches
