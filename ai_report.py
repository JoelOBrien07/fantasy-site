"""Get AI advice on the league data and save it to data/ai.json.

Providers (first key found wins):
  GEMINI_API_KEY     -> Google Gemini free tier (GEMINI_MODEL optional; auto-picks a Flash model if unset/unavailable)
  ANTHROPIC_API_KEY  -> Claude (CLAUDE_MODEL optional)
No key -> placeholder, site still builds.

The AI only runs every AI_EVERY_HOURS (default 4) to stay inside free limits; between runs the
previous report (downloaded from the live site by the workflow) is reused. FORCE_AI=true runs it anyway.
If the AI call fails, the previous report is kept.
"""
import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

DATA = Path(__file__).parent / "data"
GEMINI = "https://generativelanguage.googleapis.com/v1beta"

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


def build_prompt(league):
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
    system = ("You are a sharp fantasy basketball analyst. Be specific, use the scoring rules, "
              "and keep reasons short and casual.\n" + LEAGUE_RULES)
    user = (f"My team is {league['my_team']['name']}. League data:\n" + json.dumps(slim) + "\n\n" + SCHEMA_HINT)
    return system, user


def post_json(url, body, headers=None):
    req = urllib.request.Request(url, json.dumps(body).encode(), {"Content-Type": "application/json", **(headers or {})})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())


def gemini_models(key):
    """Usable Flash models, best first (newest non-lite, then lite), for fallback."""
    with urllib.request.urlopen(f"{GEMINI}/models?key={key}&pageSize=200", timeout=30) as r:
        models = [m["name"].removeprefix("models/") for m in json.loads(r.read()).get("models", [])
                  if "generateContent" in m.get("supportedGenerationMethods", [])]
    flash = [m for m in models if "flash" in m and not any(x in m for x in ("image", "tts", "live", "audio", "thinking"))]
    flash.sort(key=lambda m: ("preview" in m or "exp" in m, "lite" in m, "latest" in m,
                              [-int(x) for x in m.replace("-", ".").split(".") if x.isdigit()]))
    if not flash:
        raise RuntimeError(f"No Flash model available. Models: {models}")
    return flash


def ask_gemini(system, user):
    key = os.environ["GEMINI_API_KEY"]
    candidates = gemini_models(key)
    if os.environ.get("GEMINI_MODEL"):
        candidates = [os.environ["GEMINI_MODEL"]] + [m for m in candidates if m != os.environ["GEMINI_MODEL"]]
    body = {"systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {"responseMimeType": "application/json"}}
    last_err = None
    for model in candidates[:4]:
        for attempt, wait in enumerate((0, 10, 30)):
            time.sleep(wait)
            try:
                print(f"Gemini model: {model} (try {attempt + 1})")
                res = post_json(f"{GEMINI}/models/{model}:generateContent", body, {"x-goog-api-key": key})
                parts = res["candidates"][0]["content"]["parts"]
                return "".join(p.get("text", "") for p in parts if not p.get("thought"))
            except urllib.error.HTTPError as err:
                last_err = f"{err.code} {err.read().decode()[:300]}"
                print("  failed:", last_err)
                if err.code in (500, 503):
                    continue          # busy: wait and retry same model
                break                 # 429 quota / 404 etc: try the next model
            except (KeyError, IndexError) as err:
                last_err = f"empty response {err!r}"
                print("  failed:", last_err)
                break
    raise RuntimeError(f"All Gemini models failed. Last error: {last_err}")


def ask_claude(system, user):
    import anthropic
    msg = anthropic.Anthropic().messages.create(
        model=os.environ.get("CLAUDE_MODEL") or "claude-sonnet-5-5", max_tokens=3000,
        system=system, messages=[{"role": "user", "content": user}])
    return "".join(b.text for b in msg.content if b.type == "text")


def main():
    league = json.loads((DATA / "league.json").read_text())
    out = DATA / "ai.json"
    try:
        previous = json.loads(out.read_text())
    except (OSError, json.JSONDecodeError):
        previous = None

    if os.environ.get("GEMINI_API_KEY"):
        ask = ask_gemini
    elif os.environ.get("ANTHROPIC_API_KEY"):
        ask = ask_claude
    else:
        out.write_text(json.dumps({"headline": "AI analysis is off — add a GEMINI_API_KEY secret to turn it on."}))
        print("No AI key, wrote placeholder")
        return

    # Reuse the last report if it's recent enough (keeps us inside free-tier limits)
    every = float(os.environ.get("AI_EVERY_HOURS") or 4)
    if previous and previous.get("generated") and os.environ.get("FORCE_AI") != "true":
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(previous["generated"])).total_seconds() / 3600
        if age < every - 0.25:
            print(f"Last AI report is {age:.1f}h old, reusing it")
            return

    try:
        system, user = build_prompt(league)
        text = ask(system, user).strip()
        text = text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        report = json.loads(text)
        report["generated"] = datetime.now(timezone.utc).isoformat()
    except urllib.error.HTTPError as err:
        print("AI request failed:", err.code, err.read().decode()[:500])
        report = previous or {"headline": "AI is unavailable right now — it'll retry next run."}
    except Exception as err:
        print("AI step failed:", repr(err))
        report = previous or {"headline": "AI is unavailable right now — it'll retry next run."}

    out.write_text(json.dumps(report, indent=2))
    print("Saved", out)


if __name__ == "__main__":
    main()