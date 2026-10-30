// Builds docs/report/CloudLens_Project_Report.docx
// Run: node docs/report/src/build_report.js   (from the repository root)
const fs = require('fs');
const path = require('path');
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType, Table, TableRow, TableCell,
  WidthType, ShadingType, ImageRun, PageBreak, TableOfContents, Footer, Header, PageNumber,
  LevelFormat, BorderStyle, Tab, TabStopType, LeaderType,
} = require('docx');

const ROOT = path.resolve(__dirname, '..');
const IMG = (f) => path.join(ROOT, 'img', f);
const FONT = 'Calibri';
const CONTENT_W = 9026; // A4 width 11906 - 2 * 1440 margins

// ---------- helpers ----------
const P = (text, opts = {}) => (paraCounter++, new Paragraph({
  spacing: { after: 120, line: 300 },
  alignment: opts.align || AlignmentType.JUSTIFIED,
  children: (Array.isArray(text) ? text : [text]).map((t) => (typeof t === 'string' ? new TextRun(t) : t)),
  ...opts.para,
}));
const B = (t) => new TextRun({ text: t, bold: true });
const I = (t) => new TextRun({ text: t, italics: true });
const C = (t) => new TextRun({ text: t, font: 'Consolas', size: 20 });
const H1 = (t) => (paraCounter++, new Paragraph({ heading: HeadingLevel.HEADING_1, pageBreakBefore: true, children: [new TextRun(t)] }));
const H2 = (t) => (paraCounter++, new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun(t)] }));
const H3 = (t) => (paraCounter++, new Paragraph({ heading: HeadingLevel.HEADING_3, children: [new TextRun(t)] }));
const bullet = (t, level = 0) => (paraCounter++, new Paragraph({
  numbering: { reference: 'bullets', level },
  spacing: { after: 60, line: 280 },
  children: (Array.isArray(t) ? t : [t]).map((x) => (typeof x === 'string' ? new TextRun(x) : x)),
}));
let listInstance = 0;
let lastNumberedIdx = -2;
let paraCounter = 0;
const numbered = (t) => {
  // consecutive numbered() calls share an instance; any other paragraph in between starts a new list
  if (paraCounter !== lastNumberedIdx) listInstance += 1;
  lastNumberedIdx = ++paraCounter;
  return numberedPara(t, listInstance);
};
const numberedPara = (t, inst) => new Paragraph({
  numbering: { reference: 'numbers', level: 0, instance: inst },
  spacing: { after: 60, line: 280 },
  children: (Array.isArray(t) ? t : [t]).map((x) => (typeof x === 'string' ? new TextRun(x) : x)),
});
const code = (lines) => lines.map((l, i) => new Paragraph({
  shading: { type: ShadingType.CLEAR, fill: 'F3F5F9', color: 'auto' },
  spacing: { after: i === lines.length - 1 ? 160 : 0, line: 260 },
  indent: { left: 200, right: 200 },
  children: [new TextRun({ text: l || ' ', font: 'Consolas', size: 18 })],
}));

const border = { style: BorderStyle.SINGLE, size: 4, color: 'C9D2DF' };
const borders = { top: border, bottom: border, left: border, right: border };
function table(headers, rows, widths) {
  paraCounter++;
  const total = widths.reduce((a, b) => a + b, 0);
  const scaled = widths.map((w) => Math.floor((w / total) * CONTENT_W));
  scaled[scaled.length - 1] += CONTENT_W - scaled.reduce((a, b) => a + b, 0);
  const cell = (text, i, head) => new TableCell({
    borders,
    width: { size: scaled[i], type: WidthType.DXA },
    shading: head ? { type: ShadingType.CLEAR, fill: '1D3A6E', color: 'auto' } : undefined,
    margins: { top: 60, bottom: 60, left: 100, right: 100 },
    children: [new Paragraph({ children: [new TextRun({ text: String(text), bold: head, color: head ? 'FFFFFF' : undefined, size: 19 })] })],
  });
  return new Table({
    width: { size: CONTENT_W, type: WidthType.DXA },
    columnWidths: scaled,
    rows: [
      new TableRow({ tableHeader: true, children: headers.map((h, i) => cell(h, i, true)) }),
      ...rows.map((r) => new TableRow({ children: r.map((c, i) => cell(c, i, false)) })),
    ],
  });
}
const gap = () => new Paragraph({ spacing: { after: 120 }, children: [] });

