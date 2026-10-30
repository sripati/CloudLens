# Module: Authentication & Role-Based Access Control

**Paths:** `backend/app/api/deps.py`, `backend/app/api/routes/auth.py`, `backend/app/core/security.py`,
`frontend/src/context/AuthContext.jsx`, `frontend/src/App.jsx`

## Flow

1. `POST /auth/login {email, password}` → bcrypt verify → JWT (`sub`=user id, `role`, `email`, `exp`).
2. The frontend stores the token in `localStorage` (`cloudlens.token`) and sends `Authorization: Bearer`.
3. `deps.get_current_user` decodes the token, loads the user, and rejects disabled or deleted users (401).
4. `deps.require_admin` adds the role check (403).
5. On any 401 the API client calls `logout()`, and the router redirects to `/login`.

## Roles

| Capability | Admin | Viewer |
|---|---|---|
| View all dashboards, costs, resources, reports; CSV export | ✓ | ✓ |
| Acknowledge alert events; change own password; display preferences | ✓ | ✓ |
| Create / edit / delete / disable alert rules; evaluate now; test notification | ✓ | |
| Trigger syncs, test connections, inject mock anomalies | ✓ | |
| Edit budgets, exchange rate, channel, thresholds | ✓ | |
| Manage users | ✓ | |

The UI hides admin-only items (Cloud Accounts, Users menu; *Sync now*, *New rule* buttons;
Settings fields become read-only) and the **API enforces** the same rules, so hiding is never the
only protection.

## Safeguards

- Admins cannot demote, disable or delete themselves (prevents lock-out).
- Duplicate emails → 409. Passwords need at least 8 characters for new users and changes.
- The JWT secret comes from the environment. Tokens expire after 8 h by default.
- Default users are seeded only when the table is empty (`services/seed.py`).

## Extending to SSO

Add an OIDC callback route that maps an IdP group to `admin` or `viewer`, creates the user on first login,
and issues the same JWT. The rest of the app needs no change.
