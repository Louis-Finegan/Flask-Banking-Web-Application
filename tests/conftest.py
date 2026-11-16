"""Every test gets a temporary database; application data is never touched."""
import re
import pytest
from werkzeug.security import generate_password_hash
from Website import create_app, db
from Website.models import User, Account

@pytest.fixture(scope='session')
def password_hash():
    return generate_password_hash('Password!')

@pytest.fixture
def app(tmp_path, password_hash):
    app = create_app({'TESTING': True, 'SECRET_KEY': 'test-only-key',
        'SQLALCHEMY_DATABASE_URI': f'sqlite:///{tmp_path / "test.db"}',
        'CURRENCYBEACON_KEY': None})
    with app.app_context():
        for name, country, balance in [('alice', 'Ireland', 10000), ('bob', 'France', 0), ('carol', 'United States', 0)]:
            user = User(username=name, password=password_hash, email=f'{name}@example.com',
                        country=country, address='Demo address', dob='01/01/2000')
            db.session.add(user)
            db.session.flush()
            db.session.add(Account(user_id=user.id, balance_cents=balance))
        db.session.commit()
    yield app
    with app.app_context():
        db.session.remove()
        db.engine.dispose()

@pytest.fixture
def client(app):
    return app.test_client()

def post(client, route, data=None, follow=True):
    """Use actual CSRF tokens rather than switching protection off for tests."""
    page = client.get('/login', follow_redirects=True)
    token = re.search(rb'name="csrf_token" value="([^"]+)"', page.data).group(1).decode()
    return client.post(route, data={**(data or {}), 'csrf_token': token}, follow_redirects=follow)

def login(client, name='alice'):
    return post(client, '/login', {'username': name, 'password': 'Password!'})
