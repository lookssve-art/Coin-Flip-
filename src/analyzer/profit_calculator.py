"""Profit calculator with currency conversion, shipping, customs (Zoll + EUSt)."""

import logging
import requests

logger = logging.getLogger(__name__)


class ProfitCalculator:
    def __init__(self, config):
        self.config = config
        self.costs = config.get("costs", {})
        self.shipping_estimates = self.costs.get("shipping_estimates", {})
        self.customs = self.costs.get("customs", {})
        self.ebay_fee = self.costs.get("ebay_fee_percent", 0.13)
        self._rates = None

    def get_exchange_rates(self):
        """Fetch current exchange rates from frankfurter.app (free, no API key)."""
        if self._rates:
            return self._rates

        try:
            resp = requests.get(
                "https://api.frankfurter.app/latest?from=EUR",
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
            # We need rates TO EUR, so invert
            rates_from_eur = data.get("rates", {})
            self._rates = {"EUR": 1.0}
            for currency, rate in rates_from_eur.items():
                self._rates[currency] = rate
            logger.info("Exchange rates loaded: %s", self._rates)
            return self._rates
        except Exception as e:
            logger.error("Failed to fetch exchange rates: %s", e)
            # Fallback rates
            self._rates = {
                "EUR": 1.0,
                "USD": 1.08,
                "GBP": 0.86,
                "JPY": 162.0,
            }
            return self._rates

    def convert_to_eur(self, amount, currency):
        """Convert an amount from given currency to EUR."""
        rates = self.get_exchange_rates()
        if currency == "EUR":
            return amount
        rate = rates.get(currency)
        if rate is None:
            logger.warning("No exchange rate for %s, using 1.0", currency)
            return amount
        return amount / rate

    def estimate_shipping_eur(self, currency):
        """Get estimated shipping cost in EUR for a given source currency."""
        shipping_local = self.shipping_estimates.get(currency, 0)
        return self.convert_to_eur(shipping_local, currency)

    def calculate_customs(self, value_eur, shipping_eur):
        """Calculate German customs duties and EUSt (Einfuhrumsatzsteuer).

        Zollwert = Warenwert + Versand
        Zoll = Zollwert * zoll_rate (usually 0% for collectibles)
        EUSt = (Zollwert + Zoll) * 19%
        """
        eust_rate = self.customs.get("einfuhrumsatzsteuer", 0.19)
        zoll_rate = self.customs.get("zoll_rate", 0.0)
        de_minimis = self.customs.get("de_minimis_eur", 150)

        zollwert = value_eur + shipping_eur

        # Zoll only applies if value > de minimis
        if value_eur > de_minimis:
            zoll = zollwert * zoll_rate
        else:
            zoll = 0.0

        # EUSt applies from first euro for commercial imports
        eust = (zollwert + zoll) * eust_rate

        return {
            "zollwert": round(zollwert, 2),
            "zoll": round(zoll, 2),
            "eust": round(eust, 2),
            "total_customs": round(zoll + eust, 2),
        }

    def calculate_deal(self, sell_price_eur, buy_price, buy_currency,
                       shipping_price=None, quantity=1):
        """Calculate full deal profitability.

        Returns dict with all cost breakdowns or None if not profitable.
        """
        # Convert buy price to EUR
        buy_price_eur = self.convert_to_eur(buy_price, buy_currency)

        # Shipping: use provided or estimate
        if shipping_price is not None:
            shipping_eur = self.convert_to_eur(shipping_price, buy_currency)
        else:
            shipping_eur = self.estimate_shipping_eur(buy_currency)

        # Customs
        customs = self.calculate_customs(buy_price_eur, shipping_eur)

        # Total cost per unit
        total_cost = buy_price_eur + shipping_eur + customs["total_customs"]

        # eBay selling fees
        ebay_fees = sell_price_eur * self.ebay_fee

        # Net profit
        profit = sell_price_eur - total_cost - ebay_fees
        profit_percent = (profit / total_cost * 100) if total_cost > 0 else 0

        # Bulk calculation
        if quantity > 1:
            # For bulk: shipping is often shared/reduced
            bulk_buy_total = buy_price_eur * quantity
            bulk_shipping = shipping_eur  # Shipping is usually per shipment
            bulk_customs = self.calculate_customs(bulk_buy_total, bulk_shipping)
            bulk_total_cost = bulk_buy_total + bulk_shipping + bulk_customs["total_customs"]
            bulk_revenue = sell_price_eur * quantity
            bulk_ebay_fees = bulk_revenue * self.ebay_fee
            bulk_profit = bulk_revenue - bulk_total_cost - bulk_ebay_fees
        else:
            bulk_profit = profit

        return {
            "buy_price_original": buy_price,
            "buy_currency": buy_currency,
            "buy_price_eur": round(buy_price_eur, 2),
            "shipping_eur": round(shipping_eur, 2),
            "zoll": customs["zoll"],
            "eust": customs["eust"],
            "total_customs": customs["total_customs"],
            "total_cost_eur": round(total_cost, 2),
            "sell_price_eur": round(sell_price_eur, 2),
            "ebay_fees_eur": round(ebay_fees, 2),
            "profit_eur": round(profit, 2),
            "profit_percent": round(profit_percent, 1),
            "quantity": quantity,
            "bulk_profit_eur": round(bulk_profit, 2),
        }
