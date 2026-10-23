"""Users, exact balances, and an application transaction ledger."""
from datetime import datetime, timezone
from flask_login import UserMixin
from . import db

# Shared by input validation and database constraints; this is a demo limit.
MAX_CENTS = 99_999_999_999

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(100))
    address = db.Column(db.String(100))
    country = db.Column(db.String(100))
    dob = db.Column(db.String(10))
    is_admin = db.Column(db.Boolean, default=False)
    accounts = db.relationship('Account', backref='user', lazy=True)

class Account(db.Model):
    """One account per user; balances are integer hundredths, never floats."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), unique=True, nullable=False)
    balance_cents = db.Column(db.BigInteger, default=0, nullable=False)
    __table_args__ = (db.CheckConstraint(
        f'balance_cents BETWEEN 0 AND {MAX_CENTS}', name='valid_balance'),)

class Transaction(db.Model):
    """Transfers create two entries sharing one reference, in one SQL commit."""
    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey('account.id'), nullable=False, index=True)
    reference = db.Column(db.String(32), nullable=False, index=True)
    kind = db.Column(db.String(20), nullable=False)
    amount_cents = db.Column(db.BigInteger, nullable=False)
    balance_after_cents = db.Column(db.BigInteger, nullable=False)
    currency_code = db.Column(db.String(3), nullable=False)
    counterparty = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    __table_args__ = (db.CheckConstraint('amount_cents != 0', name='nonzero_entry'),)

class COUNTRY_CURRENCY(db.Model):
    """Retain the original table name for compatibility with old databases."""
    id = db.Column(db.Integer, primary_key=True)
    country = db.Column(db.String(100), unique=True)
    currency_code = db.Column(db.String(3))
    currency_symbol = db.Column(db.String(10))