let figNo = 0;
function figure(file, caption, widthIn = 6.25) {
  const buf = fs.readFileSync(IMG(file));
  const { w, h } = imageSize(buf, file);
  const width = Math.round(widthIn * 96);
  let height = Math.round((h / w) * width);
  const maxH = Math.round(8.4 * 96);
  let finalW = width;
  if (height > maxH) { finalW = Math.round(width * (maxH / height)); height = maxH; }
  figNo += 1;
  paraCounter++;
  return [
    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 120, after: 60 },
      children: [new ImageRun({ type: file.endsWith('.png') ? 'png' : 'jpg', data: buf, transformation: { width: finalW, height } })] }),
    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 200 },
      children: [new TextRun({ text: `Figure ${figNo}: ${caption}`, italics: true, size: 19, color: '4A5468' })] }),
  ];
}
function imageSize(buf, file) {
  if (file.endsWith('.png')) return { w: buf.readUInt32BE(16), h: buf.readUInt32BE(20) };
  let i = 2; // JPEG: walk segments to SOF
  while (i < buf.length) {
    const marker = buf[i + 1];
    const len = buf.readUInt16BE(i + 2);
    if (marker >= 0xc0 && marker <= 0xc3) return { h: buf.readUInt16BE(i + 5), w: buf.readUInt16BE(i + 7) };
    i += 2 + len;
  }
  throw new Error('size not found ' + file);
}

function staticToc() {
  const f = path.join(__dirname, 'toc.json');
  const entries = fs.existsSync(f) ? JSON.parse(fs.readFileSync(f, 'utf8')) : [];
  return entries.map((e) => new Paragraph({
    spacing: { after: e.level === 1 ? 80 : 40, before: e.level === 1 ? 120 : 0 },
    indent: { left: e.level === 1 ? 0 : 400 },
    tabStops: [{ type: TabStopType.RIGHT, position: CONTENT_W, leader: LeaderType.DOT }],
    children: [
      new TextRun({ text: e.title, bold: e.level === 1, size: e.level === 1 ? 22 : 20 }),
      new TextRun({ children: [new Tab(), String(e.page)], size: e.level === 1 ? 22 : 20 }),
    ],
  }));
}

// ---------- content ----------
const cover = [
  new Paragraph({ spacing: { before: 1800 }, alignment: AlignmentType.CENTER, children: [new TextRun({ text: 'CAPSTONE PROJECT REPORT', bold: true, size: 26, color: '4A5468' })] }),
  new Paragraph({ spacing: { before: 400, after: 200 }, alignment: AlignmentType.CENTER, children: [new TextRun({ text: 'CloudLens', bold: true, size: 64, color: '1D5FD6' })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 600 }, children: [new TextRun({ text: 'DevOps Dashboard for Resource and Cost Monitoring', size: 36, bold: true })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 120 }, children: [new TextRun({ text: 'Multi-cloud (AWS · Azure · GCP) cost aggregation, trend analysis and alerting', size: 24, color: '4A5468' })] }),
  new Paragraph({ spacing: { before: 1400 }, alignment: AlignmentType.CENTER, children: [new TextRun({ text: 'Submitted by: [Student Name]', size: 24 })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: 'Enrolment / Roll No.: [Number]', size: 24 })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: 'Programme: [Programme name]', size: 24 })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: 'Institute: [Institute name]', size: 24 })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: 'Guide / Mentor: [Mentor name]', size: 24 })] }),
  new Paragraph({ spacing: { before: 400 }, alignment: AlignmentType.CENTER, children: [new TextRun({ text: 'October 2026', size: 24 })] }),
];

const abstract = [
  new Paragraph({ heading: HeadingLevel.HEADING_1, pageBreakBefore: true, children: [new TextRun('Abstract')] }),
  P('DevOps teams that operate on several public clouds see their spending in three separate consoles, each with a different vocabulary, billing delay and level of detail. Without one consolidated view it is hard to know where money is going, to spot a runaway workload before the invoice arrives, or to prove that infrastructure is right-sized.'),
  P(['This project delivers ', B('CloudLens'), ', a containerised DevOps dashboard that aggregates daily cost and resource-utilisation data from ', B('AWS Cost Explorer, Azure Cost Management and the GCP Cloud Billing export'), ', normalises it into one PostgreSQL schema, and presents real-time and historical views in a custom React.js dashboard. Users can filter and drill down by provider, environment, resource type and date range; analyse month-over-month trends and anomalies; and define their own alert rules for cost thresholds, budget forecasts, cost anomalies and over- or under-utilised resources. Alerts flow through ', B('Prometheus and Alertmanager'), ' to ', B('Slack and Microsoft Teams'), '.']),
  P('A rule-based optimisation engine converts the monitoring data into concrete savings actions (stop idle machines, rightsize, schedule non-production workloads, tier storage). On the demonstration dataset it identifies about USD 9.2K of monthly savings, roughly 8.5 % of spend. The platform itself runs on one t3.small EC2 instance for about USD 21 per month, through careful API usage and data-retention policies.'),
  P('The solution is built with Python (FastAPI, SQLAlchemy, APScheduler), PostgreSQL 16, React 18 and Recharts, packaged as six Docker containers, and deployable to AWS EC2 with the provided scripts. It is verified by 77 backend tests (run against both SQLite and PostgreSQL), frontend unit tests, and an end-to-end test of the full Prometheus → Alertmanager → Slack/Teams alert pipeline.'),
  P([B('Keywords: '), 'FinOps, multi-cloud, cost monitoring, DevOps dashboard, Prometheus, Alertmanager, FastAPI, React, PostgreSQL, Docker.']),
];

const toc = [
  new Paragraph({ heading: HeadingLevel.HEADING_1, pageBreakBefore: true, children: [new TextRun('Table of Contents')] }),
  ...staticToc(),
];

