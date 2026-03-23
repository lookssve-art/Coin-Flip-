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


def extract_product_numbers(title):
    """Extract important product identifiers: card numbers, set codes, years."""
    numbers = set()
    raw_numbers = set()  # Just the bare number for cross-format matching

    # Card numbers like #4, 4/102, 004/165
    for m in re.finditer(r'(\d{1,3})/(\d{2,3})', title):
        numbers.add(m.group(0))
        raw_numbers.add(m.group(1).lstrip('0'))  # "4" from "4/102" or "004/165"
    for m in re.finditer(r'#(\d+)', title):
        numbers.add(m.group(0))
        raw_numbers.add(m.group(1).lstrip('0'))  # "4" from "#4"

    # Set codes like OP01, LOB, SV6
    for m in re.finditer(r'\b[A-Z]{2,4}\d{1,3}\b', title):
        numbers.add(m.group(0).upper())
    # Years
    for m in re.finditer(r'\b(19\d{2}|20\d{2})\b', title):
        numbers.add(m.group(0))
    return numbers, raw_numbers


def extract_keywords(title):
    """Extract important keywords from a product title."""
    title_lower = title.lower()
    stopwords = {
        'the', 'a', 'an', 'and', 'or', 'for', 'in', 'on', 'at', 'to',
        'de', 'der', 'die', 'das', 'und', 'oder', 'fuer', 'fur', 'von', 'mit',
        'new', 'neu', 'sealed', 'mint', 'near', 'eur', 'usd', 'gbp',
        'free', 'shipping', 'versand', 'kostenlos', 'gem',
        'sammelkarte', 'sammelkarten', 'karte', 'karten',
        'trading', 'card', 'cards', 'tcg',
        'top', 'hot', 'rare', 'very', 'look', 'wow', 'great',
        'see', 'photo', 'foto', 'bild', 'bilder', 'siehe',
        'item', 'listing', 'sale', 'buy', 'get',
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


def _core_match(de_title, intl_title):
    """Check if two titles refer to the same product using core identifiers.

    This is more lenient than keyword similarity - it checks if the key
    product identifiers match (grading + product name + numbers).
    """
    de_grading = extract_grading(de_title)
    intl_grading = extract_grading(intl_title)

    # If both have grading, they MUST match
    if de_grading and intl_grading:
        if de_grading != intl_grading:
            return False, 0.0

    # Check product numbers (card numbers, set codes)
    de_numbers, de_raw = extract_product_numbers(de_title)
    intl_numbers, intl_raw = extract_product_numbers(intl_title)
    if de_numbers and intl_numbers:
        # Match by full format OR raw number (#4 matches 4/102)
        full_match = de_numbers & intl_numbers
        raw_match = de_raw & intl_raw
        if not (full_match or raw_match):
            return False, 0.0

    # Keyword overlap
    de_kw = extract_keywords(de_title)
    intl_kw = extract_keywords(intl_title)
    similarity = calculate_similarity(de_kw, intl_kw)

    # Core match: grading matches + at least some keyword overlap
    if de_grading and intl_grading and de_grading == intl_grading:
        # With matching grading, lower similarity threshold is fine
        if similarity >= 0.35:
            return True, similarity

    # Without grading: need higher keyword overlap
    if similarity >= 0.50:
        return True, similarity

    return False, similarity


def find_matches(de_product, international_listings, config, profit_calc):
    """Find international listings that match a German sold product.

    Returns list of (listing, deal_info, similarity) tuples sorted by profit.
    """
    min_profit_pct = config.get("search", {}).get("min_profit_percent", 15)

    matches = []

    for listing in international_listings:
        # Check if products match
        is_match, similarity = _core_match(de_product.title, listing.title)
        if not is_match:
            continue

        # Calculate profit
        deal = profit_calc.calculate_deal(
            sell_price_eur=de_product.avg_price,
            buy_price=listing.price,
            buy_currency=listing.currency,
            shipping_price=listing.shipping_price,
            quantity=listing.quantity_available,
        )

        if deal and deal["profit_percent"] >= min_profit_pct:
            matches.append((listing, deal, similarity))
            logger.info(
                "MATCH: '%s' <-> '%s' (sim=%.2f, profit=€%.2f/%.1f%%)",
                de_product.title[:40], listing.title[:40],
                similarity, deal["profit_eur"], deal["profit_percent"],
            )

    # Sort by profit percentage descending
    matches.sort(key=lambda x: x[1]["profit_percent"], reverse=True)
    return matches
