"""Shared scraping utilities: User-Agent rotation, delays, request helpers."""

import random
import re
import time
import logging
import requests
from fake_useragent import UserAgent

logger = logging.getLogger(__name__)

_ua = UserAgent()

# German/filler words to remove when building international search queries
DE_STOPWORDS = {
    # German
    'der', 'die', 'das', 'ein', 'eine', 'und', 'oder', 'fuer', 'fur', 'von',
    'mit', 'aus', 'bei', 'nach', 'ueber', 'unter', 'vor', 'auf', 'ab', 'an',
    'ist', 'sind', 'wird', 'hat', 'haben', 'sein', 'war', 'wie', 'auch',
    'nicht', 'aber', 'noch', 'nur', 'schon', 'sehr', 'mehr', 'kein', 'keine',
    'sammelkarte', 'sammelkarten', 'karte', 'karten', 'trading', 'card',
    'cards', 'tcg', 'ccg', 'siehe', 'foto', 'bilder', 'bild', 'top',
    'zustand', 'sammlerstueck', 'sammler', 'raritaet', 'selten',
    'verkaufe', 'verkaufen', 'biete', 'angebot',
    'versand', 'kostenlos', 'gratis', 'free', 'shipping',
    'neu', 'new', 'ovp', 'originalverpackt', 'mint', 'near',
    # English filler
    'the', 'and', 'for', 'with', 'from', 'this', 'that',
    'very', 'rare', 'hot', 'look', 'wow', 'amazing', 'great',
    'get', 'buy', 'sale', 'item', 'listing',
}


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
    cleaned = price_str.strip()
    for symbol in ["EUR", "USD", "$", "£", "¥", "JPY", "GBP", "\xa0"]:
        cleaned = cleaned.replace(symbol, "")
    cleaned = cleaned.strip()

    if "," in cleaned and "." in cleaned:
        if cleaned.rindex(",") > cleaned.rindex("."):
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
    elif "," in cleaned:
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
    t = title.lower().strip()
    t = re.sub(r'[^\w\s]', ' ', t)
    t = re.sub(r'\s+', ' ', t)
    return t.strip()


def extract_search_query(de_title):
    """Extract key search terms from a German eBay title for international search.

    Removes German filler words, keeps product identifiers like grading,
    product names, set names, numbers.

    Example:
        "PSA 10 Charizard Base Set Holo Sammelkarte Pokemon #4"
        → "PSA 10 Charizard Base Set Holo Pokemon #4"
    """
    if not de_title:
        return ""

    # Keep original casing for the search but work on lowercase for filtering
    words = de_title.split()
    kept = []

    for word in words:
        word_lower = word.lower().strip('.,;:!?()[]{}')
        # Always keep: numbers, grading terms, short product codes
        if re.match(r'^[\d./#]+$', word_lower):
            kept.append(word)
        elif word_lower in DE_STOPWORDS:
            continue
        elif len(word_lower) <= 1:
            continue
        else:
            kept.append(word)

    result = " ".join(kept)

    # Limit to reasonable search length (eBay truncates very long queries)
    words_out = result.split()
    if len(words_out) > 12:
        words_out = words_out[:12]

    return " ".join(words_out)


def extract_core_identifiers(title):
    """Extract core product identifiers: grading + main product name.

    Returns a shorter search string with just the essential identifiers.
    Used as fallback when full title search returns no results.

    Example:
        "PSA 10 GEM MINT Charizard Base Set Unlimited Holo 4/102 Pokemon 1999"
        → "PSA 10 Charizard Base Set"
    """
    title_lower = title.lower()

    parts = []

    # Extract grading
    grading_patterns = [
        r'(psa\s*\d+)',
        r'(bgs\s*[\d.]+)',
        r'(cgc\s*[\d.]+)',
        r'(wata\s*[\d.]+)',
        r'(vga\s*[\d.]+)',
    ]
    for pattern in grading_patterns:
        m = re.search(pattern, title_lower)
        if m:
            parts.append(m.group(1).upper().replace('  ', ' '))
            break

    # Extract product name words (non-stopword, non-grading, alphabetic words 3+ chars)
    words = re.findall(r'\b[a-zA-Z]{3,}\b', title)
    product_words = []
    for w in words:
        wl = w.lower()
        if wl in DE_STOPWORDS:
            continue
        if re.match(r'(psa|bgs|cgc|wata|vga|gem|mint)', wl):
            continue
        product_words.append(w)
        if len(product_words) >= 4:
            break

    parts.extend(product_words)
    return " ".join(parts)
