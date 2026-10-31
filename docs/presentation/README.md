# Viva presentation

The viva deck (16 slides, with speaker notes) is a Claude Slides artifact:

**https://claude.ai/artifact/TRrgoWRe9TRkY47B4y3MuN**

Open it and use **Present** to present, or **Share → Export** to download it as PowerPoint (.pptx) or PDF.
The same deck is also saved here as `CloudLens DevOps Dashboard for Resource and Cost Monitoring.pptx`
(slides 7, 8, 12 and 14 updated for the date-range picker).
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
| 9 | Alerting pipeline | What |
| 10 | 8 rule types | What |
| 11 | Cost optimisation | What |
| 12 | Testing | Proof |
| 13 | Deployment | Proof |
| 14 | Live demo script | Proof |
| 15 | Learnings and future scope | Next |
| 16 | Thank you / Q&A (likely questions in the notes) | Next |

## Demo checklist (slide 14)

1. `docker compose up -d` at least 2 minutes before the viva.
2. Open tabs: dashboard `http://localhost:8080`, mock inbox `http://localhost:8080/mock-inbox/`,
   Prometheus alerts `http://localhost:9090/alerts`.
3. Cloud Accounts → *Clear spikes* so the demo starts clean.
4. Check the date button shows *Last 30 days* ending today (it follows the server date).
5. Run the six steps; for step 4 open the date picker, pick *Last 6 months*, then type a future *To* date to show the validation message; for the alert, inject AWS ×2.5, 1 day ago, and wait about 90 seconds.
