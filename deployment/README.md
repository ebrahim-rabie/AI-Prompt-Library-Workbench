# Deployment

Local setup is described in the [main README](../README.md). This page lists what changes in production.

## Environment variables

Copy [`.env.example`](.env.example) to `.env` (or set the variables in the hosting dashboard).

| Variable | Production value |
|---|---|
| `FLASK_CONFIG` | `production` |
| `SECRET_KEY` | A long random value. The app refuses to start in production without it. |
| `DATABASE_URL` | The PostgreSQL connection string from the host, e.g. `postgresql://user:pass@host:5432/db` |
| `ADMIN_USERNAME`, `ADMIN_EMAIL`, `ADMIN_PASSWORD` | The first administrator, used once by `seed.py` |

PostgreSQL needs a driver that is not in `requirements.txt` because development uses SQLite:

```bash
pip install psycopg2-binary
```

## Steps on the server

```bash
pip install -r requirements.txt
flask --app src/wsgi.py db upgrade      # create or update the tables
python deployment/seed.py               # first administrator + initial tags (safe to re-run)
```

Start the app with a production WSGI server instead of `flask run`, for example:

```bash
pip install gunicorn
gunicorn --chdir src wsgi:app
```

## What the production config does

- Session cookie is `Secure`, `HttpOnly` and `SameSite=Lax`.
- Plain HTTP requests are redirected to HTTPS (SRS 3.5.4). The app trusts the host's
  `X-Forwarded-Proto` header, so it must run behind the host's HTTPS proxy.
- Error pages never show stack traces; errors are written to the server log.
