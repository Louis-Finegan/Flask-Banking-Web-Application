from flask import Blueprint, render_template, request, flash, jsonify
from flask_login import login_required, current_user
from .models import Account, User
from . import db
from flask import redirect, url_for, send_from_directory
import os

views = Blueprint('views', __name__)

@views.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(views.root_path, 'static'), 'favicon.ico', mimetype='image/vnd.microsoft.icon')

@views.route('/', methods=['GET', 'POST'])
@login_required
def dashboard():
    user = current_user
    accounts = Account.query.filter_by(user_id=user.id).first()
    balance = accounts.balance if accounts else None

    return render_template('dashboard.html', user=current_user, accounts=accounts, balance=balance)


@views.route('/add_money', methods=['POST'])
def add_money():
    # Check if the user is logged in
    if not current_user.is_authenticated:
        return redirect(url_for('login'))
    
    # Get the amount to add from the form data
    amount = float(request.form['amount'])

    # Perform the addition to the user's account balance
    user_id = current_user.id
    account = Account.query.filter_by(user_id=user_id).first()
    if account:
        account.balance += amount
        db.session.commit()
        flash(f'Added {amount} to your account.', 'success')
    else:
        flash('Account not found.', 'error')

    return redirect(url_for('views.dashboard'))

@views.route('/withdraw_money', methods=['POST'])
def withdraw_money():
    # Check if the user is logged in
    if not current_user.is_authenticated:
        return redirect(url_for('login'))
    
    # Get the amount to withdraw from the form data
    amount = float(request.form['amount'])

    # Perform the withdrawal from the user's account balance
    user_id = current_user.id
    account = Account.query.filter_by(user_id=user_id).first()
    if account:
        if account.balance >= amount:
            account.balance -= amount
            db.session.commit()
            flash(f'Withdrawn {amount} from your account.', 'success')
        else:
            flash('Insufficient balance.', 'error')
    else:
        flash('Account not found.', 'error')

    return redirect(url_for('views.dashboard'))

@views.route('/transfer_money', methods=['POST'])
def transfer_money():
    # Check if the user is logged in
    if not current_user.is_authenticated:
        return redirect(url_for('login'))
    
    # Get transfer details from the form data
    recipient_username = request.form['recipient_username']
    amount = float(request.form['amount'])

    # Find sender's and recipient's accounts
    sender_id = current_user.id
    sender_account = Account.query.filter_by(user_id=sender_id).first()
    recipient = User.query.filter_by(username=recipient_username).first()
    if recipient:
        recipient_account = Account.query.filter_by(user_id=recipient.id).first()
    else:
        flash('Recipient not found.', 'error')
        return redirect(url_for('views.dashboard'))

    # Perform the transfer
    if sender_account and recipient_account:
        if sender_account.balance >= amount:
            sender_account.balance -= amount
            recipient_account.balance += amount
            db.session.commit()
            flash(f'Transferred {amount} to {recipient_username}.', 'success')
        else:
            flash('Insufficient balance.', 'error')
    else:
        flash('Account not found.', 'error')

    return redirect(url_for('views.dashboard'))