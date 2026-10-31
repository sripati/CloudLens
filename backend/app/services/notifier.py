"""Slack and Microsoft Teams notifications via incoming webhooks.

* Slack: Incoming Webhook (Block Kit message)
* Teams: Workflows / Incoming Webhook accepting an Adaptive Card attachment

Webhook URLs are saved on the Settings screen. Until then, messages go to the bundled test inbox
(monitoring/mock-receiver), which records them so delivery can be demonstrated without real workspaces.
"""
from __future__ import annotations

import logging
from typing import Dict, List, Tuple

import httpx

from app.core.config import get_settings

log = logging.getLogger("cloudlens.notifier")
SEVERITY_EMOJI = {"critical": ":red_circle:", "warning": ":large_orange_circle:", "info": ":large_blue_circle:"}
SEVERITY_COLOR = {"critical": "Attention", "warning": "Warning", "info": "Accent"}


def resolve_channels(rule_channels: str | None, default_channel: str) -> List[str]:
    choice = (rule_channels or "default").lower()
    if choice == "default":
        choice = (default_channel or "both").lower()
    if choice == "both":
        return ["slack", "teams"]
    if choice in ("slack", "teams"):
        return [choice]
    return []


def slack_payload(title: str, message: str, severity: str, status: str, fields: Dict[str, str]) -> dict:
    s = get_settings()
    icon = ":white_check_mark:" if status == "resolved" else SEVERITY_EMOJI.get(severity, "")
    prefix = "RESOLVED" if status == "resolved" else severity.upper()
    return {
        "text": f"[{prefix}] {title}",
        "blocks": [
            {"type": "header", "text": {"type": "plain_text", "text": f"{prefix}: {title}"[:150]}},
            {"type": "section", "text": {"type": "mrkdwn", "text": f"{icon} {message}"}},
            {"type": "section", "fields": [{"type": "mrkdwn", "text": f"*{k}*\n{v}"} for k, v in list(fields.items())[:10]]},
            {"type": "context", "elements": [{"type": "mrkdwn", "text": f"CloudLens · <{s.DASHBOARD_PUBLIC_URL}/alerts|Open dashboard>"}]},
        ],
    }


def teams_payload(title: str, message: str, severity: str, status: str, fields: Dict[str, str]) -> dict:
    s = get_settings()
    prefix = "RESOLVED" if status == "resolved" else severity.upper()
    return {
        "type": "message",
        "attachments": [
            {
                "contentType": "application/vnd.microsoft.card.adaptive",
                "content": {
                    "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                    "type": "AdaptiveCard",
                    "version": "1.4",
                    "body": [
                        {"type": "TextBlock", "text": f"{prefix}: {title}", "weight": "Bolder", "size": "Medium",
                         "color": "Good" if status == "resolved" else SEVERITY_COLOR.get(severity, "Default"), "wrap": True},
                        {"type": "TextBlock", "text": message, "wrap": True},
                        {"type": "FactSet", "facts": [{"title": k, "value": str(v)} for k, v in fields.items()]},
                    ],
                    "actions": [{"type": "Action.OpenUrl", "title": "Open CloudLens", "url": f"{s.DASHBOARD_PUBLIC_URL}/alerts"}],
                },
            }
        ],
    }


def send(channels: List[str], title: str, message: str, severity: str, status: str, fields: Dict[str, str], urls: Dict[str, str]) -> Tuple[str, str]:
    """Send to each channel. Returns (status, error) where status is sent|partial|failed|skipped."""
    if not channels:
        return "skipped", "no channel selected"
    errors = []
    ok = 0
    with httpx.Client(timeout=10) as client:
        for ch in channels:
            url = urls.get(ch)
            if not url:
                errors.append(f"{ch}: webhook URL not configured")
                continue
            body = slack_payload(title, message, severity, status, fields) if ch == "slack" else teams_payload(title, message, severity, status, fields)
            try:
                resp = client.post(url, json=body)
                if resp.status_code >= 300:
                    errors.append(f"{ch}: HTTP {resp.status_code} {resp.text[:200]}")
                else:
                    ok += 1
            except httpx.HTTPError as exc:
                errors.append(f"{ch}: {type(exc).__name__}: {exc}")
    if ok == len(channels):
        return "sent", ""
    if ok:
        return "partial", "; ".join(errors)
    log.warning("notification failed: %s", errors)
    return "failed", "; ".join(errors)
