# Screen: Reports

**Route:** `/reports` · **File:** `frontend/src/pages/ReportsPage.jsx` · **APIs:** `/reports/monthly`, `/reports/monthly.csv`

![Reports](../screenshots/06_reports_dark.png)

## Purpose
A monthly summary for finance and management reviews.

## Sections
- **Month picker** (last 6 months), **Download CSV**, **Print / PDF** (browser print).
- **KPIs:** month total (marked "to date" if current), previous month and change, budget used (bar), potential savings.
- **By provider** (donut), **by environment** and **by resource type** (bar lists).
- **Top services** with share and change vs the previous period.
- **Anomalies this month.**
- **Optimization recommendations** with savings.

## Extension notes
Scheduled email of this report: render it server-side (WeasyPrint) from `reports.build_monthly` and
send it weekly from a scheduler job.
