from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from os import path, urandom
from flask_login import LoginManager

db = SQLAlchemy()
DB_NAME = "APP_USER_ACCOUNT_DATABASE.db"


def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = urandom(24)
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{DB_NAME}'
    db.init_app(app)

    from .views import views
    from .auth import auth

    app.register_blueprint(views, url_prefix='/')
    app.register_blueprint(auth, url_prefix='/')

    from .models import User, Account, COUNTRY_CURRENCY
    
    with app.app_context():
        db.create_all()

    login_manager = LoginManager()
    login_manager.login_view = 'auth.login'
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(id):
        return User.query.get(int(id))
    
    with app.app_context():

        countries_data = [
            {"country": "United States", "currency_code": "USD", "currency_symbol": "\u0024"},
            {"country": "United Kingdom", "currency_code": "GBP", "currency_symbol": "\u20A4"},
            {"country": "Canada", "currency_code": "CAD", "currency_symbol": "\u0024"},
            {"country": "Australia", "currency_code": "AUD", "currency_symbol": "\u0024"},
            {"country": "Germany", "currency_code": "EUR", "currency_symbol": "\u20AC"},
            {"country": "France", "currency_code": "EUR", "currency_symbol": "\u20AC"},
            {"country": "Japan", "currency_code": "JPY", "currency_symbol": "\u00A5"},
            {"country": "Ireland", "currency_code": "EUR", "currency_symbol": "\u20AC"},
            {"country": "China", "currency_code": "CNY", "currency_symbol": "\u00A5"},
        ]

        for country_info in countries_data:
            country_instance = COUNTRY_CURRENCY.query.filter_by(country=country_info["country"]).first()

            if country_instance:
                pass
            else:
                country = COUNTRY_CURRENCY(
                    country=country_info["country"], 
                    currency_code=country_info["currency_code"], 
                    currency_symbol=country_info["currency_symbol"])
                
                db.session.add(country)

        db.session.commit()

    return app


def create_database(app):
    if not path.exists('instance/' + DB_NAME):
        db.create_all(app=app)
        print('Created Database!')