const ch1 = [
  H1('1. Introduction'),
  H2('1.1 Background'),
  P('Public cloud adoption lets teams provision infrastructure in minutes, but the pay-as-you-go model also means costs can grow silently. Organisations commonly use more than one provider, for example AWS for core services, Azure for Microsoft workloads and GCP for analytics. Each provider offers its own cost tool, but none gives a consolidated, comparable view across clouds, and native alerting is limited to per-provider budgets.'),
  H2('1.2 Problem statement'),
  P('DevOps teams struggle to monitor resource usage and manage costs across multiple cloud environments (AWS, Azure and GCP). Without clear visibility into resource allocation and spending, optimising cloud infrastructure is difficult, which leads to unnecessary costs and inefficiencies. The project aims to develop a centralised dashboard that aggregates data from the different cloud providers, lets teams track resource utilisation and cost trends, set cost thresholds, and receive alerts for anomalies.'),
  H2('1.3 Project goals'),
  numbered('Aggregate resource-utilisation and cost data from AWS, Azure and GCP into a single dashboard.'),
  numbered('Provide real-time and historical visualisation of resource usage and costs to help teams identify trends and optimise resources.'),
  numbered('Implement customisable alerting for cost thresholds, over-utilised resources and potential inefficiencies.'),
  numbered('Offer filters and drill-down by resource type, cloud provider and environment (production, staging, development).'),
  H2('1.4 Scope'),
  P('In scope: cost and utilisation ingestion from the three providers (with a realistic mock mode for development and demonstration), a PostgreSQL history store, analytics and recommendations, a role-based web dashboard, an alerting pipeline to Slack and Teams, Docker packaging, and EC2 staging deployment. Out of scope: automatic remediation (for example stopping instances), invoice reconciliation, and multi-tenant SaaS operation. These are listed as future enhancements.'),
  H2('1.5 Report organisation'),
  P('Chapter 2 reviews existing tools. Chapter 3 lists requirements. Chapters 4 and 5 describe the architecture and design. Chapter 6 covers implementation module by module. Chapter 7 describes alerting, Chapter 8 cost optimisation, Chapter 9 testing, and Chapter 10 deployment. Chapter 11 presents results with screenshots, and Chapter 12 concludes.'),
];

const ch2 = [
  H1('2. Existing Solutions and Gap Analysis'),
  table(['Tool', 'Strengths', 'Limitations for this problem'], [
    ['AWS Cost Explorer / Budgets', 'Detailed AWS costs, forecasts', 'AWS only; alerting limited to budgets'],
    ['Azure Cost Management', 'Azure + limited AWS view', 'AWS connector deprecated; no GCP'],
    ['GCP Billing reports', 'Good BigQuery export', 'GCP only'],
    ['Commercial FinOps platforms', 'Multi-cloud, rich features', 'Licence cost; data leaves the organisation'],
    ['Grafana + exporters', 'Flexible charts', 'No cost normalisation; rules edited as code; no role-aware rule editing'],
  ], [2.2, 2.4, 3.4]),
  gap(),
  P(['The gap is a ', B('self-hosted, low-cost'), ' tool that normalises all three clouds into one model, adds utilisation context, and lets non-developers define alert rules in a UI, while still using the standard Prometheus/Alertmanager pipeline that DevOps teams already operate.']),
];

const ch3 = [
  H1('3. Requirements'),
  H2('3.1 Functional requirements'),
  table(['ID', 'Requirement'], [
    ['FR-1', 'Fetch daily costs from AWS Cost Explorer, Azure Cost Management and the GCP billing export'],
    ['FR-2', 'Fetch resource inventory and CPU/memory utilisation (CloudWatch, Azure Monitor, Cloud Monitoring)'],
    ['FR-3', 'Normalise data into one schema (provider, account, day, service, type, environment, region)'],
    ['FR-4', 'Store history in PostgreSQL with scheduled daily and intraday jobs'],
    ['FR-5', 'Dashboard with KPIs, trends, breakdowns, utilisation and top resources; auto-refresh'],
    ['FR-6', 'Filters by provider, environment, resource type and date range; drill-down to a resource'],
    ['FR-7', 'Historical analysis: daily trend, moving average, month-over-month, breakdowns, anomalies'],
    ['FR-8', 'User-defined alert rules (metric, scope, threshold, severity, channel)'],
    ['FR-9', 'Notifications through Prometheus Alertmanager to Slack and/or Microsoft Teams'],
    ['FR-10', 'Login with role-based access (Admin, Viewer)'],
    ['FR-11', 'Display amounts in USD or INR with a configurable exchange rate'],
    ['FR-12', 'Dark and light theme toggle'],
    ['FR-13', 'Switch between mock and live data via .env'],
    ['FR-14', 'Monthly reports and CSV export'],
  ], [1, 7]),
  gap(),
  H2('3.2 Non-functional requirements'),
  table(['Category', 'Requirement'], [
    ['Performance', 'Dashboard API responds in < 1 s for 180 days of data'],
    ['Reliability', 'Idempotent syncs; one failing provider does not block others; health checks'],
    ['Security', 'Hashed passwords, JWT, RBAC enforced by the API, secrets only in .env, read-only cloud permissions'],
    ['Cost', 'Minimal paid API calls; runs on a single small instance'],
    ['Portability', 'One docker-compose for laptop and EC2'],
    ['Usability', 'Responsive layout, accessible contrast, keyboard-usable controls'],
    ['Maintainability', 'Modular code, tests, one documentation file per module and screen'],
  ], [1.6, 6.4]),
];

