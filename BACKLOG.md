# Circuit — Backlog

Work AFTER LAUNCH.md. Everything needed before the pilot lives in LAUNCH.md, not here.
Pull an item into a new numbered stage before building it; tick it when merged.

Priority: P1 = during pilot · P2 = after pilot · Later = only when data says so.

---

## P1 — during the pilot

### Lifestyle features (after F15–F17 ship)
- [ ] Short video in build logs (≤30s, server transcoding, moderation)
- [ ] Global search shortcut (Cmd/Ctrl+K) on desktop
- [ ] Group chats for circuits (the three members)
- [ ] Events: meetups and demo days with RSVPs in Pulse
- [ ] "Tune my Pulse": choose capabilities and topics that shape the feed

### Students and proof of work
- [ ] Searchable student profiles (opt-in) so founders can find students
- [ ] Students post offers (skills) and join circuits
- [ ] GitHub proof of work via OAuth: original repos, merged PRs, languages → capabilities; capped score weight; disconnect deletes data
- [ ] Non-code proof: portfolio, Behance/Dribbble, case studies
- [ ] "Project" job type for short paid gigs

### Data
- [ ] Production crawler as a Cloud Run Job: PageFetcher interface (own fetcher + optional Firecrawl), robots.txt, LLM extraction, dedupe, geocode, confidence score
- [ ] Review queue in Django admin; "Unclaimed · from public sources" label
- [ ] Public "Remove my startup" form + takedown queue
- [ ] Pilot city: ~150 verified startups; re-crawl every 2–4 weeks
- [ ] Startup claim outreach: 30–50 claimed with a real role

### SEO
- [ ] Public startup and job pages (statically generated on the landing site from public API endpoints), sitemap

### Matching
- [ ] v1.x tuning from real acceptance data (weights, bridge share, thresholds)
- [ ] Grow eval set to a few hundred labelled pairs from real outcomes
- [ ] Gap map export for partners (PDF/CSV)

### Revenue
- [ ] Promotions v2: custom budgets with pacing, simple targeting UI, automated GST invoices
- [ ] Partner subscriptions (colleges/incubators): free tier (org page, calls, events) + paid tier (full dashboard, cohort analytics, exports, multiple admins)
- [ ] Office hours booking (mentors and partners publish slots; members book)
- [ ] Demo day showcase pages that investors who opted in can browse

## P2 — after the pilot
- [ ] First real ModelRanker promotion: after ~300–500 labelled outcomes, shadow → A/B → active (pipeline built in LAUNCH Stage 4c)
- [ ] Mentor chains; peer circles; reputation score (PageRank over "helped" edges)
- [ ] Need decomposition (goal → sub-needs)
- [ ] Level 4 community vouching
- [ ] Regional language support
- [ ] Investor tier; corporate innovation needs; services marketplace and perks

## Later — only when measurements justify it
- [ ] Richer models (fine-tuned embeddings on our capability text, two-tower retrieval) after thousands of outcomes
- [ ] Bandit-learned bridge share per user; circuit scoring with predicted acceptance
- [ ] Neo4j behind core/graph. Trigger: warm-path or circuit queries > ~500ms p95, circuit round > 10 minutes, or multi-hop features SQL can't express cleanly
- [ ] Rust (PyO3) or Go for one hot path, only if profiling shows Python is the bottleneck
- [ ] Portable signed badges (W3C Verifiable Credentials); ecosystem reports
- [ ] Graph neural networks (tens of thousands of active users)

## Decided against (don't reopen without new evidence)
- Public like, follower and view counts; infinite feeds without an end; streaks (posts and Pulse ARE in scope, see F15)
- Scraping LinkedIn or any site that forbids it; proxy rotation / anti-bot evasion
- Storing user passwords (only Django staff admins, with 2FA)
- Success fees on fundraising; paying for placement in rankings
- Microservices / Kubernetes at pilot scale
- Neo4j for the pilot
- Another backend rewrite before the pilot
