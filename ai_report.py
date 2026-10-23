"""Ask Claude to analyse the league data and save the advice to data/ai.json.

Needs env var ANTHROPIC_API_KEY. Optional: CLAUDE_MODEL (default claude-sonnet-5-5).
If there's no key, it writes a placeholder so the site still builds.
"""
import json
import os
from pathlib import Path

import anthropic

DATA = Path(__file__).parent / "data"

LEAGUE_RULES = """
League: 8-team ESPN head-to-head POINTS league, 20 weekly matchups, top 4 make playoffs. Daily lineups.
Roster: 14 players. Starters: PG, SG, SF, PF, C, G, F, UTIL x3 (10 starters), 4 bench, 2 IR. Max 4 centres.
12 adds per matchup. Trade deadline 27 Feb 2027.
Scoring: FGM +2, FG missed -1, FTM +1, FT missed -1, 3PM +1, 3P missed -1, OREB +0.5, REB +1,
AST +2, STL +2.5, BLK +2.5, TO -2, PTS +1.
So efficient scorers, passers and stocks (steals/blocks) are worth more than usual; low-efficiency volume shooters are worth less.
Three managers in the league are inactive (Smoke Machiners, Larry birds allstars, Fade Away Aids) — don't suggest trading with them.
"""

SCHEMA_HINT = """Reply with ONLY a JSON object, no markdown, in exactly this shape:
{
  "headline": "one punchy sentence on where the team stands this week",
  "lineup": [{"slot": "PG", "player": "Name", "why": "short reason"}],   // 10 starters in slot order PG,SG,SF,PF,C,G,F,UTIL,UTIL,UTIL
  "bench": ["Name", ...],
  "trade_ideas": [{"partner": "Team name", "give": ["Name"], "get": ["Name"], "why": "1-2 sentences"}],  // 2-3 ideas, only active teams, realistic for both sides
  "waiver_adds": [{"add": "Name", "drop": "Name", "why": "short reason"}],  // 0-3, only if clearly better
  "matchup_outlook": "2-3 sentences on this week's matchup",
  "injury_watch": ["short note", ...]
}"""


def main():
    league = json.loads((DATA / "league.json").read_text())
    out = DATA / "ai.json"

    if not os.environ.get("ANTHROPIC_API_KEY"):
        out.write_text(json.dumps({"headline": "AI analysis is off — add an ANTHROPIC_API_KEY secret to turn it on."}))
        print("No API key, wrote placeholder")
        return

    # Keep the prompt lean: other teams' rosters without the noise
    slim = {
        "my_team": league["my_team"],
        "matchup": league["matchup"],
        "other_teams": [
            {"name": t["name"], "record": f'{t["wins"]}-{t["losses"]}',
             "roster": [f'{p["name"]} ({"/".join(p["eligible"])}, {p["avg_pts"]} avg, {p["injury"]})' for p in t["roster"]]}
            for t in league["teams"] if t["id"] != league["my_team"]["id"]
        ],
        "top_free_agents": league["free_agents"][:25],
        "recent_activity": league["activity"],
    }

    client = anthropic.Anthropic()
    msg = client.messages.create(
        model=os.environ.get("CLAUDE_MODEL", "claude-sonnet-5-5"),
        max_tokens=3000,
        system="You are a sharp fantasy basketball analyst. Be specific, use the scoring rules, and keep reasons short and casual.\n"
               + LEAGUE_RULES,
        messages=[{"role": "user", "content": f"My team is {league['my_team']['name']}. League data:\n"
                   + json.dumps(slim) + "\n\n" + SCHEMA_HINT}],
    )
    text = "".join(b.text for b in msg.content if b.type == "text").strip()
    text = text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        report = json.loads(text)
    except json.JSONDecodeError:
        report = {"headline": "AI replied in an unexpected format this run.", "raw": text}
    out.write_text(json.dumps(report, indent=2))
    print("Saved", out)


if __name__ == "__main__":
    main()