const ch4 = [
  H1('4. System Architecture'),
  P('CloudLens is composed of six containers orchestrated with Docker Compose: PostgreSQL, the FastAPI backend (which also hosts the scheduler and alert engine), the React frontend served by nginx, Prometheus, Alertmanager, and a mock Slack/Teams receiver used in development and demonstrations.'),
  ...figure('architecture.png', 'High-level architecture'),
  H2('4.1 Data flow'),
  numbered('APScheduler triggers jobs: a 180-day backfill on first start, a daily sync at 02:00 IST, an intraday refresh of today\'s cost every 15 minutes, and utilisation every 5 minutes.'),
  numbered('The provider factory returns the mock generator or the live connector according to DATA_SOURCE.'),
  numbered('Connectors return unified CostItem, ResourceItem and MetricItem objects; the normaliser maps service names and tags.'),
  numbered('The ingestion module upserts the rows with INSERT … ON CONFLICT DO UPDATE on natural keys, so re-runs never duplicate data. Every run is logged with its API-call count.'),
  numbered('The React app calls the REST API; analytics queries aggregate with indexed GROUP BY queries.'),
  numbered('The alert engine evaluates rules every minute and exports a Prometheus gauge per rule; Prometheus and Alertmanager handle the alert lifecycle and call the backend webhook, which notifies Slack and Teams.'),
  H2('4.2 Technology choices'),
  table(['Decision', 'Choice', 'Reason'], [
    ['Database', 'PostgreSQL 16', 'Cost data is tabular and relational; SQL aggregation, unique constraints and composite indexes suit trend analysis (MongoDB was considered)'],
    ['API', 'FastAPI', 'Async-capable, Pydantic validation, auto-generated OpenAPI docs'],
    ['Scheduler', 'APScheduler in-process', 'No message broker needed for a handful of jobs'],
    ['UI', 'Custom React + Recharts', 'Full control of filters, drill-down, RBAC-aware rule editing, theme and currency'],
    ['Alerting', 'Prometheus + Alertmanager', 'Standard tooling: grouping, de-duplication, silences, inhibition'],
    ['Notifications', 'Incoming webhooks', 'Slack Block Kit and Teams Adaptive Cards without bot tokens'],
    ['Packaging', 'Docker Compose', 'Same stack locally and on EC2'],
  ], [1.4, 1.8, 4.8]),
];

const ch5 = [
  H1('5. Design'),
  H2('5.1 Unified cost schema'),
  P('The key design decision is one grain for every provider: provider + account + day + service + environment + region + resource. The table below shows how each provider\'s fields are mapped.'),
  table(['Field', 'AWS', 'Azure', 'GCP'], [
    ['usage_date', 'TimePeriod.Start', 'UsageDate', 'DATE(usage_start_time)'],
    ['service', 'SERVICE dimension', 'ServiceName', 'service.description'],
    ['environment', 'tag environment$<v>', 'TagValue', 'label environment'],
    ['region', 'global', 'ResourceLocation', 'location.region'],
    ['cost_usd', 'UnblendedCost', 'Cost (INR→USD)', 'cost + credits'],
  ], [1.4, 2.2, 2, 2.4]),
  gap(),
  P('Service names are classified into compute, containers, database, storage, networking or other by ordered regular-expression rules. Tag values such as prod, prd, stg, uat, dev and test are mapped to production, staging, development or unassigned.'),
  H2('5.2 Database tables'),
  table(['Table', 'Purpose', 'Key constraint / index'], [
    ['cost_records', 'Normalised daily cost lines', 'UNIQUE on the natural grain; (provider|environment|type, date) indexes'],
    ['resources', 'Inventory', 'UNIQUE(provider, resource_id)'],
    ['resource_metrics', 'CPU / memory / storage samples', 'UNIQUE(resource_pk, ts)'],
    ['alert_rules', 'User-defined rules + live state', '—'],
    ['alert_events', 'Notifications sent and delivery status', 'index on fingerprint, created_at'],
    ['sync_runs', 'Audit of every fetch incl. API calls', 'index on provider, started_at'],
    ['users', 'Accounts and roles', 'UNIQUE(email)'],
    ['app_settings', 'Budget, exchange rate, channel, thresholds', 'key primary key'],
  ], [1.8, 3.2, 3]),
  gap(),
  H2('5.3 API design'),
  P('The REST API under /api/v1 is grouped into auth/users, dashboard, costs, resources, alerts, sync, settings and reports. All read endpoints accept the same filter parameters (days or start/end, provider, environment, resource_type, service, region), validated centrally. Write endpoints require the admin role. The Dashboard screen uses one aggregated /dashboard/overview call to minimise round trips. Interactive documentation is generated at /docs.'),
  H2('5.4 Module structure'),
  table(['Layer', 'Modules'], [
    ['core', 'config (pydantic-settings), database (SQLAlchemy), security (bcrypt, JWT)'],
    ['services', 'providers (aws, azure, gcp, mock), normalizer, ingestion, analytics, alert_engine, prom_metrics, notifier, scheduler, settings_service, seed'],
    ['api', 'deps (auth, RBAC, filters), routes (8 routers)'],
    ['frontend', 'api client, Auth and Prefs contexts, useApi hook, shared components, charts, 10 pages'],
  ], [1.4, 6.6]),
];

