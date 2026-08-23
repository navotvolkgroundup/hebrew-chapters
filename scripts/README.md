# sofit scripts

- `pool.py` — candidate-pool generator + spec builder (suggest → pick → build)
- `quotecards.py` — branded IG carousel quote-cards from episode pull-quotes
- `publish/` — semi-automated publish + measure pipeline:
  uploaders for TikTok / Instagram / YouTube Shorts (Playwright over a
  logged-in Chrome profile at ~/.ws-scraper/profile), a daily metrics
  scraper (retention curves, traffic sources, reach splits → the
  performance log at ~/.sofit/performance.jsonl), and a WhatsApp digest.

Account/brand specifics are machine-local, never in this repo:
`~/.sofit/publish.json` (profile, collaborators, dirs), `~/.sofit/plans/`
(publish plans), `~/.sofit/assets/` (brand kit), `~/.sofit/brand.json`.
