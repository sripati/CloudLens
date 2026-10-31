"""Capture screenshots of every screen (used for the documentation and report).

Usage:  python scripts/screenshots.py --base http://localhost:8080 --out docs/screenshots
Requires: pip install playwright && playwright install chromium
"""
from __future__ import annotations

import argparse
import os
import sys

from playwright.sync_api import sync_playwright

PAGES = [
    ("01_dashboard", "/"),
    ("02_cost_explorer", "/costs"),
    ("03_resources", "/resources"),
    ("04_resource_detail", "/resources/1"),
    ("05_alerts", "/alerts"),
    ("06_reports", "/reports"),
    ("07_cloud_accounts", "/accounts"),
    ("08_users", "/users"),
    ("09_settings", "/settings"),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://localhost:8080")
    ap.add_argument("--out", default="docs/screenshots")
    ap.add_argument("--email", default=os.getenv("ADMIN_EMAIL", "admin@cloudlens.dev"))
    ap.add_argument("--password", default=os.getenv("ADMIN_PASSWORD", "Admin@123"))
    ap.add_argument("--width", type=int, default=1440)
    ap.add_argument("--themes", default="dark,light")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    errors = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for theme in args.themes.split(","):
            ctx = browser.new_context(viewport={"width": args.width, "height": 900}, device_scale_factor=1)
            ctx.add_init_script(f"localStorage.setItem('cloudlens.theme', '{theme}')")
            page = ctx.new_page()
            page.on("console", lambda m: m.type == "error" and errors.append(f"{theme} {page.url}: {m.text}"))
            page.on("pageerror", lambda e: errors.append(f"{theme} {page.url}: {e}"))
            page.goto(args.base + "/login")
            if theme == args.themes.split(",")[0]:
                page.screenshot(path=f"{args.out}/00_login_{theme}.png")
            page.fill("#email", args.email)
            page.fill("#password", args.password)
            page.click("button[type=submit]")
            page.wait_for_url(args.base + "/")
            for name, path in PAGES:
                page.goto(args.base + path)
                page.wait_for_load_state("networkidle")
                if path == "/reports":  # show a multi-month report
                    page.click(".drp-trigger")
                    page.click("role=option[name=/Last 6 months/]")
                    page.wait_for_load_state("networkidle")
                page.wait_for_timeout(1200)
                page.screenshot(path=f"{args.out}/{name}_{theme}.png", full_page=True)
                print("saved", name, theme)
            ctx.close()
        # date-range picker: open with a range being picked, then a validation error
        ctx = browser.new_context(viewport={"width": args.width, "height": 900})
        ctx.add_init_script("localStorage.setItem('cloudlens.theme', 'dark')")
        page = ctx.new_page()
        page.goto(args.base + "/login")
        page.fill("#email", args.email)
        page.fill("#password", args.password)
        page.click("button[type=submit]")
        page.wait_for_url(args.base + "/")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(800)
        page.click(".drp-trigger")
        days = page.eval_on_selector_all(".drp-day:not(.off):not(.empty)", "els => els.map(e => e.dataset.date)")
        page.click(f"[data-date='{days[-27]}']")
        page.hover(f"[data-date='{days[-13]}']")
        page.wait_for_timeout(200)
        page.screenshot(path=f"{args.out}/11_date_range_picker_dark.png", clip={"x": 0, "y": 0, "width": args.width, "height": 720})
        page.fill("input[type=date] >> nth=1", "2099-01-01")
        page.wait_for_timeout(200)
        page.screenshot(path=f"{args.out}/12_date_range_validation_dark.png", clip={"x": 0, "y": 0, "width": args.width, "height": 720})
        ctx.close()
        # phone width check of the dashboard
        ctx = browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2)
        page = ctx.new_page()
        page.goto(args.base + "/login")
        page.fill("#email", args.email)
        page.fill("#password", args.password)
        page.click("button[type=submit]")
        page.wait_for_url(args.base + "/")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(1200)
        page.screenshot(path=f"{args.out}/10_dashboard_mobile.png", full_page=True)
        browser.close()
    if errors:
        print("CONSOLE ERRORS:")
        for e in errors:
            print(" ", e)
    return 0


if __name__ == "__main__":
    sys.exit(main())