const ch6 = [
  H1('6. Implementation'),
  P('The work followed the six-sprint plan in content but was delivered in a single pass. This chapter describes the implementation in the order of the sprint goals.'),
  H2('6.1 Cloud integration (Sprint 1)'),
  bullet([B('AWS: '), 'boto3 Cost Explorer GetCostAndUsage (DAILY, UnblendedCost, grouped by SERVICE and the environment tag, paginated), EC2/RDS inventory, CloudWatch GetMetricData. It supports access keys, profiles, or the EC2 instance role.']),
  bullet([B('Azure: '), 'Cost Management Query API (ActualCost, daily, grouped by service, location and environment tag) in 7-day windows, Resource Manager inventory, and Azure Monitor CPU metrics, using a service principal.']),
  bullet([B('GCP: '), 'the Cloud Billing API does not return daily cost lines, so costs are read from the BigQuery billing export with partition filters and a 2 GB scan guard; the Cloud Billing API verifies the billing account; Cloud Monitoring supplies instances and CPU.']),
  bullet([B('Mock mode: '), 'a deterministic generator (hash of resource and date) produces 25 realistic resources with growth, weekly seasonality, noise, periodic anomalies and deliberate waste, so the system can be developed and demonstrated without credentials. DATA_SOURCE=mock|live switches modes.']),
  bullet('Credentials are configured in .env; the Cloud Accounts screen offers a Test connection button for each provider.'),
  H2('6.2 Aggregation and storage (Sprint 2)'),
  P('The ingestion module batches upserts in chunks of 1000 rows, merging duplicates in memory first because ON CONFLICT cannot update a row twice in one statement. Each provider is synchronised independently; a provider without credentials is recorded as skipped, and an exception is recorded as failed without affecting the others. A retention job removes old metric samples (90 days), cost lines (2 years) and sync logs (60 days).'),
  H2('6.3 Real-time dashboard (Sprint 3)'),
  P('The React dashboard implements the design approved before development: five KPI cards, a daily cost trend with a daily-budget line and anomaly markers, spend by provider (donut) and by resource type, current utilisation per provider, recent alerts, and the top resources table. Utilisation is sampled every 5 minutes and today\'s cost every 15 minutes; the page refreshes every 60 seconds. A shared filter bar (provider, environment, resource type, date range) is kept in session storage so it follows the user between screens.'),
  ...figure('01_dashboard_light.jpg', 'Dashboard (light theme)'),
  H2('6.4 Historical analysis (Sprint 4)'),
  P('Analytics functions compute zero-filled daily series with a 7-day moving average, breakdowns by any dimension compared with the previous equal-length period, monthly totals with month-over-month change (and run-rate change for the partial current month), forecasts (full days so far + 7-day average × remaining days), and anomalies (days more than 40 % above the trailing 7-day average). The Cost Explorer screen adds custom date ranges, group-by switching, 3/6/12-month views and CSV export.'),
  ...figure('02_cost_explorer_light.jpg', 'Cost Explorer with historical trends and month-over-month table'),
  H2('6.5 Resources and drill-down'),
  P('The Resources screen lists every resource with period cost, latest and 7-day CPU, and a status: over-utilised (CPU ≥ 80 %), idle (7-day average below 10 %), healthy, or no metrics. Selecting a row opens the resource detail page with 30 days of cost, 7 days of utilisation, tags and any recommendation.'),
  ...figure('03_resources_light.jpg', 'Resources: utilisation trend, inventory and recommendations'),
  H2('6.6 Authentication and roles'),
  P('Passwords are hashed with bcrypt and sessions use signed JWTs (8-hour expiry). FastAPI dependencies enforce authentication on every route and the admin role on every write. The UI hides admin-only navigation and actions for viewers, but the API is the source of truth. Admins cannot demote or delete themselves, which prevents lock-out.'),
  H2('6.7 Currency and theme'),
  P('The API always returns USD; the frontend converts to INR with the exchange rate stored in Settings and formats Indian units (K, lakh, crore). Themes are implemented with CSS custom properties for dark and light; charts use the same tokens, so switching is instant and contrast stays above WCAG AA in both themes.'),
];

