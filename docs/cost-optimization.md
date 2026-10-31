# Cost Optimization

Cost optimization is handled at two levels: **features that save money on the monitored clouds**, and
**design choices that keep CloudLens itself cheap to run**.

## 1. Features that reduce cloud spend

### 1.1 Recommendations engine (`analytics.recommendations`)

Every resource with cost in the last 30 days is checked against its 7-day utilization:

| Rule | Condition | Action | Estimated saving |
|---|---|---|---|
| Idle (non-prod) | avg CPU < idle threshold (10 %) | Stop it, or schedule it off outside working hours | 90 % of monthly cost |
| Idle (production) | avg CPU < 10 % | Rightsize to a smaller family | 50 % |
| Under-utilized | avg CPU < 30 % and memory < 50 % | Move one size down | 40 % |
| Non-prod 24x7 | dev/staging compute running all week | Shut down nights and weekends | 60 % |
| Low storage use | storage used < 20 % | Infrequent-access / archive tier, lifecycle rules | 45 % |

Thresholds are editable in **Settings → Optimization thresholds**. On the mock dataset this produces
8 recommendations worth about **USD 9.3K / month (≈ 8.5 % of spend)**, led by an idle GPU training VM
(USD 3.4K).

### 1.2 Visibility features

- **Budget KPI and forecast** with an 80 % warning rule and a forecast > 100 % critical rule. Overruns
  are caught mid-month, not on the invoice.
- **Anomaly detection** (day > 40 % above the trailing 7-day average) catches runaway jobs within a day.
- **Idle-resource alert** sends a daily nudge to the owning team.
- **Breakdowns by environment** show non-production share. Dev/staging spend is the easiest to cut.
- **Drill-down per resource** shows the cost and CPU history behind every recommendation.

## 2. Keeping CloudLens cheap to run

| Area | Design choice | Effect |
|---|---|---|
| Cost Explorer API (USD 0.01/request) | Backfill once; daily sync only re-fetches `SYNC_LOOKBACK_DAYS`=3; today's cost refreshes at most every 360 min per Live connection; `api_calls` recorded per sync run | ~5 requests/day per connection ≈ **USD 1.50/month** instead of ~USD 29 for 15-minute polling |
| BigQuery (GCP) | Query filters on `_PARTITIONTIME`; `maximum_bytes_billed` = 2 GB guard | Each sync scans only recent partitions, within the free 1 TB/month |
| Azure Query API | 7-day windows, aggregated server-side (Daily, grouped) | Few calls, no throttling |
| Compute | Single t3.small for the whole stack; 1 backend worker; in-process scheduler (no Redis/Celery) | ≈ USD 15/month |
| Storage | Retention: metrics 90 d, costs 730 d, sync logs 60 d; Prometheus retention 15 d; Docker log rotation 10 MB × 3 | Disk stays < 2 GB, so 20 GB gp3 is plenty |
| Images | Multi-stage frontend (nginx ≈ 50 MB); `python:slim`| Faster deploys, less EBS and ECR storage |
| Network | Static assets gzip-compressed and cached for 1 year (hashed filenames) | Low data transfer |
| Credentials | IAM instance role rather than access keys | No key-rotation overhead, lower risk |
| Scheduling | `create-ec2.sh` tags the instance; stop it outside demo hours | ≈ 65 % lower compute cost for staging |

### Monthly running cost of the staging deployment

| Item | USD |
|---|---|
| t3.small on-demand (730 h) | ~15.2 |
| 20 GB gp3 | ~1.9 |
| Public IPv4 | ~3.6 |
| Cost Explorer API | ~1.5 |
| BigQuery / Azure APIs | ~0 (free tier) |
| **Total** | **≈ 21 (₹1,770)** |

A t4g.small (Graviton) costs about 20 % less again; the images are multi-arch compatible.

## 3. Talking points for the viva

1. "We don't poll Cost Explorer every minute. It costs a cent per call, so the daily job re-reads only 3
   days, and we record API calls per sync so the overhead is visible."
2. "Recommendations turn monitoring into savings: the demo data shows USD 9.3K a month of waste,
   mostly one idle GPU VM in development."
3. "The whole platform runs on one t3.small for about USD 21 a month, and retention policies keep storage flat."
