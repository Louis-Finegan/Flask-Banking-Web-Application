"""Registration and session routes, with validation on the server."""
from datetime import date, datetime
import re
from string import punctuation
from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_user, login_required, logout_user, current_user
from sqlalchemy.exc import IntegrityError
from werkzeug.security import generate_password_hash, check_password_hash
from . import db
from .models import User, Account, COUNTRY_CURRENCY

auth = Blueprint('auth', __name__)

def CheckCapital(value):
    return any(char.isupper() for char in value)

def CheckSpecialChar(value):
    return any(char in punctuation for char in value)

def CheckEmail(value):
    return re.fullmatch(r'[^\s@]+@[^\s@.]+(?:\.[^\s@.]+)+', value) is not None

def CheckDOB(value):
    if not re.fullmatch(r'\d{2}/\d{2}/\d{4}', value):
        return False
    try:
        datetime.strptime(value, '%d/%m/%Y')
        return True
    except ValueError:
        return False

def CheckAge(value, today=None):
    """Count completed birthdays rather than just subtracting birth years."""
    today = today or date.today()
    born = datetime.strptime(value, '%d/%m/%Y').date()
    return today.year - born.year - ((today.month, today.day) < (born.month, born.day))

@auth.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('views.dashboard'))
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        user = db.session.scalar(db.select(User).filter_by(username=username))
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('views.dashboard'))
        flash('Incorrect username or password.', 'error')
    return render_template('login.html')

@auth.route('/logout', methods=['POST'])
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))

@auth.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('views.dashboard'))
    countries = db.session.scalars(db.select(COUNTRY_CURRENCY).order_by(COUNTRY_CURRENCY.country)).all()
    if request.method == 'POST':
        data = {key: request.form.get(key, '').strip()
                for key in ('username', 'email', 'address', 'country', 'DOB')}
        password = request.form.get('password', '')
        confirmation = request.form.get('password1', '')
        error = None
        if not all(data.values()) or not password or not confirmation:
            error = 'Please fill in all fields.'
        elif any(len(value) > 100 for value in data.values()) or len(password) > 256:
            error = 'One or more fields are too long.'
        elif not any(c.country == data['country'] for c in countries):
            error = 'App is not supported in your country.'
        elif len(password) < 8 or not CheckCapital(password) or not CheckSpecialChar(password):
            error = 'Password needs at least 8 characters, an uppercase letter and a special character.'
        elif password != confirmation:
            error = 'Passwords do not match.'
        elif not CheckEmail(data['email']):
            error = 'Enter a valid email address.'
        elif not CheckDOB(data['DOB']):
            error = 'Date of birth must be a valid date in DD/MM/YYYY format.'
        elif CheckAge(data['DOB']) < 18:
            error = 'You must be at least 18 to register.'
        if error:
            flash(error, 'error')
        else:
            user = User(username=data['username'], email=data['email'], address=data['address'],
                        country=data['country'], dob=data['DOB'], password=generate_password_hash(password))
            # Flush obtains an id without committing a user without an account.
            try:
                db.session.add(user)
                db.session.flush()
                db.session.add(Account(user_id=user.id, balance_cents=0))
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                flash('Username already exists.', 'error')
            else:
                login_user(user)
                flash('Account created successfully!', 'success')
                return redirect(url_for('views.dashboard'))
    return render_template('register.html', countries=countries)
