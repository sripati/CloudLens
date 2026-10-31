# Module: Settings Service

**Path:** `backend/app/services/settings_service.py`, route `routes/settings.py`, screen [Settings](../screens/settings.md)

Runtime settings that admins change from the UI are stored as JSON in `app_settings`; application
secrets and infrastructure settings stay in `.env`. Slack and Teams webhook URLs are stored encrypted in `app_settings`
(`webhooks_encrypted`); `webhook_urls` falls back to the bundled test inbox, and `publish_alertmanager_slack_url` writes the Slack URL
to the volume Alertmanager reads.

| Key | Default | Used by |
|---|---|---|
| `monthly_budget_usd` | `DEFAULT_MONTHLY_BUDGET_USD` (120000) | Budget KPI, budget/forecast rules, reports |
| `provider_budgets_usd` | 48 % / 32 % / 20 % of total | Budget when filtered to one provider |
| `exchange_rate_inr` | 84.20 | Frontend INR display; Azure/GCP INR → USD conversion |
| `default_currency` | USD | Initial display currency for users without a saved preference |
| `notification_channel` | `DEFAULT_NOTIFICATION_CHANNEL` (both) | Rules with channel = default |
| `idle_cpu_threshold` | 10 | Resource status, idle alert, recommendations |
| `underutilized_cpu_threshold` | 30 | Recommendations |
| `mock_anomalies` | [] | Demo spikes (not editable via PUT, managed by `/sync/mock/anomaly`) |

Functions: `defaults()`, `get_value(db, key)`, `get_all(db)`, `set_value(db, key, value)`,
`budget_for(db, provider)`. `EDITABLE_KEYS` limits what `PUT /settings` can change.

Saving settings in the UI also calls `/alerts/evaluate`, so budget changes reflect in rule states at once.