const ch7 = [
  H1('7. Alerting and Notifications (Sprint 5)'),
  P('Users define rules in the Alerts screen. Every minute the alert engine computes each rule\'s value and exports cloudlens_alert_rule_breached with the rule\'s labels. A single Prometheus rule (CloudLensRuleBreached, for: 1m) turns breached series into alerts; Alertmanager groups, de-duplicates, repeats every 4 hours and sends resolved notifications to the backend webhook (protected by a bearer token). The backend stores an AlertEvent and posts a Slack Block Kit message and/or a Teams Adaptive Card, according to the rule\'s channel or the default preference.'),
  ...figure('alert_flow.png', 'Alert pipeline'),
  table(['Metric', 'Meaning', 'Example rule'], [
    ['daily_cost', 'Cost of the last full day', 'AWS > $1,800 (warning)'],
    ['mtd_cost', 'Month-to-date cost', 'Development > $5,000'],
    ['budget_used_pct', 'MTD as % of budget', '≥ 80 % (warning)'],
    ['forecast_budget_pct', 'Forecast as % of budget', '> 100 % (critical)'],
    ['cost_anomaly_pct', 'Last day vs 7-day average', '> 40 % (critical)'],
    ['resource_cpu / resource_memory', 'Highest current utilisation in scope', 'Production CPU > 80 %'],
    ['idle_resource_count', 'Resources with 7-day avg CPU < 10 %', '> 0 (info)'],
  ], [2.2, 3, 2.8]),
  gap(),
  P('Platform alerts are included too: backend down (routed straight to Slack, because the backend cannot relay it), sync failing, stale data and high API latency, with an inhibition rule to avoid duplicate noise. A mock receiver stands in for Slack and Teams during development and the viva demonstration, and an admin-only "simulate a cost spike" action makes the anomaly path easy to demonstrate.'),
  ...figure('05_alerts_light.jpg', 'Alerts screen: rules with live state'),
];

const ch8 = [
  H1('8. Cost Optimisation'),
  H2('8.1 Savings for the monitored clouds'),
  table(['Rule', 'Condition', 'Action', 'Est. saving'], [
    ['Idle (non-prod)', 'avg CPU < 10 %', 'Stop / schedule off', '90 %'],
    ['Idle (prod)', 'avg CPU < 10 %', 'Rightsize', '50 %'],
    ['Under-utilised', 'CPU < 30 % and mem < 50 %', 'One size down', '40 %'],
    ['Non-prod 24x7', 'dev/staging compute', 'Nights/weekends off', '60 %'],
    ['Low storage use', '< 20 % used', 'Archive tier / lifecycle', '45 %'],
  ], [1.8, 2.4, 2.2, 1.6]),
  gap(),
  P('On the demonstration data the engine finds 8 recommendations worth about USD 9.2K per month, led by an idle GPU training VM in development. Budget and forecast alerts catch overruns mid-month, and anomaly detection flags runaway jobs within a day.'),
  H2('8.2 Keeping the platform itself cheap'),
  bullet('Cost Explorer charges USD 0.01 per request, so the daily job re-reads only 3 days, intraday refresh is configurable (6 hours recommended live), and every sync records its API calls: about 2 requests a day (≈ USD 0.60/month) instead of about USD 30 for minute-level polling.'),
  bullet('BigQuery queries filter on the partition column with a 2 GB maximum-bytes-billed guard, keeping usage within the free tier.'),
  bullet('The whole stack runs on one t3.small (single backend worker, in-process scheduler, no Redis), with retention policies, 15-day Prometheus retention and Docker log rotation that keep the disk under 2 GB.'),
  bullet('A multi-stage nginx frontend image (≈ 50 MB), an optional cloud-SDK-free backend image, and an IAM instance role instead of long-lived keys.'),
  table(['Staging item', 'USD / month'], [
    ['t3.small on-demand', '~15.2'], ['20 GB gp3', '~1.9'], ['Public IPv4', '~3.6'], ['Cost Explorer API', '~0.6'], ['Total', '≈ 21 (₹1,770)'],
  ], [5, 3]),
];

const ch9 = [
  H1('9. Testing'),
  table(['Suite', 'Tests', 'Result'], [
    ['Backend on SQLite', '77', '77 passed'],
    ['Backend on PostgreSQL 16', '77', '77 passed'],
    ['Backend with pinned requirements (clean venv)', '77', '77 passed'],
    ['Frontend (Vitest)', '9', '9 passed'],
    ['promtool / amtool / docker compose config', '—', 'valid'],
    ['End-to-end alert pipeline', '5 steps', 'passed'],
  ], [4.5, 1.5, 2]),
  gap(),
  P('Backend line coverage is 85 % (analytics 96 %, alert engine 94 %). Key automated checks: breakdowns by provider, environment, type and service always add up to the period total; re-syncing never changes row counts; viewers receive HTTP 403 on every write endpoint; an injected cost spike is detected as an anomaly; Alertmanager duplicates are ignored; and Slack and Teams payloads have the expected structure.'),
  P('End-to-end, real Prometheus 2.55.1 and Alertmanager 0.27.0 were run against the backend: an injected AWS cost spike caused four rules to fire, eight messages (Slack and Teams) were delivered, and clearing the spike produced RESOLVED messages. Every screen was captured with Playwright in both themes and at phone width, with no application console errors.'),
  table(['ID', 'UI test case', 'Expected'], [
    ['UI-02', 'Sign in as viewer', 'Admin menus and actions hidden; Settings read-only'],
    ['UI-04', 'Switch to INR', 'Amounts in ₹ with lakh/crore units'],
    ['UI-05', 'Filter AWS', 'All widgets limited to AWS; AWS budget used'],
    ['UI-08', 'Click a resource', 'Drill-down with cost, utilisation and tags'],
    ['UI-09', 'Create rule', 'Evaluated immediately; state shown'],
    ['UI-10', 'Test notification', 'Message delivered; event marked sent'],
    ['UI-14', 'Phone width', 'Sidebar stacks, cards wrap, tables scroll'],
  ], [1, 3.5, 3.5]),
];

