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

The webhook URLs and preferred channel (`notification_channel`) are set in Settings. Until URLs are saved, both channels use the
bundled test inbox (`monitoring/mock-receiver`).

## Testing

`tests/conftest.py` replaces `notifier.send` with a recorder, so no HTTP calls happen in unit tests.
`test_payload_shapes` checks both payload formats.

## Adding a channel (for example email or PagerDuty)

1. Add `xxx_payload()` and a branch in `send()`.
2. Add the value to `CHANNELS` (models/alert.py), `resolve_channels`, the Settings schema, and the
   frontend selects (Alerts rule form, Settings, test notification).
