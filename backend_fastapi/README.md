# Library backend (FastAPI)

This is the FastAPI replacement for the Flask app in [`../backend/`](../backend/). It keeps the same API contracts where it matters:

- Standard JSON envelope: `{ success, message, data, error, meta }` (see [`app/utils/response.py`](app/utils/response.py))
- **`HTTPException`** and **`RequestValidationError`** mapped to the same envelope in [`app/main.py`](app/main.py); unexpected errors return **500** with safe messaging and full trace in logs only
- JWT **access** + **refresh** tokens in HttpOnly cookies (`access_token_cookie`, `refresh_token_cookie`)
- Redis-backed refresh **JTI** revocation (`jwt:revoked:{jti}`) and `users.token_version` invalidation
- **Books API** with Redis **cache-aside** on `GET /books` and `GET /books/{id}` (`X-Cache: HIT|MISS`), invalidation on create/update/delete
- **Structured JSON logging** (method, path, status, duration, request id, auth and CRUD events)
- **Prometheus** metrics at `GET /metrics` (via `prometheus-fastapi-instrumentator`)

Endpoints (summary):

- `GET /health` — Postgres + Redis checks
- `POST /auth/register`, `/auth/login`, `/auth/logout`, `/auth/refresh`, `/auth/revoke`, `GET /auth/me`
- `GET|POST|PATCH|DELETE /books` — members can list/read; **admin** for create/update/delete

## Local run

```bash
cd backend_fastapi
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # adjust DATABASE_URL / REDIS_URL
alembic upgrade head     # or rely on dev bootstrap create_all (see below)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Dev bootstrap admin

If `APP_ENV` is `development` and `BOOTSTRAP_ADMIN=true`, startup runs `Base.metadata.create_all()` and seeds an admin user (same behavior as the Flask app). For production, prefer **Alembic** and set `BOOTSTRAP_ADMIN=false`.

### Existing database from Flask

If tables already exist from the Flask app, **do not** run `001_initial` upgrade (it uses `create_all` and may fail if objects differ). Instead:

```bash
alembic stamp 001_initial
```

Then use Alembic for future schema changes.

## Docker / Compose (infrastructure only)

From the **repository root**, Compose starts **Postgres, Redis, Prometheus, and Grafana** (no API container by default). Run the API **locally** with `uvicorn` and point [`.env`](.env.example) at `localhost` for the DB and Redis ports.

```bash
docker compose up -d
```

When you later add a `backend` service to Compose, use `postgresql+psycopg2://...@postgres:5432/...` and `redis://redis:6379/0`, and add a Prometheus scrape target for `backend:8000` in [`../observability/prometheus.yml`](../observability/prometheus.yml).

**Observability:** Grafana is provisioned with a **FastAPI overview** dashboard under [`../observability/`](../observability/); panels need the API reachable from Prometheus (after you wire scrape config).

## Cache performance (measurable)

With Redis running and an existing book id `N`, compare response time on a cold vs warm cache:

```bash
# First call — expect X-Cache: MISS
curl -sS -o /dev/null -w "time_total=%{time_total}s\n" \
  -b cookies.txt -c cookies.txt \
  http://localhost:8000/books/N

# Second call — expect X-Cache: HIT and usually lower time_total
curl -sS -D - -o /dev/null -w "time_total=%{time_total}s\n" \
  -b cookies.txt \
  http://localhost:8000/books/N
```

Log in first (as admin or member) so the `access_token_cookie` is set in `cookies.txt`, or pass cookies from your browser session.

## Cutover from Flask

1. Stop the Flask container/process.
2. Point clients at this service (same paths under `/auth` and `/health` plus `/books`).
3. Users must **log in again** — JWTs issued by Flask-JWT-Extended are not guaranteed to validate with this stack (signing/claims are aligned for new tokens, not legacy sessions).

The old Flask backend remains in `backend/` for reference until you delete it.
