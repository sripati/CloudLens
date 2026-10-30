"""Build the project report (Word + PDF) with a static table of contents that has real page numbers.

Usage (from the repository root):  python docs/report/src/make_report.py
Needs: node + the `docx` npm package, LibreOffice (soffice), poppler (pdftotext), python-docx.
"""
import json
import os
import subprocess
import sys

from docx import Document

HERE = os.path.dirname(os.path.abspath(__file__))
REPORT = os.path.dirname(HERE)
DOCX = os.path.join(REPORT, "CloudLens_Project_Report.docx")
PDF = os.path.join(REPORT, "CloudLens_Project_Report.pdf")
TOC = os.path.join(HERE, "toc.json")
SOFFICE = os.environ.get("SOFFICE", "soffice")


def build():
    subprocess.run(["node", os.path.join(HERE, "build_report.js")], check=True)
    cmd = SOFFICE.split() + ["--headless", "--convert-to", "pdf", "--outdir", REPORT, DOCX]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def headings():
    out = []
    for p in Document(DOCX).paragraphs:
        style = p.style.name if p.style is not None else ""
        if style in ("Heading 1", "Heading 2") and p.text.strip() and p.text.strip() not in ("Table of Contents", "Abstract"):
            out.append({"title": p.text.strip(), "level": 1 if style == "Heading 1" else 2})
    return out


def pages_text():
    txt = subprocess.run(["pdftotext", "-layout", PDF, "-"], check=True, capture_output=True, text=True).stdout
    return txt.split("\f")


def locate(entries, pages):
    # skip cover and TOC pages: start searching after the page containing "Table of Contents"
    start = next(i for i, t in enumerate(pages) if "Table of Contents" in t) + 1
    while start < len(pages) and "1. Introduction" not in pages[start]:
        start += 1
    cursor = start
    for e in entries:
        key = " ".join(e["title"].split())
        for i in range(cursor, len(pages)):
            if key in " ".join(pages[i].split()):
                e["page"] = i  # pdf page index i (0-based) == footer number, since the cover is page 0
                cursor = i
                break
        else:
            e["page"] = "?"
    return entries


def main():
    # pass 1: placeholder TOC with the right number of lines
    with open(TOC, "w") as f:
        json.dump([], f)
    build()
    entries = [dict(e, page="00") for e in headings()]
    with open(TOC, "w") as f:
        json.dump(entries, f)
    build()  # pagination now includes a TOC of the final length
    entries = locate(entries, pages_text())
    with open(TOC, "w") as f:
        json.dump(entries, f, indent=1)
    build()
    missing = [e["title"] for e in entries if e["page"] == "?"]
    print("TOC entries:", len(entries), "missing:", missing)
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
