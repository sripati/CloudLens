# Module: Frontend Application

**Path:** `frontend/src/`. React 18 + React Router 6 + Recharts 3, built with Vite. Plain JavaScript (JSX).

## Structure

```
src/
├── main.jsx                 Router + AuthProvider + PrefsProvider
├── App.jsx                  Routes, RequireAuth (and admin-only) guards
├── api/client.js            fetch wrapper: base URL, JWT header, error → message, 401 → logout, CSV download
├── context/
│   ├── AuthContext.jsx      user, login, logout, isAdmin
│   └── PrefsContext.jsx     theme, currency, exchange rate, settings, shared filters, fmt helpers
├── hooks/useApi.js          GET with params, auto-refresh (refreshMs), keeps old data while loading
├── utils/format.js          money / compact (K, L, Cr) / pct / dates
├── utils/dates.js           ISO-date math, presets (relative to today), resolveRange, validateRange
├── utils/constants.js       providers, environments, types, colours, labels
├── components/
│   ├── Layout.jsx           sidebar nav (role-aware), cloud connection status, alert badge, user bar (name, role, Logout)
│   ├── PageHeader.jsx       title, subtitle and page actions
│   ├── FilterBar.jsx        provider · environment · type · DateRangePicker
│   ├── DateRangePicker.jsx  calendar popover: presets, 2-month calendar, From/To inputs, validation, keyboard support
│   ├── ui.jsx               Card, Segmented, Badge, StatusBadge, Progress, Modal, Toast, Skeleton, ErrorBox
│   ├── widgets.jsx          KpiCard, BarList, ProviderLegendRows, UtilizationPanel, ResourceTable, AlertList
│   ├── Icon.jsx             inline stroke icons
│   └── charts/              CostTrendChart, DonutChart, MonthlyBarChart, UtilizationChart, ChartTooltip
├── pages/                   one file per screen (see docs/screens)
└── styles/theme.css         design tokens for dark and light; app.css layout and components
```

## State

| State | Where | Persistence |
|---|---|---|
| JWT | `api/client.js` | localStorage `cloudlens.token` |
| Theme (changed in Settings) | PrefsContext | localStorage `cloudlens.theme` (also applied before first paint in `index.html`) |
| Currency (changed in Settings) | PrefsContext | localStorage `cloudlens.currency` |
| Filters (provider, env, type, `range`) | PrefsContext | sessionStorage `cloudlens.filters`, shared by Dashboard, Cost Explorer, Resources, Reports and resource detail. `range` stores a preset key (`last_30_days`…) or `{preset:'custom', start, end}` |
| Date bounds (`today`, `min_date`) | PrefsContext, from `GET /costs/date-bounds` | refreshed on load and every 15 min |
| Server data | `useApi` per component | none |

## Date range picker

`components/DateRangePicker.jsx` + `utils/dates.js`.

- **No hard-coded dates.** Presets (`PRESETS` in `dates.js`) are functions of *today*, and *today* comes from the server
  (`/costs/date-bounds`, in `TIMEZONE`), so the browser's clock or timezone never shifts a range. A stored preset is
  re-resolved on every render, so *Last 30 days* still means the last 30 days tomorrow.
- **Validation** (`validateRange`, mirrors the backend's `validate_range`): both dates required and real; neither in the
  future; start ≤ end; start not before the first date with data; at most `max_range_days` (731). Invalid typed input
  shows a message (`role="alert"`) and disables *Apply*; future and no-data days are disabled in the calendar.
- **Interaction:** presets apply in one click; a custom range is click-start, click-end (hover preview), then *Apply*.
  Escape or clicking outside cancels. The popover measures the space and opens left, right or centred.
- **Accessibility:** `role="dialog"`, grid of day buttons with full-date `aria-label`s (today, start, end, unavailable),
  roving tab stop with arrow keys / Page Up / Page Down / Home / End.
- Used by `FilterBar` (shared range), `ResourceDetailPage` (shared range) and `ReportsPage` (its own range,
  `REPORT_PRESETS`). Pages wait for `boundsReady` before fetching, so they never request a range computed from a
  wrong "today".

To add a preset: add an entry to `PRESETS` (`label`, `range(today) → {start, end}`) and its key to `DASHBOARD_PRESETS`
or `REPORT_PRESETS`; add a case to `utils/dates.test.js`.

## Theming

All colours are CSS variables in `theme.css` under `:root[data-theme='dark'|'light']`. Charts use
`var(--aws)` etc. directly, so switching theme needs no re-render logic. Provider colours differ in lightness
as well as hue (accessibility), and all text colours meet 4.5:1 contrast.

## Currency

The API always returns USD. `fmt(usd)` and `fmtCompact(usd)` convert using the Settings exchange rate
and format as `en-US` ($) or `en-IN` (₹, lakh and crore units).

## Real-time behaviour

`useApi(path, params, { refreshMs: 60000 })` refetches every 60 s while the tab is visible. The
Dashboard, Resources and Alerts screens use it. The footer shows the last refresh time.

## Dev / build / test

```bash
npm run dev      # Vite on :5173, proxies /api and /health to :8000 (VITE_API_PROXY to override)
npm run build    # dist/ (vendor and charts split into separate chunks)
npm test         # vitest + Testing Library (format utils, UI primitives)
```

## Adding a screen

1. Create `src/pages/NewPage.jsx` using `PageHeader`, `Card` and `useApi`.
2. Add the route in `App.jsx` (wrap in `<RequireAuth admin>` if admin-only).
3. Add a nav entry in `components/Layout.jsx` (`admin: true` to hide from viewers).
4. Document it in `docs/screens/`.
