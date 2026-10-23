from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from unittest.mock import Mock
import pytest
import requests
from sqlalchemy.exc import SQLAlchemyError
from Website import create_app, db
from Website.auth import CheckAge
from Website.models import User, Account, Transaction, MAX_CENTS
from Website.money import deposit_or_withdraw, MoneyError
from Website.currencybeacon import convert_cents, ExchangeError
from .conftest import post, login

def snapshot(app):
    with app.app_context():
        balances = dict(db.session.execute(db.select(User.username, Account.balance_cents)
                        .join(Account, User.id == Account.user_id)).all())
        count = db.session.scalar(db.select(db.func.count()).select_from(Transaction))
        return balances, count

def registration(**changes):
    return {'username': 'dave', 'email': 'dave@example.com', 'address': 'Demo address',
            'country': 'Ireland', 'DOB': '01/01/2000', 'password': 'Password!',
            'password1': 'Password!', **changes}

def test_registration_login_logout(client, app):
    response = post(client, '/register', registration())
    assert b'Account created successfully' in response.data
    assert b'0.00' in response.data
    with app.app_context():
        user = db.session.scalar(db.select(User).filter_by(username='dave'))
        assert user.password != 'Password!'
        assert len(user.accounts) == 1
    assert client.get('/logout').status_code == 405
    post(client, '/logout')
    assert client.get('/').status_code == 302
    assert b'Welcome, dave' in login(client, 'dave').data

@pytest.mark.parametrize('changes,message', [
    ({'username': ''}, b'fill in all fields'),
    ({'password': 'short'}, b'Password needs'),
    ({'password': 'password!'}, b'Password needs'),
    ({'password': 'Password'}, b'Password needs'),
    ({'password1': 'Wrong123!'}, b'do not match'),
    ({'email': 'bad'}, b'valid email'),
    ({'DOB': '31/02/2000'}, b'valid date'),
    ({'DOB': '1/1/2000'}, b'valid date'),
    ({'DOB': '01/01/2999'}, b'at least 18'),
    ({'country': 'Unknown'}, b'not supported'),
    ({'address': 'x' * 101}, b'too long'),
    ({'username': 'alice'}, b'already exists'),
])
def test_registration_validation(client, app, changes, message):
    response = post(client, '/register', registration(**changes))
    assert message in response.data
    with app.app_context():
        assert db.session.scalar(db.select(db.func.count()).select_from(User)) == 3
        assert db.session.scalar(db.select(db.func.count()).select_from(Account)) == 3

def test_missing_registration_fields(client):
    assert b'fill in all fields' in post(client, '/register').data

def test_age_counts_birthdays():
    today = date(2026, 10, 23)
    assert CheckAge('24/10/2008', today) == 17
    assert CheckAge('23/10/2008', today) == 18
    assert CheckAge('22/10/2008', today) == 18

def test_wrong_credentials(client):
    assert b'Incorrect username or password' in post(client, '/login', {'username': 'alice', 'password': 'wrong'}).data
    assert client.get('/').status_code == 302
    assert b'Incorrect username or password' in post(client, '/login').data

@pytest.mark.parametrize('route', ['/add_money', '/withdraw_money', '/transfer_money'])
def test_login_required(client, app, route):
    before = snapshot(app)
    response = post(client, route, {'amount': '1'}, follow=False)
    assert response.status_code == 302 and '/login' in response.location
    assert snapshot(app) == before

@pytest.mark.parametrize('route', ['/login', '/register', '/logout', '/add_money', '/withdraw_money', '/transfer_money'])
def test_csrf_required(client, app, route):
    login(client)
    before = snapshot(app)
    assert client.post(route, data={'amount': '1'}).status_code == 400
    assert snapshot(app) == before

@pytest.mark.parametrize('amount', ['', '-10', '0', '0.00', 'NaN', 'nan', 'Infinity', 'inf',
                                     '1e2', '0.001', '1.234', '1000000000', '+1', 'abc'])
@pytest.mark.parametrize('route', ['/add_money', '/withdraw_money', '/transfer_money'])
def test_invalid_amounts_never_change_balances(client, app, route, amount):
    login(client)
    before = snapshot(app)
    assert post(client, route, {'amount': amount, 'recipient_username': 'bob'}).status_code == 200
    assert snapshot(app) == before

def test_exact_deposit_withdrawal_and_history(client, app):
    login(client)
    for amount in ['0.10', '0.20', '0.10']:
        post(client, '/add_money', {'amount': amount})
    post(client, '/withdraw_money', {'amount': '0.30'})
    balances, count = snapshot(app)
    assert balances['alice'] == 10010 and count == 4
    page = client.get('/')
    assert b'100.10' in page.data and b'Transaction history' in page.data
    before = snapshot(app)
    assert b'Insufficient' in post(client, '/withdraw_money', {'amount': '100.11'}).data
    assert snapshot(app) == before

def test_same_currency_transfer_is_offline(client, app, monkeypatch):
    network = Mock(side_effect=AssertionError('Unexpected network call'))
    monkeypatch.setattr(requests, 'get', network)
    login(client)
    assert b'Recipient received 12.34 EUR' in post(client, '/transfer_money', {'amount': '12.34', 'recipient_username': 'bob'}).data
    balances, count = snapshot(app)
    assert balances == {'alice': 8766, 'bob': 1234, 'carol': 0} and count == 2
    with app.app_context():
        entries = db.session.scalars(db.select(Transaction).order_by(Transaction.id)).all()
        assert entries[0].reference == entries[1].reference
        assert sum(e.amount_cents for e in entries) == 0
    post(client, '/logout')
    page = login(client, 'bob')
    assert b'From alice' in page.data and b'To bob' not in page.data
    network.assert_not_called()

