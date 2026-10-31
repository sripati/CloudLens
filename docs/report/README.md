# Project report

| File | Description |
|---|---|
| `CloudLens_Project_Report.docx` | Editable Word report (30 pages, including §6.4 Date range selection and validation): abstract, introduction, gap analysis, requirements, architecture, design, implementation, alerting, cost optimisation, testing, deployment, results with screenshots, conclusion, references, appendices |
| `CloudLens_Project_Report.pdf` | The same report as PDF, ready to submit |
| `img/` | Diagrams and cropped screenshots used in the report |
| `src/` | Generator: `build_report.js` (content), `make_report.py` (builds Word + PDF with page-numbered contents), `diagrams.html` (architecture and alert-flow diagrams) |

**Before submitting:** fill in the cover page placeholders `[Student Name]`, `[Number]`, `[Programme name]`,
`[Institute name]` and `[Mentor name]` (in Word, or in `src/build_report.js` before regenerating).

To regenerate after editing the content (needs Node with the `docx` package, LibreOffice, poppler-utils and python-docx):

```bash
npm install -g docx          # once
python docs/report/src/make_report.py
```
