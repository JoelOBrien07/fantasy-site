# Scottier Barney's — fantasy dashboard

A site that rebuilds itself every 4 hours: it pulls your ESPN league, asks Claude for lineup / trade / waiver advice, and publishes to GitHub Pages.

```
fetch_data.py   ESPN API  -> data/league.json
ai_report.py    Claude    -> data/ai.json
build_site.py   both      -> site/index.html
.github/workflows/update.yml   runsss all three on a schedule and deploys
```

## Setup (~20 min)

1. **Make a GitHub repo** and push these files to it. Free GitHub Pages needs the repo to be **public**. That means the dashboard is public too, but your keys stay hidden in Secrets.

2. **Get your league ID.** Open your league on ESPN. It's the number after `leagueId=` in the URL.

3. **Get your ESPN cookies** (only needed if the league is private):
   on a laptop, log into espn.com, open DevTools (F12) → Application → Cookies → `https://www.espn.com`, and copy the values of `espn_s2` and `SWID` (keep the `{}` braces on SWID).

4. **Get a Claude API key** from console.anthropic.com → API Keys. It's billed per use. Each run is one request, so 6 runs a day is light, but check the pricing page. Skip this and the site still works, just without the AI parts.

5. **Add secrets** in the repo: Settings → Secrets and variables → Actions → *New repository secret*:
   - `LEAGUE_ID`
   - `ESPN_S2`
   - `SWID`
   - `ANTHROPIC_API_KEY`

   Optional: under the *Variables* tab, add `MY_TEAM` if your team name ever changes (default is `Scottier Barney's`).

6. **Turn on Pages:** Settings → Pages → Source: **GitHub Actions**.

7. **Run it:** Actions tab → *Update fantasy site* → *Run workflow*. When it's green, your site is at `https://<your-username>.github.io/<repo-name>/`.

## Run it locally

```bash
pip install -r requirements.txt
export LEAGUE_ID=... ESPN_S2=... SWID=... ANTHROPIC_API_KEY=...
python fetch_data.py && python ai_report.py && python build_site.py
open site/index.html
```

## Tweaks

- **How often:** change the `cron` line in `update.yml` (it's in UTC).
- **Model:** set a `CLAUDE_MODEL` env var in the AI step (default `claude-sonnet-5-5`).
- **What the AI knows:** league rules and scoring live in `LEAGUE_RULES` in `ai_report.py`. Update it if the settings change.
- **Season:** `SEASON` defaults to `2027` (ESPN numbers seasons by the year they end).

## Troubleshooting

- `Couldn't find team` — the error lists every team name; set `MY_TEAM` to yours exactly.
- 401 / "not authorized" — ESPN cookies expired or wrong; grab them again.
- Never commit the cookies or API key into the code — Secrets only.
