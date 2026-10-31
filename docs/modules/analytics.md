# Module: Analytics

**Path:** `backend/app/services/analytics.py`

All dashboard numbers come from here. SQL does the heavy `GROUP BY` work. Month bucketing, moving
averages and zero-filling happen in Python, so the same code runs on PostgreSQL and SQLite.

## Filters

`Filters(start, end, providers, environments, resource_types, services, regions)`, where `end` is inclusive.
`_cost_where(f)` and `_res_where(f)` build SQL conditions; `f.shifted(start, end)` reuses the same
scope for comparison periods.

## Functions

| Function | Returns | Used by |
|---|---|---|
| `total_cost(db, f)` | float | everywhere |
| `daily_totals(db, f)` | `{date: cost}` | MTD, anomaly baseline |
| `daily_series(db, f, group_by)` | zero-filled points with `total`, `ma7`, one key per group | Dashboard, Cost Explorer |
| `breakdown(db, f, dim)` | rows `key, cost, pct, previous, change_pct` (previous = equal-length prior period) | Dashboard, Cost Explorer, Reports |
| `month_to_date(db, f)` | `mtd`, `forecast`, `avg_daily_7d`, last-month comparisons | Summary, alert engine |
| `budget_info` | budget for the provider scope, `used_pct`, `forecast_pct`, `applies_to_filtered_view` | Summary |
| `summary(db, f)` | KPI bundle | `/dashboard/summary` |
| `month_spans(start, end)` | calendar months touched by a range, with covered days and `full` flag | monthly, reports |
| `monthly(db, f, months=None, group_by)` | one row per calendar month inside `f` (or the last `months` months): totals per key, `partial`, `change_pct` + `change_basis` (`total` / `run_rate`) | Cost Explorer, Reports |
| `resources(db, f, search, status, sort)` | inventory with period cost, latest and 7-day metrics, status | Resources, Dashboard |
| `utilization(db, f, hours)` | per-provider averages, peaks and current snapshot; bucketed CPU trend; counts; healthy rate | Dashboard, Resources |
| `resource_detail(db, pk, days, f)` | single resource: cost series for `f` (or last `days`), metrics, recommendations | Resource detail |
| `anomalies(db, f, threshold_pct)` | days where provider cost > trailing 7-day average + threshold (today excluded) | Dashboard, Cost Explorer, Reports |
| `recommendations(db, f)` | optimization actions with monthly savings | Resources, Reports, Summary |

## Key formulas

- **Forecast** = Σ full days of the month + (7-day average × remaining days including today).
  Today's partial cost is excluded so the forecast doesn't dip in the morning.
- **Anomaly**: `(cost_d − mean(cost_{d-7..d-1})) / mean × 100`; needs at least 4 prior days.
- **Resource status**: `over_utilized` if latest CPU ≥ 80 % (or storage ≥ 90 %); `idle` if the 7-day average CPU
  is below the idle threshold; `no_metrics` if the type reports none; otherwise `healthy`.
- **Healthy rate** = healthy ÷ (total − no_metrics).
- **Budget scope**: a provider budget when one provider is filtered; the total budget otherwise. With
  environment or type filters the budget is shown as informational only (`applies_to_filtered_view = false`).
- **Recommendations**: see [cost-optimization.md](../cost-optimization.md#11-recommendations-engine-analyticsrecommendations).

## Performance

Queries hit the composite indexes `(provider|environment|resource_type, usage_date)`. The overview
endpoint runs about 15 queries and returns in under 150 ms on the mock dataset.
