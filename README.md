# Flask Banking Web Application

A banking simulation built with Python, Flask and SQLite. It supports registration, account balances, deposits, withdrawals and transfers between users, including currency conversion through CurrencyBeacon.

All money is simulated. Use fictional registration details; this is an educational project, not a service for handling real funds.

## Features

- Register and log in, with hashed passwords and server-side validation.
- One account per user, with a currency determined by their country.
- Add and withdraw demo money, with positive-amount and available-balance checks.
- Transfer between accounts in one database transaction. Same-currency transfers work offline.
- Convert cross-currency transfers using CurrencyBeacon, with timeouts and error handling.
- View a private, paginated transaction history, including transferred amounts and balances after each operation.
- Protect forms with CSRF tokens and require a POST request to log out.
- Run locally or in a Docker container with persistent data.

Money is stored as integer hundredths, avoiding floating-point balance arithmetic. The demo uses two decimal places for every supported currency, including JPY; it does not implement each currency's real-world minor-unit rules. Converted amounts round to the nearest hundredth using `ROUND_HALF_UP`. Individual amounts and account balances are limited to 999,999,999.99.

## Run locally

Use Python 3.11 or newer. From the repository root:

```bash
python -m pip install -r requirements.txt
python main.py
```

Open <http://127.0.0.1:5000>. The application creates its database and local session key in `instance/` on first startup. Keep that folder to preserve accounts and sessions across restarts. Debug mode is off by default. For local development with automatic reload:

```bash
python -m flask --app main run --debug
```

Register an account, add demo money and register a second account in another browser session to try a transfer. You can also log out and switch between the two accounts. Usernames are case-sensitive.

## Currency conversion and configuration

Same-currency transfers do not need configuration or an internet connection. For transfers between different currencies, copy `.env.example` to `.env` and set:

```dotenv
CURRENCYBEACON_KEY=your_api_key
```

The key is read on the server and is never sent to the browser. A missing key, provider failure, invalid quote or timeout leaves both balances unchanged. The application reads `response.value` from the [CurrencyBeacon conversion endpoint](https://api.currencybeacon.com/api-documentation). Your API plan must allow conversion requests.

Other optional environment variables:

| Variable | Purpose |
| --- | --- |
| `SECRET_KEY` | Shared session/CSRF signing key. If unset, a random key is persisted in `instance/.secret_key`. |
| `DATABASE_URL` | SQLAlchemy database URI. Defaults to SQLite in `instance/`. The included upgrade command supports SQLite only. |
| `COOKIE_SECURE` | Set `true` when serving over HTTPS. Leave `false` for local HTTP. |

Supported countries are Australia, Canada, China, France, Germany, Ireland, Japan, the United Kingdom and the United States. Their account currencies are AUD, CAD, CNY, EUR, JPY, GBP and USD.

## Upgrade an existing database

The original project stored floating-point balances in `account.balance`. The updated version detects that schema and displays an upgrade message rather than using it for account operations.

1. Stop the running application and make a backup of the entire `instance/` folder.
2. Install the updated requirements and run:

   ```bash
   python -m flask --app main migrate-db
   ```

3. Restart the application.

The command converts valid balances to integer hundredths, adds opening-balance history entries, enforces one account per user and restores missing zero-balance accounts from interrupted registrations. It refuses invalid balances or duplicate accounts for manual review. The original `balance` column remains untouched as a record of the old values; the updated application uses `balance_cents`. Do not run the old version against an upgraded database. Earlier transaction history cannot be reconstructed from balances alone.

## Docker

```bash
docker compose up --build
```

Open <http://127.0.0.1:5000>. Compose binds to localhost and stores the database and local session key in the `bank-data` named volume. The image runs Gunicorn as a non-root user. Optional settings in `.env` are passed through by Compose.

To upgrade an existing database already placed in that volume, stop the service, back up the volume, then run:

```bash
docker compose run --rm web flask --app main migrate-db
```

`docker compose down` preserves the volume. `docker compose down -v` deletes it and its demo accounts.

## Tests

```bash
python -m pip install -r requirements-dev.txt
python -m pytest --cov=Website --cov-report=term-missing
```

Tests use temporary SQLite databases and keep CSRF protection enabled. They cover registration and login, exact balance arithmetic, invalid input, transaction history isolation, concurrent withdrawals, transfer rollback, mocked currency-provider errors and migration from the original schema. No API key or live conversion service is required.

GitHub Actions runs tests on Python 3.11, 3.12 and 3.13 for pull requests and pushes to `main` or `dev`, then builds and smoke-tests the container. Pushes can publish `bankapp:latest` or `bankappdev:latest` to Docker Hub if the repository has `DOCKER_USERNAME` and `DOCKER_PASSWORD` secrets. Publishing is skipped when those credentials are absent; tests and container checks still run.

## Code layout

| Path | Purpose |
| --- | --- |
| `main.py` | Application entry point. |
| `Website/__init__.py` | Factory, configuration, extensions and country/currency setup. |
| `Website/auth.py` | Registration validation, login and logout. |
| `Website/models.py` | Users, accounts, country currencies and transaction history. |
| `Website/money.py` | Amount validation and atomic balance/ledger operations. |
| `Website/views.py` | Dashboard and authenticated money-operation routes. |
| `Website/currencybeacon.py` | External conversion requests and quote validation. |
| `Website/migration.py` | Explicit upgrade for the original SQLite database. |
| `Website/templates/`, `Website/static/` | Server-rendered pages and local CSS. |
| `tests/` | Isolated application and database-upgrade tests. |

Balance changes use conditional SQL updates, so a stale browser balance cannot authorise overspending. Each successful change and its history commit together; transfers update both accounts together. The ledger is written by the application and has no edit/delete route, but it is not tamper-proof against direct database access.

## Scope

This completes the original demo workflow, rather than implementing a production bank. It has no real payment connections, identity verification, password recovery, login rate limiting, transfer confirmation/quote acceptance or idempotency keys. Resubmitting a valid form creates another operation. Cross-currency transfers immediately use the provider's returned conversion and do not model fees, spreads or FX settlement. SQLite is suitable for a small local demo; broader deployment would need a separate security, operational and database design review.