@pytest.mark.parametrize('recipient,amount,message', [('alice', '1', b'yourself'), ('nobody', '1', b'not found'), ('bob', '100.01', b'Insufficient'), ('carol', '1', b'API key')])
def test_transfer_rejections(client, app, recipient, amount, message):
    login(client)
    before = snapshot(app)
    response = post(client, '/transfer_money', {'amount': amount, 'recipient_username': recipient})
    assert message in response.data and snapshot(app) == before

def test_missing_amount(client, app):
    login(client)
    before = snapshot(app)
    assert b'positive amount' in post(client, '/withdraw_money').data
    assert snapshot(app) == before

def test_cross_currency_transfer(client, app, monkeypatch):
    app.config['CURRENCYBEACON_KEY'] = 'not-a-real-key'
    response = Mock()
    response.json.return_value = {'meta': {'code': 200}, 'response': {'value': Decimal('13.555')}}
    get = Mock(return_value=response)
    monkeypatch.setattr(requests, 'get', get)
    login(client)
    page = post(client, '/transfer_money', {'amount': '10', 'recipient_username': 'carol'})
    balances, count = snapshot(app)
    assert balances['alice'] == 9000 and balances['carol'] == 1356 and count == 2
    assert b'13.56 USD' in page.data
    assert get.call_args.kwargs['headers'] == {'Authorization': 'Bearer not-a-real-key'}
    assert get.call_args.kwargs['timeout'] == (3.05, 10)

@pytest.mark.parametrize('payload', [{}, [], {'response': {}}, {'response': None},
    {'response': {'value': 'NaN'}}, {'response': {'value': 'Infinity'}},
    {'response': {'value': -1}}, {'response': {'value': 0}},
    {'response': {'value': '0.001'}}, {'response': {'value': '1e100'}},
    {'meta': {'code': 401}, 'response': {'value': 1}}])
def test_bad_exchange_responses(client, app, monkeypatch, payload):
    app.config['CURRENCYBEACON_KEY'] = 'test'
    response = Mock()
    response.json.return_value = payload
    monkeypatch.setattr(requests, 'get', Mock(return_value=response))
    login(client)
    before = snapshot(app)
    page = post(client, '/transfer_money', {'amount': '1', 'recipient_username': 'carol'})
    assert b'No money was moved' in page.data and snapshot(app) == before

@pytest.mark.parametrize('error', [requests.Timeout(), requests.ConnectionError(), requests.HTTPError()])
def test_provider_failures_do_not_move_money(client, app, monkeypatch, error):
    app.config['CURRENCYBEACON_KEY'] = 'test'
    monkeypatch.setattr(requests, 'get', Mock(side_effect=error))
    login(client)
    before = snapshot(app)
    assert b'No money was moved' in post(client, '/transfer_money', {'amount': '1', 'recipient_username': 'carol'}).data
    assert snapshot(app) == before

def test_invalid_provider_json(monkeypatch):
    response = Mock()
    response.json.side_effect = ValueError('invalid JSON')
    monkeypatch.setattr(requests, 'get', Mock(return_value=response))
    with pytest.raises(ExchangeError):
        convert_cents('EUR', 'USD', 100, 'test')

def test_transfer_rolls_back_if_recipient_limit_exceeded(client, app):
    with app.app_context():
        bob = db.session.scalar(db.select(Account).join(User).where(User.username == 'bob'))
        bob.balance_cents = MAX_CENTS
        db.session.commit()
    login(client)
    before = snapshot(app)
    assert b'limit exceeded' in post(client, '/transfer_money', {'amount': '1', 'recipient_username': 'bob'}).data
    assert snapshot(app) == before

def test_ledger_failure_rolls_back_balance(client, app, monkeypatch):
    from Website import money
    monkeypatch.setattr(money, 'record', Mock(side_effect=SQLAlchemyError('test failure')))
    login(client)
    before = snapshot(app)
    assert b'No money was moved' in post(client, '/add_money', {'amount': '1'}).data
    assert snapshot(app) == before

def test_concurrent_withdrawals_do_not_overspend(app):
    with app.app_context():
        account_id = db.session.scalar(db.select(Account.id).join(User).where(User.username == 'alice'))
    def withdraw(_):
        with app.app_context():
            try:
                deposit_or_withdraw(account_id, 7500, 'EUR', withdraw=True)
                return True
            except MoneyError:
                return False
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(withdraw, range(2)))
    assert sorted(results) == [False, True]
    assert snapshot(app)[0]['alice'] == 2500
    assert snapshot(app)[1] == 1

def test_history_pagination_and_privacy(client, app):
    login(client)
    for _ in range(21):
        post(client, '/add_money', {'amount': '1'})
    page = client.get('/')
    assert b'Page 1 of 2' in page.data and b'Next' in page.data
    assert b'Page 2 of 2' in client.get('/?page=2').data
    post(client, '/logout')
    assert b'No transactions yet' in login(client, 'bob').data

def test_missing_account_is_handled(client, app):
    with app.app_context():
        account = db.session.scalar(db.select(Account).join(User).where(User.username == 'alice'))
        db.session.delete(account)
        db.session.commit()
    # Supply a CSRF token from the login page before the dashboard becomes unavailable.
    page = post(client, '/login', {'username': 'alice', 'password': 'Password!'})
    assert page.status_code == 409 and b'Account not found' in page.data

def test_test_database_is_isolated(app):
    assert 'test.db' in app.config['SQLALCHEMY_DATABASE_URI']
    assert 'APP_USER_ACCOUNT_DATABASE' not in app.config['SQLALCHEMY_DATABASE_URI']
