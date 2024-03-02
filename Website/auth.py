from flask import Blueprint, render_template, request, flash, redirect, url_for
from .models import User, Account
from werkzeug.security import generate_password_hash, check_password_hash
from . import db   ##means from __init__.py import db
from flask_login import login_user, login_required, logout_user, current_user
from string import punctuation

def is_capital_in_string(string):
    for char in string:
        if char.isupper():
            return True
    return False

def has_special_character(string):
    special_characters = set(punctuation)  # Get all punctuation characters
    for char in string:
        if char in special_characters:
            return True
    return False



auth = Blueprint('auth', __name__)


@auth.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user:
            if check_password_hash(user.password, password):
                flash('Logged in successfully!', category='success')
                login_user(user, remember=True)
                return redirect(url_for('views.dashboard'))
            else:
                flash('Incorrect password, try again.', category='error')
        else:
            flash('Username does not exist.', category='error')
    return render_template("login.html", user=current_user)

@auth.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))


@auth.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':

        username = request.form.get('username')
        password = request.form.get('password')
        password1 = request.form.get('password1')
        email = request.form.get('email')
        address = request.form.get('address')
        country = request.form.get('country')
        dob = request.form.get('DOB')

        user = User.query.filter_by(username=username).first()

        if user:
            flash('Username already exists!', category='error')
        elif len(password) < 8:
            flash('Password must have atleast 8 characters', category='error')
        elif not is_capital_in_string(password):
            flash('Password must have an upper case character', category='error')
        elif not has_special_character(password):
            flash('Password must contain a special character', category='error')
        elif password != password1:
            flash('Passwords do not match', category='error')
        else:
            new_user = User(
                username=username, 
                password=generate_password_hash(
                    password), 
                email=email, 
                address=address, 
                country=country, 
                dob=dob)
            
            db.session.add(new_user)
            db.session.commit()

            new_account = Account(
                user_id = new_user.id)
            
            db.session.add(new_account)
            db.session.commit()

            login_user(new_user, remember=True)
            flash('Account created successfully!', category='success')

            return redirect(url_for('views.dashboard'))
            
        
            

    return render_template('register.html', user=current_user)


