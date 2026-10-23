"""Dashboard and demo money operations. All writes require login and CSRF."""
from decimal import Decimal
from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app
from flask_login import login_required, current_user
from sqlalchemy.exc import SQLAlchemyError
from . import db
from .models import Account, User, COUNTRY_CURRENCY, Transaction
from .money import MoneyError, parse_amount, deposit_or_withdraw, transfer
from .currencybeacon import convert_cents, ExchangeError

views = Blueprint('views', __name__)

def account_for(user):
    account = db.session.scalar(db.select(Account).filter_by(user_id=user.id))
    if account is None:
        raise MoneyError('Account not found.')
    return account

def currency_for(user):
    country = db.session.scalar(db.select(COUNTRY_CURRENCY).filter_by(country=user.country))
    if country is None:
        raise MoneyError('Account currency is not supported.')
    return country

@views.route('/')
@login_required
def dashboard():
    try:
        account, currency = account_for(current_user), currency_for(current_user)
    except MoneyError as error:
        return render_template('error.html', message=str(error)), 409
    # Never accept an account id from the browser to select history.
    history = db.paginate(db.select(Transaction).where(Transaction.account_id == account.id)
                          .order_by(Transaction.id.desc()), per_page=20, error_out=False)
    return render_template('dashboard.html', account=account, currency=currency, history=history)

def operation_error(error):
    db.session.rollback()
    if isinstance(error, SQLAlchemyError):
        current_app.logger.error('Database operation failed (%s)', type(error).__name__)
        flash('The operation could not be completed. No money was moved. Please try again.', 'error')
    else:
        flash(str(error), 'error')

@views.route('/add_money', methods=['POST'])
@login_required
def add_money():
    try:
        cents = parse_amount(request.form.get('amount'))
        account, currency = account_for(current_user), currency_for(current_user)
        deposit_or_withdraw(account.id, cents, currency.currency_code)
        flash('Demo money added.', 'success')
    except (MoneyError, SQLAlchemyError) as error:
        operation_error(error)
    return redirect(url_for('views.dashboard'))

@views.route('/withdraw_money', methods=['POST'])
@login_required
def withdraw_money():
    try:
        cents = parse_amount(request.form.get('amount'))
        account, currency = account_for(current_user), currency_for(current_user)
        deposit_or_withdraw(account.id, cents, currency.currency_code, withdraw=True)
        flash('Demo money withdrawn.', 'success')
    except (MoneyError, SQLAlchemyError) as error:
        operation_error(error)
    return redirect(url_for('views.dashboard'))

@views.route('/transfer_money', methods=['POST'])
@login_required
def transfer_money():
    try:
        cents = parse_amount(request.form.get('amount'))
        name = request.form.get('recipient_username', '').strip()
        recipient = db.session.scalar(db.select(User).filter_by(username=name))
        if recipient is None:
            raise MoneyError('Recipient not found.')
        if recipient.id == current_user.id:
            raise MoneyError('You cannot transfer to yourself.')
        sender_account, recipient_account = account_for(current_user), account_for(recipient)
        sender_currency, recipient_currency = currency_for(current_user), currency_for(recipient)
        if sender_account.balance_cents < cents:
            raise MoneyError('Insufficient balance.')
        # Obtain the quote before any writes; SQL rechecks funds after the quote.
        received = convert_cents(sender_currency.currency_code, recipient_currency.currency_code,
                                 cents, current_app.config['CURRENCYBEACON_KEY'])
        transfer(sender_account, recipient_account, cents, received,
                 sender_currency.currency_code, recipient_currency.currency_code)
        flash(f'Transferred to {recipient.username}. Recipient received '
              f'{Decimal(received) / 100:.2f} {recipient_currency.currency_code}.', 'success')
    except (MoneyError, ExchangeError, SQLAlchemyError) as error:
        operation_error(error)
    return redirect(url_for('views.dashboard'))
