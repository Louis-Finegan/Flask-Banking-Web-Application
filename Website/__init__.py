"""Application factory and shared extensions for the banking demo."""
import os
from pathlib import Path
import secrets
import tempfile
from dotenv import load_dotenv
from flask import Flask, render_template, request
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFError, CSRFProtect
from sqlalchemy import event, inspect
from sqlalchemy.engine import Engine

db = SQLAlchemy()
csrf = CSRFProtect()
DB_NAME = 'APP_USER_ACCOUNT_DATABASE.db'
COUNTRIES = [
    ('United States', 'USD', '$'), ('United Kingdom', 'GBP', '£'),
    ('Canada', 'CAD', '$'), ('Australia', 'AUD', '$'),
    ('Germany', 'EUR', '€'), ('France', 'EUR', '€'),
    ('Japan', 'JPY', '¥'), ('Ireland', 'EUR', '€'), ('China', 'CNY', '¥'),
]

@event.listens_for(Engine, 'connect')
def enable_sqlite_foreign_keys(connection, _):
    """SQLite requires each connection to opt in to foreign-key enforcement."""
    import sqlite3
    if isinstance(connection, sqlite3.Connection):
        connection.execute('PRAGMA foreign_keys=ON')
        connection.execute('PRAGMA busy_timeout=10000')

def persistent_secret(instance_path):
    """Publish a complete local key atomically so worker restarts keep sessions."""
    target = Path(instance_path) / '.secret_key'
    if not target.exists():
        fd, temporary = tempfile.mkstemp(dir=instance_path)
        try:
            with os.fdopen(fd, 'w') as stream:
                stream.write(secrets.token_hex(32))
            try:
                os.link(temporary, target)
            except FileExistsError:
                pass
        finally:
            os.unlink(temporary)
    return target.read_text().strip()

def create_app(test_config=None):
    """Apply configuration before opening any database, including in tests."""
    load_dotenv()
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SQLALCHEMY_DATABASE_URI=os.getenv('DATABASE_URL', f'sqlite:///{DB_NAME}'),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SECRET_KEY=os.getenv('SECRET_KEY'),
        CURRENCYBEACON_KEY=os.getenv('CURRENCYBEACON_KEY'),
        SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax',
        SESSION_COOKIE_SECURE=os.getenv('COOKIE_SECURE', 'false').lower() == 'true',
        REMEMBER_COOKIE_HTTPONLY=True, MAX_CONTENT_LENGTH=16 * 1024,
    )
    if test_config:
        app.config.update(test_config)
    os.makedirs(app.instance_path, exist_ok=True)
    if not app.config['SECRET_KEY']:
        app.config['SECRET_KEY'] = persistent_secret(app.instance_path)
    db.init_app(app)
    csrf.init_app(app)
    from .models import User, COUNTRY_CURRENCY
    from .views import views
    from .auth import auth
    from .migration import migrate_db
    app.register_blueprint(views)
    app.register_blueprint(auth)
    app.cli.add_command(migrate_db)
    login_manager = LoginManager(app)
    login_manager.login_view = 'auth.login'

    @login_manager.user_loader
    def load_user(user_id):
        try:
            return db.session.get(User, int(user_id))
        except (ValueError, TypeError):
            return None

    with app.app_context():
        db.create_all()
        app.config['LEGACY_SCHEMA'] = 'balance_cents' not in {
            c['name'] for c in inspect(db.engine).get_columns('account')}
        for name, code, symbol in COUNTRIES:
            country = db.session.scalar(db.select(COUNTRY_CURRENCY).filter_by(country=name))
            if country is None:
                db.session.add(COUNTRY_CURRENCY(country=name, currency_code=code, currency_symbol=symbol))
            else:
                country.currency_symbol = symbol
        db.session.commit()

    @app.before_request
    def require_current_schema():
        if app.config['LEGACY_SCHEMA'] and request.endpoint != 'static':
            return render_template('error.html', message=(
                'This database needs an upgrade. Stop the server, back up the instance '
                'folder, then run: flask --app main migrate-db')), 503

    @app.errorhandler(CSRFError)
    def csrf_error(_):
        return render_template('error.html', message='This form expired. Reload the page and try again.'), 400

    @app.template_filter('money')
    def money_filter(cents):
        from decimal import Decimal
        return f'{Decimal(cents) / 100:,.2f}'
    return app
