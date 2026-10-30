# User Guide

This guide walks through daily use of CloudLens. Details of every screen are in [screens/](screens/).

## 1. Signing in

Open the dashboard URL and sign in. Your role decides what you can do:

- **Admin:** everything, including alert rules, cloud accounts, users and settings.
- **Viewer:** read-only access to all dashboards and reports; can acknowledge alerts.

Use the sun/moon button to switch between **dark and light** themes, and **USD $ / INR ₹** to change the
display currency. Both choices are remembered in your browser.

## 2. Daily check (Dashboard)

1. Look at the **KPI cards**: spend in the selected period and its change, month-to-date against budget,
   forecast, active alerts, and potential savings.
2. In **Daily cost trend**, red rings mark anomaly days and the dashed red line is the daily budget.
3. **Spend by provider** and **by resource type** show where the money goes.
4. **Resource utilization** shows current CPU and memory per cloud. Bars turn red at 80 %.
5. **Recent alerts** lists what was sent to Slack and Teams.
6. Click any row in **Top resources by cost** to see its history.

The page refreshes itself every minute.

## 3. Filtering and drilling down

The filter bar appears on Dashboard, Cost Explorer and Resources, and the selection carries across them:

- **Cloud provider:** All, AWS, Azure or GCP
- **Environment:** production, staging, development, unassigned (untagged)
- **Resource type:** compute, containers, database, storage, networking, other
- **Date range:** 7, 30 or 90 days (Cost Explorer adds 180 days and a custom from/to range)

*Reset filters* returns to all providers and 30 days.

## 4. Analysing history (Cost Explorer)

- Switch **Group by** between provider, environment, resource type and total.
- The **Monthly cost** chart and **Month-over-month** table show trends. The current month is compared by
  daily run rate because it is not finished.
- **Cost breakdown** lets you rank by service, region or account and compare with the previous period.
- **Export CSV** downloads the raw normalized lines for Excel.

## 5. Finding waste (Resources)

- Filter the inventory by status: **Over-utilized** (risk to performance) or **Idle** (wasted money).
- The **Recommendations** table lists concrete actions and estimated monthly savings.
- Open a resource to check its 7-day CPU and memory before acting.

## 6. Alerts

### Creating a rule (admin)

1. Alerts → **New rule**.
2. Pick what to **watch**, for example *Daily cost of the last full day*.
3. Set the condition and threshold (for example `> 2000`).
4. Optionally limit the scope to a provider, environment or resource type.
5. Choose the severity and where to notify (Default, Slack, Teams or both).
6. Save. The rule is evaluated immediately and its state shows in the table.

Examples:

| Goal | Watch | Condition | Scope |
|---|---|---|---|
| Warn at 80 % of budget | Month-to-date as % of budget | ≥ 80 | all |
| Catch runaway jobs | Last day vs 7-day average (%) | > 40 | all |
| Production overload | Highest current CPU % | > 85 | Production |
| Dev spend control | Month-to-date cost | > 5000 | Development |
| Waste reminder | Idle resource count | > 0 | all |

### Receiving alerts
Alerts are delivered to the channel set on the rule, or the Settings default. Resolved alerts are
also sent. Repeats happen every 4 hours while a problem persists.

### History
**Event history** shows every notification and whether delivery succeeded. Use **Ack** to mark that
someone is handling it.

## 7. Reports
Pick a month to get its totals, comparison with the previous month, budget use, breakdowns, top services,
anomalies and recommendations. **Download CSV** or **Print / PDF** to share it.

## 8. Administration

- **Cloud Accounts:** check each provider's connection (*Test connection*), run a sync now, view scheduled jobs
  and the sync history (including API call counts). In mock mode you can **simulate a cost spike** to demonstrate alerting.
- **Users & Roles:** add users, change roles, disable or delete accounts.
- **Settings:** budgets (total and per provider), INR exchange rate, preferred notification channel, and the
  idle and under-utilized thresholds.

## 9. Glossary

| Term | Meaning |
|---|---|
| MTD | Month to date |
| Forecast | Full days so far + 7-day average × remaining days |
| Anomaly | A day more than 40 % above the previous 7-day average |
| Idle | 7-day average CPU below the idle threshold (default 10 %) |
| Over-utilized | Latest CPU ≥ 80 % (storage ≥ 90 %) |
| Unassigned | Cost without an environment tag |
