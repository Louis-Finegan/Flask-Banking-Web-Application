from . import db
from flask_login import UserMixin
from sqlalchemy.sql import func


# Define Account model for account balances database
class Account(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    balance = db.Column(db.Float, default=0.0)

# Define User model for user information database
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100))
    email = db.Column(db.String(100))
    address = db.Column(db.String(100))
    country = db.Column(db.String(100))
    dob = db.Column(db.String(10))
    is_admin = db.Column(db.Boolean, default=False)
    accounts = db.relationship('Account', backref='user', lazy=True)