import sqlite3
from decimal import Decimal
import pytest
from Website import create_app, db
from Website.models import Account, Transaction

@pytest.fixture
def legacy(tmp_path):
    path = tmp_path / 'legacy.db'
    with sqlite3.connect(path) as connection:
        connection.executescript('''
        CREATE TABLE user (id INTEGER PRIMARY KEY, username VARCHAR(100) UNIQUE NOT NULL,
            password VARCHAR(100), email VARCHAR(100), address VARCHAR(100), country VARCHAR(100),
            dob VARCHAR(10), is_admin BOOLEAN);
        CREATE TABLE account (id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, balance FLOAT,
            FOREIGN KEY(user_id) REFERENCES user(id));
        INSERT INTO user VALUES (1, 'old-user', 'unused', 'old@example.com', 'Demo', 'Ireland', '01/01/2000', 0);
        INSERT INTO user VALUES (2, 'orphan', 'unused', 'other@example.com', 'Demo', 'Ireland', '01/01/2000', 0);
        INSERT INTO account VALUES (1, 1, 12.345);
        ''')
    app = create_app({'TESTING': True, 'SECRET_KEY': 'test', 'SQLALCHEMY_DATABASE_URI': f'sqlite:///{path}'})
    yield app, path
    with app.app_context():
        db.session.remove()
        db.engine.dispose()

def test_legacy_upgrade_preserves_balance_and_repairs_orphan(legacy):
    app, path = legacy
    assert app.test_client().get('/login').status_code == 503
    result = app.test_cli_runner().invoke(args=['migrate-db'])
    assert result.exit_code == 0, result.output
    with app.app_context():
        assert db.session.get(Account, 1).balance_cents == 1235
        assert db.session.scalar(db.select(Account).filter_by(user_id=2)).balance_cents == 0
        entry = db.session.scalar(db.select(Transaction))
        assert entry.kind == 'opening_balance' and entry.amount_cents == 1235
    with sqlite3.connect(path) as connection:
        assert connection.execute('SELECT balance FROM account WHERE id=1').fetchone()[0] == 12.345
    assert app.test_client().get('/login').status_code == 200
    result = app.test_cli_runner().invoke(args=['migrate-db'])
    assert result.exit_code == 0 and 'already current' in result.output

@pytest.mark.parametrize('value', [-1, float('inf'), None, 1e20])
def test_invalid_legacy_balances_abort_before_schema_changes(legacy, value):
    app, path = legacy
    with sqlite3.connect(path) as connection:
        connection.execute('UPDATE account SET balance=?', (value,))
    result = app.test_cli_runner().invoke(args=['migrate-db'])
    assert result.exit_code != 0
    with sqlite3.connect(path) as connection:
        assert 'balance_cents' not in [row[1] for row in connection.execute('PRAGMA table_info(account)')]

def test_duplicate_legacy_accounts_need_review(legacy):
    app, path = legacy
    with sqlite3.connect(path) as connection:
        connection.execute('INSERT INTO account VALUES (2, 1, 10)')
    result = app.test_cli_runner().invoke(args=['migrate-db'])
    assert result.exit_code != 0 and 'Duplicate' in result.output
