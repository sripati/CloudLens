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
├── utils/constants.js       providers, environments, types, colours, labels
├── components/
│   ├── Layout.jsx           sidebar nav (role-aware), cloud connection status, alert badge
│   ├── PageHeader.jsx       title + currency toggle + theme toggle + user chip / sign out
│   ├── FilterBar.jsx        provider · environment · type · date range (+ custom range)
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
| Theme | PrefsContext | localStorage `cloudlens.theme` (also applied before first paint in `index.html`) |
| Currency | PrefsContext | localStorage `cloudlens.currency` |
| Filters (provider, env, type, days, start/end) | PrefsContext | sessionStorage `cloudlens.filters`, shared by Dashboard, Cost Explorer and Resources |
| Server data | `useApi` per component | none |

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
