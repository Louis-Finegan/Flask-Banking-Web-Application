"""Explicit, transactional upgrade from the original SQLite float schema."""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from uuid import uuid4
import click
from flask import current_app
from flask.cli import with_appcontext
from sqlalchemy import inspect
from . import db
from .models import MAX_CENTS

@click.command('migrate-db')
@with_appcontext
def migrate_db():
    """Upgrade legacy balances. Stop the server and back up instance/ first."""
    if db.engine.dialect.name != 'sqlite':
        raise click.ClickException('This migration supports the original SQLite database only.')
    if 'balance_cents' in {c['name'] for c in inspect(db.engine).get_columns('account')}:
        click.echo('Database is already current.')
        return
    # Validate every row before changing the schema. DDL and balance conversion
    # share an explicit SQLite transaction so a failure leaves the old schema intact.
    db.session.remove()
    try:
        with db.engine.connect() as connection:
            connection.exec_driver_sql('BEGIN IMMEDIATE')
            try:
                rows = connection.exec_driver_sql(
                    'SELECT a.id, a.user_id, a.balance, c.currency_code FROM account a '
                    'LEFT JOIN user u ON u.id=a.user_id '
                    'LEFT JOIN country_currency c ON c.country=u.country').all()
                if len({row.user_id for row in rows}) != len(rows):
                    raise ValueError('Duplicate accounts or country records need manual review.')
                converted = []
                for row in rows:
                    amount = Decimal(str(row.balance))
                    if not amount.is_finite() or not 0 <= amount <= Decimal(MAX_CENTS) / 100 or not row.currency_code:
                        raise ValueError(f'Account {row.id} has an invalid balance or currency.')
                    cents = int((amount * 100).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
                    converted.append((row.id, cents, row.currency_code))
                # Orphan users were possible when the old two-commit registration failed.
                missing = connection.exec_driver_sql(
                    'SELECT u.id FROM user u LEFT JOIN account a ON a.user_id=u.id WHERE a.id IS NULL').all()
                connection.exec_driver_sql(
                    f'ALTER TABLE account ADD COLUMN balance_cents BIGINT NOT NULL DEFAULT 0 '
                    f'CHECK (balance_cents BETWEEN 0 AND {MAX_CENTS})')
                connection.exec_driver_sql('CREATE UNIQUE INDEX uq_account_user_id ON account(user_id)')
                for account_id, cents, code in converted:
                    connection.exec_driver_sql('UPDATE account SET balance_cents=? WHERE id=?', (cents, account_id))
                    if cents:
                        connection.exec_driver_sql(
                            'INSERT INTO "transaction" (account_id, reference, kind, amount_cents, '
                            'balance_after_cents, currency_code, created_at) '
                            "VALUES (?, ?, 'opening_balance', ?, ?, ?, CURRENT_TIMESTAMP)",
                            (account_id, uuid4().hex, cents, cents, code))
                for row in missing:
                    connection.exec_driver_sql('INSERT INTO account (user_id, balance_cents) VALUES (?, 0)', (row.id,))
                connection.commit()
            except Exception:
                connection.rollback()
                raise
    except (ValueError, InvalidOperation) as error:
        raise click.ClickException(str(error)) from None
    current_app.config['LEGACY_SCHEMA'] = False
    click.echo('Upgrade complete. Legacy balances retained as opening entries. Restart the server.')
