"""Shared scraping utilities: TLS fingerprint spoofing, delays, request helpers."""

import random
import re
import time
import logging

from curl_cffi import requests as cffi_requests

logger = logging.getLogger(__name__)

# Browser impersonation options to rotate through
BROWSER_IMPERSONATIONS = [
    "chrome",
    "chrome110",
    "chrome116",
    "chrome120",
    "chrome124",
    "edge101",
    "safari17_0",
]

# German/filler words to remove when building international search queries
DE_STOPWORDS = {
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
    'the', 'and', 'for', 'with', 'from', 'this', 'that',
    'very', 'rare', 'hot', 'look', 'wow', 'amazing', 'great',
    'get', 'buy', 'sale', 'item', 'listing',
}

# Persistent sessions per eBay domain (keeps cookies like a real browser)
_sessions = {}


def _get_session(domain="www.ebay.de"):
    """Get or create a persistent session for a domain with Chrome impersonation."""
    if domain not in _sessions:
        impersonate = random.choice(BROWSER_IMPERSONATIONS)
        session = cffi_requests.Session(impersonate=impersonate)
        session.headers.update({
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Cache-Control": "max-age=0",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "same_origin",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1",
            "Referer": f"https://{domain}/",
        })
        _sessions[domain] = session
        logger.info("Created new session for %s (impersonate=%s)", domain, impersonate)
    return _sessions[domain]


def reset_session(domain=None):
    """Reset session(s) to get fresh cookies and new browser fingerprint."""
    global _sessions
    if domain:
        _sessions.pop(domain, None)
    else:
        _sessions.clear()
    logger.info("Session(s) reset")


def random_delay(min_sec, max_sec):
    """Sleep for a random duration between min_sec and max_sec."""
    delay = random.uniform(min_sec, max_sec)
    time.sleep(delay)


def fetch_page(url, session=None, proxy=None, delay_min=1.5, delay_max=4):
    """Fetch a page with Chrome TLS fingerprint and realistic delays.

    Uses curl_cffi to impersonate a real Chrome browser, bypassing
    eBay's TLS fingerprinting (Distil Networks) bot detection.
    """
    random_delay(delay_min, delay_max)

    # Extract domain for session management
    from urllib.parse import urlparse
    domain = urlparse(url).netloc

    sess = session or _get_session(domain)
    proxies = {"https": proxy, "http": proxy} if proxy else None

    for attempt in range(3):
        try:
            resp = sess.get(
                url,
                proxies=proxies,
                timeout=30,
                allow_redirects=True,
            )

            # Check if we got a real page (not a bot detection page)
            if resp.status_code == 200:
                content = resp.text
                # Verify it's a real eBay page with items
                if "s-item" in content or "srp-results" in content or "sch/i.html" in url:
                    return resp
                # If it looks like a captcha/bot page, retry with different fingerprint
                if "captcha" in content.lower() or len(content) < 1000:
                    logger.warning("Possible bot detection on attempt %d, rotating fingerprint", attempt + 1)
                    reset_session(domain)
                    sess = _get_session(domain)
                    random_delay(3, 8)  # Longer delay before retry
                    continue
                return resp

            elif resp.status_code == 429:
                logger.warning("Rate limited (429), waiting before retry %d", attempt + 1)
                random_delay(10, 20)
                continue

            elif resp.status_code in (403, 503):
                logger.warning("Blocked (%d) on attempt %d, rotating fingerprint", resp.status_code, attempt + 1)
                reset_session(domain)
                sess = _get_session(domain)
                random_delay(5, 10)
                continue

            else:
                resp.raise_for_status()

        except Exception as e:
            logger.warning("Fetch attempt %d failed for %s: %s", attempt + 1, url[:80], e)
            if attempt < 2:
                reset_session(domain)
                sess = _get_session(domain)
                random_delay(3, 8)

    logger.error("All fetch attempts failed for %s", url[:80])
    return None


def parse_price(price_str):
    """Parse a price string like 'EUR 123,45' or '$1,234.56' into a float."""
    if not price_str:
        return None
    cleaned = price_str.strip()
    for symbol in ["EUR", "USD", "$", "£", "¥", "JPY", "GBP", "\xa0", "€"]:
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
    """
    if not de_title:
        return ""

    words = de_title.split()
    kept = []

    for word in words:
        word_lower = word.lower().strip('.,;:!?()[]{}')
        if re.match(r'^[\d./#]+$', word_lower):
            kept.append(word)
        elif word_lower in DE_STOPWORDS:
            continue
        elif len(word_lower) <= 1:
            continue
        else:
            kept.append(word)

    result = " ".join(kept)
    words_out = result.split()
    if len(words_out) > 12:
        words_out = words_out[:12]

    return " ".join(words_out)


def extract_core_identifiers(title):
    """Extract core product identifiers: grading + main product name.

    Returns a shorter search string with just the essential identifiers.
    Used as fallback when full title search returns no results.
    """
    title_lower = title.lower()

    parts = []

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
