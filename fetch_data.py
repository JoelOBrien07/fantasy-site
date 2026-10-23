"""Pull league data from ESPN and save it to data/league.json.

Needs env vars: LEAGUE_ID, and for private leagues ESPN_S2 + SWID.
Optional: SEASON (default 2027 = the 2026-27 season), MY_TEAM (team name, default "Scottier Barney's").
"""
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from espn_api.basketball import League

OUT = Path(__file__).parent / "data" / "league.json"


def player_dict(p, team_name=None):
    return {
        "name": p.name,
        "pro_team": p.proTeam,
        "position": p.position,
        "eligible": [s for s in p.eligibleSlots if s not in ("BE", "IR", "UT", "Rookie")],
        "slot": p.lineupSlot,
        "injury": p.injuryStatus or "ACTIVE",
        "avg_pts": round(p.avg_points or 0, 1),
        "total_pts": round(p.total_points or 0, 1),
        "proj_avg": round(p.projected_avg_points or 0, 1),
        "fantasy_team": team_name,
    }


def main():
    league = League(
        league_id=int(os.environ["LEAGUE_ID"]),
        year=int(os.environ.get("SEASON", "2027")),
        espn_s2=os.environ.get("ESPN_S2") or None,
        swid=os.environ.get("SWID") or None,
    )
    my_name = (os.environ.get("MY_TEAM") or "Scottier Barney's").strip().lower()

    teams = []
    my_team = None
    for t in league.teams:
        td = {
            "id": t.team_id,
            "name": t.team_name,
            "wins": t.wins,
            "losses": t.losses,
            "points_for": round(t.points_for, 1),
            "points_against": round(t.points_against, 1),
            "standing": t.standing,
            "roster": [player_dict(p, t.team_name) for p in t.roster],
        }
        teams.append(td)
        if t.team_name.strip().lower() == my_name:
            my_team = td
    if my_team is None:
        raise SystemExit(f"Couldn't find team '{my_name}'. Teams: {[t['name'] for t in teams]}")

    matchup = None
    for m in league.scoreboard():
        home, away = m.home_team, m.away_team
        if not hasattr(home, "team_name") or not hasattr(away, "team_name"):
            continue
        if my_team["id"] in (home.team_id, away.team_id):
            me_home = home.team_id == my_team["id"]
            opp = away if me_home else home
            matchup = {
                "week": league.currentMatchupPeriod,
                "opponent": opp.team_name,
                "my_score": round((m.home_team_live_score if me_home else m.away_team_live_score)
                                  or (m.home_final_score if me_home else m.away_final_score) or 0, 1),
                "opp_score": round((m.away_team_live_score if me_home else m.home_team_live_score)
                                   or (m.away_final_score if me_home else m.home_final_score) or 0, 1),
            }

    free_agents = [player_dict(p) for p in league.free_agents(size=40)]

    activity = []
    try:
        for a in league.recent_activity(size=15):
            for team, action, player, *_ in a.actions:
                activity.append({
                    "date": datetime.fromtimestamp(a.date / 1000).strftime("%d %b"),
                    "team": getattr(team, "team_name", str(team)),
                    "action": action,
                    "player": getattr(player, "name", str(player)),
                })
    except Exception as e:  # activity needs auth on private leagues; not essential
        print("Skipping activity:", e)

    data = {
        "updated": datetime.now(timezone.utc).isoformat(),
        "league_name": league.settings.name,
        "my_team": my_team,
        "matchup": matchup,
        "teams": sorted(teams, key=lambda t: t["standing"]),
        "free_agents": free_agents,
        "activity": activity,
    }
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(data, indent=2))
    print(f"Saved {OUT} — {len(my_team['roster'])} players on {my_team['name']}")


if __name__ == "__main__":
    main()
