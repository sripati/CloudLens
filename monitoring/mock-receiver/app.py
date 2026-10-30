"""Mock Slack / Microsoft Teams incoming-webhook receiver.

Stands in for real webhooks during development, testing and the viva demo.
* POST /slack    - accepts a Slack incoming-webhook payload
* POST /teams    - accepts a Teams Workflows / incoming-webhook payload (Adaptive Card)
* GET  /messages - JSON list of everything received (newest first)
* GET  /         - auto-refreshing web page that renders the messages like chat cards
* DELETE /messages - clear the inbox
"""
from __future__ import annotations

import html
import json
import os
from collections import deque
from datetime import datetime, timezone
from typing import Any, Deque, Dict

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse

app = FastAPI(title="CloudLens mock Slack/Teams receiver", version="1.0.0")
INBOX: Deque[Dict[str, Any]] = deque(maxlen=int(os.getenv("MOCK_RECEIVER_MAX", "500")))


def _summary(channel: str, body: Dict[str, Any]) -> Dict[str, str]:
    if channel == "slack":
        title = body.get("text", "")
        text = ""
        for block in body.get("blocks", []):
            if block.get("type") == "section" and "text" in block:
                text = block["text"].get("text", "")
                break
        return {"title": title, "text": text}
    try:
        card = body["attachments"][0]["content"]["body"]
        return {"title": card[0].get("text", ""), "text": card[1].get("text", "") if len(card) > 1 else ""}
    except (KeyError, IndexError, TypeError):
        return {"title": body.get("title", body.get("text", "")), "text": ""}


async def _store(channel: str, request: Request):
    try:
        body = await request.json()
    except json.JSONDecodeError:
        return {"ok": False, "error": "invalid json"}
    INBOX.appendleft({
        "channel": channel,
        "received_at": datetime.now(timezone.utc).isoformat(),
        **_summary(channel, body),
        "payload": body,
    })
    print(f"[{channel}] {INBOX[0]['title']}", flush=True)
    return {"ok": True}


@app.post("/slack")
async def slack(request: Request):
    await _store("slack", request)
    return "ok"  # Slack returns plain "ok"


@app.post("/teams")
async def teams(request: Request):
    return await _store("teams", request)


@app.get("/messages")
def messages(channel: str | None = None, limit: int = 100):
    items = [m for m in INBOX if not channel or m["channel"] == channel]
    return items[:limit]


@app.delete("/messages")
def clear():
    n = len(INBOX)
    INBOX.clear()
    return {"cleared": n}


@app.get("/health")
def health():
    return {"status": "ok", "messages": len(INBOX)}


@app.get("/", response_class=HTMLResponse)
def index():
    cards = []
    for m in INBOX:
        color = "#4A154B" if m["channel"] == "slack" else "#464EB8"
        cards.append(
            f"""<article><header><span class="tag" style="background:{color}">{m['channel'].upper()}</span>
            <time>{html.escape(m['received_at'][:19].replace('T', ' '))} UTC</time></header>
            <h2>{html.escape(m['title'])}</h2><p>{html.escape(m['text'])}</p></article>"""
        )
    body = "".join(cards) or "<p class='empty'>No messages yet. Trigger an alert or send a test notification from CloudLens.</p>"
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta http-equiv="refresh" content="5">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Mock Slack / Teams inbox</title>
<style>body{{margin:0;font-family:system-ui,sans-serif;background:#f4f5f7;color:#1d1c1d}}main{{max-width:760px;margin:0 auto;padding:24px 16px}}
h1{{font-size:20px}}article{{background:#fff;border:1px solid #dde1e6;border-radius:10px;padding:14px 16px;margin:0 0 12px}}
header{{display:flex;justify-content:space-between;align-items:center;font-size:12px;color:#555}}.tag{{color:#fff;border-radius:4px;padding:2px 8px;font-weight:600}}
h2{{font-size:15px;margin:8px 0 4px}}p{{margin:0;font-size:14px;line-height:1.45}}.empty{{color:#555}}</style></head>
<body><main><h1>Mock Slack / Teams inbox ({len(INBOX)})</h1>{body}</main></body></html>"""
