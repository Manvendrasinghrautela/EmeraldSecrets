import logging
from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable, Optional

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

TWOPLACES = Decimal('0.01')


def _to_decimal(value) -> Decimal:
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal('0.00')


def _quantize_money(amount: Decimal) -> Decimal:
    return _to_decimal(amount).quantize(TWOPLACES, rounding=ROUND_HALF_UP)


def calculate_cart_weight(cart_items: Iterable, default_weight: Optional[Decimal] = None) -> Decimal:
    """
    Calculate total shipment weight (in grams) for the given cart items.
    """
    default_weight = default_weight or _to_decimal(getattr(settings, 'DELHIVERY_DEFAULT_ITEM_WEIGHT_G', Decimal('250')))
    total_weight = Decimal('0.00')

    for item in cart_items:
        product = getattr(item, 'product', None)
        product_weight = getattr(product, 'shipping_weight_grams', None) if product else None
        unit_weight = _to_decimal(product_weight) if product_weight else default_weight
        quantity = _to_decimal(getattr(item, 'quantity', 0) or 0)
        total_weight += unit_weight * quantity

    if total_weight <= 0:
        return default_weight
    return total_weight


def _extract_amount(payload: dict) -> Optional[Decimal]:
    """
    Try to extract the shipping amount from various possible Delhivery responses.
    """
    if not isinstance(payload, dict):
        return None

    possible_keys = ['total_amount', 'amount', 'charge']
    for key in possible_keys:
        amount = payload.get(key)
        if amount not in (None, ''):
            return _to_decimal(amount)

    for container_key in ('data', 'charges', 'rate'):
        container = payload.get(container_key)
        if isinstance(container, dict):
            amount = _extract_amount(container)
            if amount:
                return amount
        elif isinstance(container, list):
            for row in container:
                amount = _extract_amount(row)
                if amount:
                    return amount

    return None


def _call_delhivery_rate_api(destination_pincode: str, weight_grams: Decimal, is_cod: bool) -> Optional[Decimal]:
    api_key = getattr(settings, 'DELHIVERY_API_KEY', '')
    if not api_key or not destination_pincode:
        return None

    request_payload = {
        "md": "E",
        "ss": "Delivered",
        "o_pin": str(getattr(settings, 'DELHIVERY_ORIGIN_PINCODE', '110001')),
        "d_pin": str(destination_pincode),
        "cgm": str(int(weight_grams.to_integral_value(rounding=ROUND_HALF_UP))),
        "pt": "D",
        "cod": "1" if is_cod else "0",
    }

    headers = {
        "Authorization": f"Token {api_key}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(
            getattr(settings, 'DELHIVERY_RATE_URL', ''),
            json=request_payload,
            headers=headers,
            timeout=getattr(settings, 'DELHIVERY_REQUEST_TIMEOUT', 10),
        )
        response.raise_for_status()
        payload = response.json()
        return _extract_amount(payload)
    except requests.RequestException as exc:
        logger.warning("Delhivery rate API request failed: %s", exc)
    except ValueError:
        logger.warning("Delhivery rate API returned invalid JSON.")
    return None


def quote_delhivery_shipping(destination_pincode: Optional[str], weight_grams: Decimal, is_cod: bool = False) -> Decimal:
    fallback = _to_decimal(getattr(settings, 'DELHIVERY_FALLBACK_CHARGE', Decimal('65')))
    min_weight = _to_decimal(getattr(settings, 'DELHIVERY_MIN_WEIGHT_G', Decimal('150')))

    if not destination_pincode or weight_grams <= 0:
        return fallback

    chargeable_weight = weight_grams if weight_grams >= min_weight else min_weight
    live_quote = _call_delhivery_rate_api(destination_pincode, chargeable_weight, is_cod)
    if live_quote is None or live_quote <= 0:
        return fallback
    return _quantize_money(live_quote)


def get_shipping_cost_for_cart(cart_items: Iterable, postal_code: Optional[str] = None, is_cod: bool = False) -> Decimal:
    """
    Public helper to compute shipping cost for a set of cart items.
    """
    cart_items = list(cart_items)
    if not cart_items:
        return Decimal('0.00')

    total_weight = calculate_cart_weight(cart_items)
    return quote_delhivery_shipping(postal_code, total_weight, is_cod=is_cod)

