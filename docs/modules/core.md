# Module: Core (config, database, security)

**Path:** `backend/app/core/`

## config.py

- `Settings` (pydantic-settings) reads every environment variable, or `.env` / `../.env`. Defaults make the
  app run in mock mode with no configuration.
- `get_settings()` is cached with `lru_cache`, so read env vars **before** first import (the tests do this in `conftest.py`).
- Helper properties: `enabled_providers`, `cors_origins` (comma-separated values → lists).
- Nothing about Live connections is configured here: every cloud starts on Mock, and the Cloud Accounts screen decides after that.
- `crypto.py` encrypts credentials saved on that screen and webhook URLs saved in Settings (Fernet, key derived from `JWT_SECRET`).
- `database.add_missing_columns` applies schema changes made after the first release, because `create_all` never alters existing tables.

**Extending:** add a typed field with a default, document it in `.env.example`, and expose it in
`routes/settings.py → _public()["system"]` if the UI should display it.

## database.py

- `Base`: SQLAlchemy 2.0 `DeclarativeBase` that all models inherit.
- `engine` / `SessionLocal`: built from `DATABASE_URL`. PostgreSQL uses a pool (size `DB_POOL_SIZE`, overflow 5)
  with `pool_pre_ping`; SQLite (tests) uses `StaticPool` for in-memory databases.
- `get_db()`: FastAPI dependency that yields a session and always closes it.
- `init_db()`: imports `app.models` and runs `create_all` (idempotent).
- `configure_engine(url)`: re-points the engine (tests or tooling).

**Note:** schema changes to existing columns need a migration tool. See *Alembic* in
[future-enhancements.md](../future-enhancements.md).

## security.py

| Function | Purpose |
|---|---|
| `hash_password(pw)` | bcrypt, 12 rounds |
| `verify_password(pw, hash)` | Constant-time check; returns False on malformed hashes |
| `create_access_token(sub, role, extra)` | HS256 JWT with `sub`, `role`, `iat`, `exp` (+ email) |
| `decode_token(token)` | Verifies signature and expiry; raises `jwt.PyJWTError` subclasses |

The secret is `JWT_SECRET` (use 32+ characters). Expiry is `JWT_EXPIRE_MINUTES` (480).