const ch10 = [
  H1('10. Deployment'),
  P('The same docker-compose.yml runs locally and on AWS EC2. Only the dashboard port is public; the API, Prometheus, Alertmanager and the mock receiver are bound to localhost and reached through nginx or an SSH tunnel. Containers run as non-root users with health checks and log rotation, and data persists in named volumes.'),
  numbered([C('create-ec2.sh'), ' creates a security group (SSH from the operator IP only, HTTP 80), an IAM role with a read-only policy, and a t3.small Amazon Linux 2023 instance with IMDSv2 and user data that installs Docker and swap.']),
  numbered([C('.env.staging'), ' holds the secrets (database password, JWT secret, webhook URLs) and AWS_USE_DEFAULT_CREDENTIALS=true to use the instance role.']),
  numbered([C('deploy.sh'), ' synchronises the project, uploads the environment file, runs docker compose up --build, and waits for /health.']),
  ...code(['cp .env.example .env.staging   # edit secrets', 'KEY_NAME=my-key ./deploy/aws/create-ec2.sh', 'EC2_HOST=<ip> SSH_KEY=~/.ssh/my-key.pem ./deploy/aws/deploy.sh']),
  P('A database backup script, a Makefile of common tasks, and a production-hardening checklist (HTTPS, removing the mock receiver, rotating defaults, EBS snapshots) are provided.'),
];

const ch11 = [
  H1('11. Results'),
  P('All four project goals were met. The screens below show the delivered application with mock data.'),
  ...figure('01_dashboard_dark.jpg', 'Dashboard in dark theme (approved design)'),
  ...figure('04_resource_detail_light.jpg', 'Resource drill-down'),
  ...figure('06_reports_light.jpg', 'Monthly report'),
  ...figure('07_cloud_accounts_light.jpg', 'Cloud Accounts: connectivity, scheduled jobs, spike simulation, sync history'),
  ...figure('09_settings_light.jpg', 'Settings: budgets, exchange rate, channels, thresholds'),
  ...figure('08_users_light.jpg', 'Users & Roles'),
  ...figure('00_login_dark.jpg', 'Login'),
  table(['Goal', 'Outcome'], [
    ['Aggregate AWS, Azure, GCP', 'Three connectors + mock; unified schema; 180-day backfill in ~3 s'],
    ['Real-time and historical visualisation', '5-min utilisation, 15-min cost, 60 s refresh; trends, MoM, anomalies, reports'],
    ['Customisable alerting', '8 metric types; Prometheus → Alertmanager → Slack/Teams verified end to end'],
    ['Filters and drill-down', 'Provider, environment, type, date range; per-resource drill-down'],
  ], [2.6, 5.4]),
];

const ch12 = [
  H1('12. Conclusion and Future Scope'),
  H2('12.1 Conclusion'),
  P('CloudLens shows that a small, self-hosted platform can give DevOps teams a single, trustworthy view of multi-cloud cost and utilisation. Normalising the three providers into one schema made cross-cloud comparison and filtering straightforward. Bridging user-defined rules into Prometheus kept the standard alerting toolchain while making rules editable by non-developers. The recommendations engine turns monitoring into measurable savings, and the platform\'s own running cost stays around USD 21 per month.'),
  H2('12.2 Learnings'),
  bullet('Each cloud exposes cost data differently: GCP requires the BigQuery export, AWS limits Cost Explorer to two group-by keys, and Azure pages large results. A unified data contract hides these differences from the rest of the system.'),
  bullet('Idempotent upserts and per-provider error isolation make scheduled ingestion safe to re-run.'),
  bullet('Paid monitoring APIs need cost-aware design: sync windows, caching and call accounting.'),
  H2('12.3 Future scope'),
  bullet('Alembic migrations, HTTPS, and a live exchange-rate feed.'),
  bullet('A separate worker container so the API can scale; table partitioning or TimescaleDB.'),
  bullet('ML-based forecasting and per-service anomaly detection.'),
  bullet('SSO (Azure AD / Google), audit log, scheduled email reports, Kubernetes cost allocation.'),
  bullet('Automated remediation with approval workflows; Savings Plan / RI recommendations.'),
];

