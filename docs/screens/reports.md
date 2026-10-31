# Screen: Reports

**Route:** `/reports` · **File:** `frontend/src/pages/ReportsPage.jsx` · **APIs:** `/reports/summary`, `/reports/summary.csv`, `/costs/date-bounds`

![Reports](../screenshots/06_reports_dark.png)

## Purpose
A cost report for **any period** (a month, the last 6 months, year to date, a custom range) for finance and management
reviews, downloadable as CSV or printable to PDF.

## Header
- **Report period** (date-range calendar, `REPORT_PRESETS`): This month (default), Last month, Last 3 / 6 / 12 months,
  Year to date, Last 30 / 90 days, or a custom range. All presets are computed from today; the same validation as the
  dashboard applies (no future dates, start ≤ end, at most 731 days, not before the first data).
- **Download CSV**: `cloudlens_report_<start>_to_<end>.csv` with summary, monthly breakdown, breakdowns, anomalies and recommendations.
- **Print / PDF**: browser print; print styles hide the sidebar, toolbar and filters.

## Sections

| Section | Details |
|---|---|
| Period line | Preset name, exact dates, number of days, and the comparison period |
| KPIs | Total and daily average · previous period of equal length with change % (notes when data does not cover all of it) · budget used, with the monthly budget pro-rated to the days in the range · potential savings |
| Monthly breakdown | Stacked bar chart (when the range spans 2+ months) and a table: month, cost per provider, total, budget used % for that month, change vs previous month (*run rate* for partial or in-progress months), and a totals row |
| By provider / environment / resource type | Donut and bar lists |
| Top services | Cost, share and change vs the previous period |
| Anomalies | Days > 40 % above the 7-day baseline within the period (first 12 on screen, all in the CSV) |
| Recommendations | Current optimisation actions and savings |

The selected period is remembered for the browser session (`sessionStorage cloudlens.reportRange`).

## Extension notes
Scheduled email of this report: render `reports.build_report` server-side (WeasyPrint) and send it from a scheduler job.
