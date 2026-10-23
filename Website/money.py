"""Money validation and atomic balance/ledger updates."""
from decimal import Decimal
import re
from uuid import uuid4
from . import db
from .models import Account, Transaction, MAX_CENTS

class MoneyError(ValueError):
    """A rejected operation whose message can be shown to the user."""

def parse_amount(value):
    """Reject signs, exponents, NaN, infinity, and fractional hundredths."""
    if not isinstance(value, str) or not re.fullmatch(r'[0-9]{1,9}(?:\.[0-9]{1,2})?', value.strip()):
        raise MoneyError('Enter a positive amount with at most two decimal places.')
    cents = int(Decimal(value.strip()) * 100)
    if not 0 < cents <= MAX_CENTS:
        raise MoneyError('Amount must be between 0.01 and 999,999,999.99.')
    return cents

def change_balance(account_id, delta):
    """A conditional SQL update prevents concurrent requests overspending."""
    result = db.session.execute(db.update(Account).where(
        Account.id == account_id,
        Account.balance_cents + delta >= 0,
        Account.balance_cents + delta <= MAX_CENTS,
    ).values(balance_cents=Account.balance_cents + delta),
        execution_options={'synchronize_session': False})
    if result.rowcount != 1:
        raise MoneyError('Insufficient balance, account missing, or balance limit exceeded.')
    return db.session.scalar(db.select(Account.balance_cents).where(Account.id == account_id))

def record(account_id, delta, balance, code, kind, reference, counterparty=None):
    db.session.add(Transaction(account_id=account_id, reference=reference, kind=kind,
        amount_cents=delta, balance_after_cents=balance, currency_code=code, counterparty=counterparty))

def deposit_or_withdraw(account_id, cents, currency, *, withdraw=False):
    """Commit the balance and history together, or roll both back."""
    if not isinstance(cents, int) or not 0 < cents <= MAX_CENTS:
        raise MoneyError('Invalid amount.')
    delta = -cents if withdraw else cents
    try:
        balance = change_balance(account_id, delta)
        record(account_id, delta, balance, currency,
               'withdrawal' if withdraw else 'deposit', uuid4().hex)
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

def transfer(sender, recipient, cents, received_cents, sender_code, recipient_code):
    """Both accounts and both ledger entries belong to one SQL transaction."""
    if sender.id == recipient.id:
        raise MoneyError('You cannot transfer to yourself.')
    if any(not isinstance(n, int) or not 0 < n <= MAX_CENTS for n in (cents, received_cents)):
        raise MoneyError('Invalid transfer amount.')
    reference = uuid4().hex
    try:
        # Consistent lock ordering also prevents opposing-transfer deadlocks on SQL servers.
        changes = [(sender.id, -cents), (recipient.id, received_cents)]
        balances = {account_id: change_balance(account_id, delta)
                    for account_id, delta in sorted(changes)}
        record(sender.id, -cents, balances[sender.id], sender_code,
               'transfer_out', reference, recipient.user.username)
        record(recipient.id, received_cents, balances[recipient.id], recipient_code,
               'transfer_in', reference, sender.user.username)
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