const refs = [
  H1('References'),
  numbered('AWS Cost Explorer API Reference: GetCostAndUsage. Amazon Web Services documentation.'),
  numbered('Azure Cost Management Query API. Microsoft Learn.'),
  numbered('Export Cloud Billing data to BigQuery. Google Cloud documentation.'),
  numbered('Prometheus alerting rules and Alertmanager configuration. prometheus.io documentation.'),
  numbered('Slack incoming webhooks and Block Kit. Slack API documentation.'),
  numbered('Microsoft Teams Workflows webhooks and Adaptive Cards. Microsoft Learn.'),
  numbered('FastAPI, SQLAlchemy 2.0, APScheduler, React, Recharts project documentation.'),
  numbered('FinOps Foundation: FinOps Framework.'),
  H1('Appendix A: Repository and Documentation Map'),
  table(['Path', 'Contents'], [
    ['backend/', 'FastAPI service, connectors, analytics, alert engine, tests'],
    ['frontend/', 'React dashboard'],
    ['monitoring/', 'Prometheus config and rules, Alertmanager template, mock receiver'],
    ['deploy/aws/', 'EC2 creation, bootstrap, deploy scripts, IAM policy'],
    ['docs/', 'Architecture, setup, user guide, API, database, alerting, deployment, testing, cost optimisation, troubleshooting, sprint mapping'],
    ['docs/modules/', 'One document per module (15)'],
    ['docs/screens/', 'One document per screen (10)'],
  ], [2, 6]),
  gap(),
  H1('Appendix B: Key Configuration'),
  table(['Variable', 'Default', 'Meaning'], [
    ['DATA_SOURCE', 'mock', 'mock or live'],
    ['ENABLED_PROVIDERS', 'aws,azure,gcp', 'Providers to sync'],
    ['BACKFILL_DAYS', '180', 'History on first start'],
    ['METRICS_INTERVAL_MINUTES', '5', 'Utilisation sampling'],
    ['INTRADAY_COST_REFRESH_MINUTES', '15', 'Today\'s cost refresh (360+ live)'],
    ['ALERT_DELIVERY', 'alertmanager', 'or direct'],
    ['SLACK_WEBHOOK_URL / TEAMS_WEBHOOK_URL', 'mock receiver', 'Notification endpoints'],
    ['DEFAULT_MONTHLY_BUDGET_USD', '120000', 'Initial budget'],
    ['DEFAULT_EXCHANGE_RATE_INR', '84.20', 'Initial INR rate'],
  ], [3.4, 2, 2.6]),
];

const doc = new Document({
  creator: 'CloudLens project',
  title: 'CloudLens - DevOps Dashboard for Resource and Cost Monitoring',
  styles: {
    default: { document: { run: { font: FONT, size: 22 } } },
    paragraphStyles: [
      { id: 'Heading1', name: 'Heading 1', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { size: 34, bold: true, color: '1D3A6E', font: FONT }, paragraph: { spacing: { before: 240, after: 200 }, outlineLevel: 0 } },
      { id: 'Heading2', name: 'Heading 2', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { size: 27, bold: true, color: '1D5FD6', font: FONT }, paragraph: { spacing: { before: 240, after: 120 }, outlineLevel: 1 } },
      { id: 'Heading3', name: 'Heading 3', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { size: 23, bold: true, font: FONT }, paragraph: { spacing: { before: 180, after: 80 }, outlineLevel: 2 } },
    ],
  },
  numbering: {
    config: [
      { reference: 'bullets', levels: [{ level: 0, format: LevelFormat.BULLET, text: '•', alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 540, hanging: 300 } } } },
        { level: 1, format: LevelFormat.BULLET, text: '◦', alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 1000, hanging: 300 } } } }] },
      { reference: 'numbers', levels: [{ level: 0, format: LevelFormat.DECIMAL, text: '%1.', alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 540, hanging: 340 } } } }] },
    ],
  },
  sections: [
    { properties: { page: { margin: { top: 1440, bottom: 1440, left: 1440, right: 1440 } } }, children: cover },
    {
      properties: { page: { margin: { top: 1440, bottom: 1300, left: 1440, right: 1440 }, pageNumbers: { start: 1 } } },
      headers: { default: new Header({ children: [new Paragraph({ alignment: AlignmentType.RIGHT, children: [new TextRun({ text: 'CloudLens · DevOps Dashboard for Resource and Cost Monitoring', size: 17, color: '7A8599' })] })] }) },
      footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ children: ['Page ', PageNumber.CURRENT], size: 18, color: '7A8599' })] })] }) },
      children: [...abstract, ...toc, ...ch1, ...ch2, ...ch3, ...ch4, ...ch5, ...ch6, ...ch7, ...ch8, ...ch9, ...ch10, ...ch11, ...ch12, ...refs],
    },
  ],
});

// numbered lists restart per chapter is not needed for this report (single sequence per list type is acceptable)
const out = path.join(ROOT, 'CloudLens_Project_Report.docx');
Packer.toBuffer(doc).then((buf) => {
  fs.writeFileSync(out, buf);
  console.log('written', out);
});
