"""Server-side CurrencyBeacon adapter; never changes account balances."""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import requests
from .models import MAX_CENTS

class ExchangeError(ValueError):
    pass

def convert_cents(source, target, cents, api_key):
    """Return integer hundredths; same-currency transfers work offline."""
    if source == target:
        return cents
    if not api_key:
        raise ExchangeError('Cross-currency transfers need a CurrencyBeacon API key.')
    try:
        response = requests.get('https://api.currencybeacon.com/v1/convert',
            headers={'Authorization': f'Bearer {api_key}'},
            params={'from': source, 'to': target, 'amount': str(Decimal(cents) / 100)},
            timeout=(3.05, 10))
        response.raise_for_status()
        payload = response.json(parse_float=Decimal)
        if payload.get('meta', {}).get('code', 200) != 200:
            raise ValueError('Provider rejected conversion')
        converted = Decimal(str(payload['response']['value']))
        if not converted.is_finite() or not 0 < converted <= Decimal(MAX_CENTS) / 100:
            raise ValueError('Invalid converted amount')
        result = int((converted * 100).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
        if not 0 < result <= MAX_CENTS:
            raise ValueError('Converted amount below minimum')
        return result
    except (requests.RequestException, ValueError, KeyError, TypeError, AttributeError, InvalidOperation):
        # Avoid disclosing request URLs, credentials, or provider internals in flashes.
        raise ExchangeError('Currency conversion is unavailable. No money was moved.') from None
