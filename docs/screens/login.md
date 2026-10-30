# Screen: Login

**Route:** `/login` · **File:** `frontend/src/pages/LoginPage.jsx` · **API:** `POST /auth/login`

![Login](../screenshots/00_login_dark.png)

## Purpose
Authenticate users and obtain a JWT.

## Layout
A centered card with the CloudLens logo, a theme toggle, email and password fields, and a *Sign in* button.
A note says the default accounts are defined in `.env`.

## Behaviour
- On success the token and user are stored (AuthContext) and the user returns to the page they
  originally requested (`location.state.from`), or `/`.
- Errors (wrong password, disabled account) show inline in a red box with `role="alert"`.
- Already signed-in users visiting `/login` are redirected to the dashboard.
- Inputs use `autocomplete="username"` and `"current-password"` for password managers.

## Extension notes
For SSO, add a "Sign in with Microsoft/Google" button that starts the OIDC flow. See
[../modules/auth-rbac.md](../modules/auth-rbac.md).
