"""Discord webhook notifications for arbitrage deals."""

import logging
import requests
import time

logger = logging.getLogger(__name__)


def send_deal_notification(webhook_url, de_product, listing, deal_info):
    """Send a formatted deal notification to Discord."""
    # Build embed
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

    # Add thumbnail if available
    if listing.image_url and listing.image_url.startswith("http"):
        embed["thumbnail"] = {"url": listing.image_url}

    payload = {
        "embeds": [embed],
    }

    try:
        resp = requests.post(webhook_url, json=payload, timeout=10)
        if resp.status_code == 429:
            # Rate limited, wait and retry
            retry_after = resp.json().get("retry_after", 5)
            logger.warning("Discord rate limited, waiting %s seconds", retry_after)
            time.sleep(retry_after)
            resp = requests.post(webhook_url, json=payload, timeout=10)
        resp.raise_for_status()
        logger.info("Discord notification sent for: %s", de_product.title[:80])
        return True
    except Exception as e:
        logger.error("Failed to send Discord notification: %s", e)
        return False


def send_summary(webhook_url, total_queries, total_deals, deals_list):
    """Send a scan summary to Discord."""
    if not deals_list:
        description = (
            f"**Scan abgeschlossen**\n"
            f"Suchbegriffe gescannt: {total_queries}\n"
            f"Neue Deals gefunden: 0\n\n"
            f"Keine profitablen Deals in diesem Durchlauf gefunden."
        )
    else:
        top_deals = deals_list[:5]
        deals_text = "\n".join(
            f"• **{d['title'][:60]}** - Gewinn: €{d['profit']:.2f} ({d['profit_pct']:.1f}%)"
            for d in top_deals
        )
        description = (
            f"**Scan abgeschlossen**\n"
            f"Suchbegriffe gescannt: {total_queries}\n"
            f"Neue Deals gefunden: {total_deals}\n\n"
            f"**Top Deals:**\n{deals_text}"
        )

    embed = {
        "title": "📊 Arbitrage Bot - Scan Zusammenfassung",
        "description": description,
        "color": 0x0099FF,
    }

    try:
        resp = requests.post(webhook_url, json={"embeds": [embed]}, timeout=10)
        resp.raise_for_status()
    except Exception as e:
        logger.error("Failed to send summary: %s", e)
