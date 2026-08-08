# Traveler Finance

Mobile-first PWA for shared trip finances: expenses, money transfers, advances, loans, and loan repayments.

## Architecture

- Backend: Python standard library HTTP server.
- Database: SQLite, stored at `data/traveler.sqlite3` by default.
- Frontend: static PWA in `static/`.
- Money: all values are stored as integer minor currency units, never as floating point.

Financial operation types are intentionally separated:

- `expenses` are shared costs and affect expense shares.
- `money_transfers` are cash flows only. `transfer` and `advance` do not become expenses automatically.
- `loans` track principal and remaining debt separately.
- `loan_repayments` preserve repayment history and reduce only `remaining_amount_minor`.

## Run

```bash
python3 backend/app.py
```

Open `http://127.0.0.1:8080`.

Optional environment variables:

```bash
PORT=8081 TRAVELER_DB=/var/lib/traveler/traveler.sqlite3 python3 backend/app.py
```

## API

- `GET /api/trips`
- `POST /api/trips`
- `GET /api/trips/:id`
- `PUT /api/trips/:id`
- `DELETE /api/trips/:id`
- `GET /api/trips/:id/summary`
- `GET /api/trips/:id/families`
- `POST /api/trips/:id/families`
- `DELETE /api/trips/:id/families/:familyId`
- `POST /api/trips/:id/expenses`
- `POST /api/trips/:id/transfers`
- `GET /api/trips/:id/loans`
- `POST /api/trips/:id/loans`
- `POST /api/trips/:id/loans/:loanId/repayments`
- `GET /api/trips/:id/journal`

Deletes for expenses, transfers, and loans are soft deletes:

```http
DELETE /api/trips/:id/expenses/:expenseId
DELETE /api/trips/:id/transfers/:transferId
DELETE /api/trips/:id/loans/:loanId
```

## Production Notes

For Ubuntu deployment, run the app behind Nginx or Caddy and keep the SQLite file in a persistent directory such as `/var/lib/traveler`. The app creates the schema automatically on startup and seeds the example trip `Италия 2026` when the database is empty.
