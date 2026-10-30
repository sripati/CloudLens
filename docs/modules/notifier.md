# Module: Notifier (Slack & Microsoft Teams)

**Path:** `backend/app/services/notifier.py`

| Function | Purpose |
|---|---|
| `resolve_channels(rule_channels, default_channel)` | `default` → Settings preference; `both` → `["slack","teams"]` |
| `slack_payload(title, message, severity, status, fields)` | Block Kit: header, section with severity emoji, fields grid, context link |
| `teams_payload(...)` | Adaptive Card 1.4 wrapped in a `message` attachment (Workflows webhook format), with colour by severity, FactSet and Open-dashboard action |
| `send(channels, ...)` | POSTs with `httpx` (10 s timeout); returns `(sent \| partial \| failed \| skipped, error)` |

Delivery status and errors are stored on the `alert_events` row and shown in **Alerts → Event history**.

## Configuration

`SLACK_WEBHOOK_URL`, `TEAMS_WEBHOOK_URL` (secrets, `.env` only) and the preferred channel in Settings
(`notification_channel`). By default both URLs point at the mock receiver.

## Testing

`tests/conftest.py` replaces `notifier.send` with a recorder, so no HTTP calls happen in unit tests.
`test_payload_shapes` checks both payload formats.

## Adding a channel (for example email or PagerDuty)

1. Add `xxx_payload()` and a branch in `send()`.
2. Add the value to `CHANNELS` (models/alert.py), `resolve_channels`, the Settings schema, and the
   frontend selects (Alerts rule form, Settings, test notification).
