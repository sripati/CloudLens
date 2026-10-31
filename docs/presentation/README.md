# Viva presentation

The current viva deck (18 slides, with speaker notes) is `CloudLens DevOps Dashboard for Resource and Cost Monitoring.pptx`.
It adds slides 9 and 10 for Mock and Live modes, and updates the cost, testing and demo slides.

An earlier 16-slide version is a Claude Slides artifact and doesn't have these changes:
https://claude.ai/artifact/TRrgoWRe9TRkY47B4y3MuN

Replace the `[Student name] · [Roll no.] · [Institute]` placeholders on the first and last slides.

| # | Slide | Section |
|---|---|---|
| 1 | CloudLens (title) | Why |
| 2 | Problem statement | Why |
| 3 | Four goals, all delivered | Why |
| 4 | Architecture | How |
| 5 | Technology choices | How |
| 6 | One schema for every cloud | How |
| 7 | Real-time dashboard | What |
| 8 | Historical analysis: any period, validated (date-range picker) | What |
| 9 | Mock or Live, per cloud | What |
| 10 | Tested before it is trusted (connecting a real account) | What |
| 11 | Alerting pipeline | What |
| 12 | 8 rule types | What |
| 13 | Cost optimisation | What |
| 14 | Testing | Proof |
| 15 | Deployment | Proof |
| 16 | Live demo script | Proof |
| 17 | Learnings and future scope | Next |
| 18 | Thank you / Q&A (likely questions in the notes) | Next |

**The PDF is out of date:** it still shows the earlier 16 slides. To refresh it, open the `.pptx` in PowerPoint and export to PDF.

## Demo checklist (slide 16)

1. `docker compose up -d` at least 2 minutes before the viva.
2. Open tabs: dashboard `http://localhost:8080`, mock inbox `http://localhost:8080/mock-inbox/`,
   Prometheus alerts `http://localhost:9090/alerts`.
3. Cloud Accounts → *Clear spikes* so the demo starts clean.
4. Check the date button shows *Last 30 days* ending today (it follows the server date).
5. Run the seven steps; for step 4 open the date picker, pick *Last 6 months*, then type a future *To* date to show the validation message; for the alert, inject AWS ×2.5, 1 day ago, and wait about 90 seconds.
