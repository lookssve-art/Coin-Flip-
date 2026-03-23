"""Discord webhook notifications for arbitrage deals."""

import logging
import requests
import time

logger = logging.getLogger(__name__)


def _post_webhook(webhook_url, payload, max_retries=2):
    """Post to Discord webhook with retry and rate limit handling."""
    for attempt in range(max_retries + 1):
        try:
            resp = requests.post(webhook_url, json=payload, timeout=10)
            if resp.status_code == 429:
                retry_after = resp.json().get("retry_after", 5)
                logger.warning("Discord rate limited, waiting %s seconds", retry_after)
                time.sleep(retry_after)
                continue
            resp.raise_for_status()
            return True
        except Exception as e:
            logger.error("Discord webhook attempt %d failed: %s", attempt + 1, e)
            if attempt < max_retries:
                time.sleep(2)
    return False


def send_deal_notification(webhook_url, de_product, listing, deal_info):
    """Send a formatted deal notification to Discord."""
    profit_emoji = "🔥" if deal_info["profit_percent"] >= 50 else "✅"
    bulk_text = ""
    if deal_info["quantity"] > 1:
        bulk_text = f"\n📦 **Menge verfuegbar:** {deal_info['quantity']} Stueck\n💰 **Bulk-Gewinn:** €{deal_info['bulk_profit_eur']:.2f}"

    description = (
        f"**📊 eBay.de Verkaufsdaten:**\n"
        f"Durchschn. Verkaufspreis: **€{de_product.avg_price:.2f}**\n"
        f"Anzahl Verkaeufe: **{de_product.sold_count}x**\n"
        f"Preisspanne: €{de_product.min_price:.2f} - €{de_product.max_price:.2f}\n"
        f"\n"
        f"**🛒 Einkauf ({listing.site_id}):**\n"
        f"Preis: {deal_info['buy_currency']} {deal_info['buy_price_original']:.2f} (≈€{deal_info['buy_price_eur']:.2f})\n"
        f"[→ Zum Angebot]({listing.url})\n"
        f"\n"
        f"**💰 Kostenrechnung:**\n"
        f"Warenwert: €{deal_info['buy_price_eur']:.2f}\n"
        f"Versand: €{deal_info['shipping_eur']:.2f}\n"
        f"Zoll: €{deal_info['zoll']:.2f}\n"
        f"EUSt (19%): €{deal_info['eust']:.2f}\n"
        f"eBay Gebuehren (~13%): €{deal_info['ebay_fees_eur']:.2f}\n"
        f"**Gesamtkosten: €{deal_info['total_cost_eur']:.2f}**\n"
        f"\n"
        f"{profit_emoji} **Geschaetzter Gewinn: €{deal_info['profit_eur']:.2f} ({deal_info['profit_percent']:.1f}%)**"
        f"{bulk_text}\n"
        f"\n"
        f"🔗 [eBay.de Verkauft]({de_product.sample_url}) | [Einkauf {listing.site_id}]({listing.url})"
    )

    embed = {
        "title": f"{'🔥' if deal_info['profit_percent'] >= 50 else '💰'} Arbitrage Deal: {de_product.title[:200]}",
        "description": description,
        "color": 0x00FF00 if deal_info["profit_percent"] >= 50 else 0xFFAA00,
    }

    if listing.image_url and listing.image_url.startswith("http"):
        embed["thumbnail"] = {"url": listing.image_url}

    payload = {"embeds": [embed]}
    success = _post_webhook(webhook_url, payload)
    if success:
        logger.info("Discord deal notification sent: %s", de_product.title[:80])
    return success


def send_progress(webhook_url, query, items_found, products_found, query_num, total_queries):
    """Send a brief progress update during scanning."""
    description = (
        f"**Query {query_num}/{total_queries}:** `{query}`\n"
        f"Verkaufte Artikel gefunden: **{items_found}**\n"
        f"Produkte mit mehrfachen Verkaeufen: **{products_found}**"
    )

    if products_found > 0:
        description += "\n🔍 Suche jetzt international nach guenstigeren Preisen..."
    else:
        description += "\n⏭️ Keine Produkte mit genug Verkaeufen, weiter zum naechsten..."

    embed = {
        "title": f"🔍 Scan Fortschritt ({query_num}/{total_queries})",
        "description": description,
        "color": 0x3498DB,
    }

    _post_webhook(webhook_url, {"embeds": [embed]})


def send_summary(webhook_url, total_queries, total_deals, deals_list,
                 total_items_scanned=0, total_products_found=0):
    """Send a scan summary to Discord."""
    if not deals_list:
        description = (
            f"**Scan abgeschlossen**\n"
            f"Suchbegriffe gescannt: {total_queries}\n"
            f"Verkaufte Artikel analysiert: {total_items_scanned}\n"
            f"Produkte mit mehrfachen Verkaeufen: {total_products_found}\n"
            f"Neue Deals gefunden: 0\n\n"
        )
        if total_items_scanned == 0:
            description += "⚠️ Keine Artikel konnten gescraped werden. Pruefe ob eBay erreichbar ist oder ein Proxy benoetigt wird."
        elif total_products_found == 0:
            description += "ℹ️ Keine Produkte mit genug wiederholten Verkaeufen gefunden. Versuche min_sold_count zu senken."
        else:
            description += "ℹ️ Produkte gefunden, aber keine mit ausreichend Gewinnmarge international."
    else:
        top_deals = deals_list[:5]
        deals_text = "\n".join(
            f"• **{d['title'][:60]}** - Gewinn: €{d['profit']:.2f} ({d['profit_pct']:.1f}%)"
            for d in top_deals
        )
        description = (
            f"**Scan abgeschlossen**\n"
            f"Suchbegriffe gescannt: {total_queries}\n"
            f"Verkaufte Artikel analysiert: {total_items_scanned}\n"
            f"Produkte mit mehrfachen Verkaeufen: {total_products_found}\n"
            f"Neue Deals gefunden: **{total_deals}**\n\n"
            f"**Top Deals:**\n{deals_text}"
        )

    embed = {
        "title": "📊 Arbitrage Bot - Scan Zusammenfassung",
        "description": description,
        "color": 0x00FF00 if deals_list else 0xFF6600,
    }

    _post_webhook(webhook_url, {"embeds": [embed]})
