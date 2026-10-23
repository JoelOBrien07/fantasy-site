"""Turn data/league.json + data/ai.json into site/index.html."""
import json
from datetime import datetime
from html import escape as e
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).parent
DATA, SITE = ROOT / "data", ROOT / "site"

INJ = {"ACTIVE": "", "OUT": "out", "DAY_TO_DAY": "dtd", "QUESTIONABLE": "dtd",
       "INJURY_RESERVE": "out", "SUSPENSION": "out"}


def badge(status):
    cls = INJ.get(status, "dtd")
    return f'<span class="badge {cls}">{e(status.replace("_", " ").title())}</span>' if cls else ""


def card(title, body, order=0):
    return f'<section class="card" style="order:{order}"><h2>{e(title)}</h2>{body}</section>' if body else ""


def build():
    lg = json.loads((DATA / "league.json").read_text())
    ai_path = DATA / "ai.json"
    ai = json.loads(ai_path.read_text()) if ai_path.exists() else {}
    me = lg["my_team"]
    updated = datetime.fromisoformat(lg["updated"]).astimezone(ZoneInfo("Australia/Melbourne"))

    top, left, right = [], [], []  # desktop columns; phone order comes from `order`

    m = lg.get("matchup")
    if m:
        lead = m["my_score"] - m["opp_score"]
        top.append(f'''<section class="card matchup" style="order:1">
          <div class="mlabel">Week {m["week"]} matchup</div>
          <div class="score"><div><span>{e(me["name"])}</span><b>{m["my_score"]}</b></div>
          <div class="vs">vs</div><div><span>{e(m["opponent"])}</span><b>{m["opp_score"]}</b></div></div>
          <div class="lead {'up' if lead >= 0 else 'down'}">{'+' if lead >= 0 else ''}{lead:.1f}</div>
          {f'<p>{e(ai["matchup_outlook"])}</p>' if ai.get("matchup_outlook") else ""}
        </section>''')

    if ai.get("headline"):
        top.append(f'<section class="card ai" style="order:2"><div class="tag">AI take</div><p class="headline">{e(ai["headline"])}</p></section>')

    if ai.get("lineup"):
        rows = "".join(f'<tr><td class="slot">{e(r["slot"])}</td><td><b>{e(r["player"])}</b><small>{e(r.get("why", ""))}</small></td></tr>'
                       for r in ai["lineup"])
        bench = ", ".join(e(b) for b in ai.get("bench", []))
        left.append(card("Best lineup", f'<table class="lineup">{rows}</table>' + (f'<p class="muted">Bench: {bench}</p>' if bench else ""), 3))

    if ai.get("trade_ideas"):
        body = "".join(f'''<div class="trade"><div class="partner">with {e(t["partner"])}</div>
            <div class="swap"><div><small>Give</small>{"<br>".join(e(x) for x in t["give"])}</div><div class="arrow">⇄</div>
            <div><small>Get</small>{"<br>".join(e(x) for x in t["get"])}</div></div><p>{e(t["why"])}</p></div>''' for t in ai["trade_ideas"])
        right.append(card("Trade ideas", body, 4))

    if ai.get("waiver_adds"):
        body = "".join(f'<div class="wa"><b class="add">+ {e(w["add"])}</b> <b class="drop">− {e(w["drop"])}</b><p>{e(w["why"])}</p></div>'
                       for w in ai["waiver_adds"])
        right.append(card("Waiver moves", body, 5))

    if ai.get("injury_watch"):
        right.append(card("Injury watch", "<ul>" + "".join(f"<li>{e(x)}</li>" for x in ai["injury_watch"]) + "</ul>", 6))

    roster = sorted(me["roster"], key=lambda p: (p["slot"] == "IR", -(p["avg_pts"] or p["proj_avg"])))
    rows = "".join(f'<tr><td><b>{e(p["name"])}</b>{badge(p["injury"])}<small>{e(p["pro_team"])} · {e("/".join(p["eligible"][:3]))}</small></td>'
                   f'<td class="wide muted">{e(p["slot"])}</td><td class="num wide">{p["total_pts"]}</td>'
                   f'<td class="num">{p["avg_pts"]}</td><td class="num muted">{p["proj_avg"]}</td></tr>' for p in roster)
    left.append(card("Roster", '<table><tr><th></th><th class="wide">Slot</th><th class="num wide">Total</th>'
                     f'<th class="num">Avg</th><th class="num">Proj</th></tr>{rows}</table>', 7))

    rows = "".join(f'<tr class="{"me" if t["id"] == me["id"] else ""}"><td>{t["standing"]}</td><td>{e(t["name"])}</td>'
                   f'<td class="num">{t["wins"]}-{t["losses"]}</td><td class="num muted">{t["points_for"]}</td></tr>' for t in lg["teams"])
    right.append(card("Standings", f'<table><tr><th>#</th><th>Team</th><th class="num">W-L</th><th class="num">PF</th></tr>{rows}</table>', 8))

    fa = sorted(lg["free_agents"], key=lambda p: -p["avg_pts"])[:10]
    rows = "".join(f'<tr><td><b>{e(p["name"])}</b>{badge(p["injury"])}<small>{e(p["pro_team"])} · {e("/".join(p["eligible"][:3]))}</small></td>'
                   f'<td class="num">{p["avg_pts"]}</td></tr>' for p in fa)
    right.append(card("Best free agents", f'<table>{rows}</table>', 9))

    if lg.get("activity"):
        right.append(card("League activity", "<ul class='act'>" + "".join(
            f'<li><span class="muted">{e(a["date"])}</span> {e(a["team"])} — {e(a["action"].lower())} {e(a["player"])}</li>'
            for a in lg["activity"][:12]) + "</ul>", 10))

    html = f'''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{e(me["name"])}</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@600;700&family=Inter:wght@400;600&display=swap" rel="stylesheet">
<style>{CSS}</style></head><body>
<header><div><div class="league">{e(lg["league_name"])}</div><h1>{e(me["name"])}</h1></div>
<div class="meta"><div class="rec">{me["wins"]}-{me["losses"]} · #{me["standing"]} · {me["points_for"]} PF</div>
<div class="upd">Updated {updated.strftime("%a %d %b, %-I:%M%p")}</div></div></header>
<main><div class="top">{"".join(top)}</div><div class="col">{"".join(left)}</div><div class="col">{"".join(right)}</div></main><footer>Data from ESPN · analysis by Claude</footer></body></html>'''
    SITE.mkdir(exist_ok=True)
    (SITE / "index.html").write_text(html)
    (SITE / "ai.json").write_text(json.dumps(ai))  # next run reuses this instead of calling the AI again
    print("Built", SITE / "index.html")


CSS = """
:root{--bg:#0d1014;--card:#161b22;--line:#252c36;--text:#e8edf2;--muted:#8b96a5;--accent:#ff7a1a;--up:#3ddc84;--down:#ff5d5d;--warn:#f5b83d}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--text);font:15px/1.45 Inter,system-ui,sans-serif;padding:0 16px 40px;max-width:640px;margin:auto}
header{padding:28px 0 18px}
h1,h2,.score b,.lead{font-family:'Barlow Condensed',sans-serif;letter-spacing:.02em}
h1{font-size:40px;line-height:1;text-transform:uppercase}
.league{color:var(--accent);font-size:12px;text-transform:uppercase;letter-spacing:.12em;font-weight:600}
.rec{font-size:17px;margin-top:6px}.upd,.muted,small{color:var(--muted)}.upd{font-size:12px;margin-top:4px}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px}
h2{font-size:20px;text-transform:uppercase;margin-bottom:10px}
table{width:100%;border-collapse:collapse}td,th{padding:8px 4px;border-top:1px solid var(--line);vertical-align:top;text-align:left}
tr:first-child td,tr:first-child th{border-top:0}th{font-size:12px;color:var(--muted);font-weight:600}
.num{text-align:right;white-space:nowrap}small{display:block;font-size:12px}
.slot{width:52px;color:var(--accent);font-weight:600}
.badge{font-size:10px;font-weight:600;padding:2px 6px;border-radius:6px;margin-left:6px;text-transform:uppercase}
.badge.out{background:#ff5d5d22;color:var(--down)}.badge.dtd{background:#f5b83d22;color:var(--warn)}
tr.me td{color:var(--accent);font-weight:600}
.matchup{text-align:center}.mlabel{font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:.1em}
.score{display:flex;justify-content:space-around;align-items:center;margin:8px 0}.score span{display:block;font-size:13px;color:var(--muted)}
.score b{font-size:44px}.vs{color:var(--muted)}.lead{font-size:22px}.lead.up{color:var(--up)}.lead.down{color:var(--down)}
.matchup p{margin-top:10px;text-align:left}
.ai{border-color:var(--accent)}.tag{color:var(--accent);font-size:12px;font-weight:600;text-transform:uppercase;letter-spacing:.1em}
.headline{font-size:18px;font-weight:600;margin-top:4px}
.trade{border-top:1px solid var(--line);padding:12px 0}.trade:first-of-type{border-top:0;padding-top:0}
.partner{font-size:12px;color:var(--muted);text-transform:uppercase}.swap{display:flex;gap:10px;align-items:center;margin:6px 0;font-weight:600}
.swap>div:not(.arrow){flex:1}.arrow{color:var(--accent);font-size:20px}
.wa{padding:8px 0;border-top:1px solid var(--line)}.wa:first-of-type{border-top:0}.add{color:var(--up)}.drop{color:var(--down);margin-left:8px}
ul{padding-left:18px}li{margin:4px 0}.act{list-style:none;padding:0;font-size:14px}
footer{text-align:center;color:var(--muted);font-size:12px;margin-top:20px}
/* phone: one column, cards in `order` sequence */
main{display:flex;flex-direction:column;gap:14px}
main>div{display:contents}
.wide{display:none}
/* desktop: header bar, top row of two, then two columns */
@media (min-width:900px){
  body{max-width:1240px;padding:0 32px 48px;font-size:15px}
  header{display:flex;justify-content:space-between;align-items:flex-end;padding:40px 0 24px;border-bottom:1px solid var(--line);margin-bottom:24px}
  h1{font-size:60px}.meta{text-align:right}.rec{font-size:20px}
  main{display:grid;grid-template-columns:1.15fr 1fr;gap:20px;align-items:start}
  main>div{display:flex;flex-direction:column;gap:20px}
  .top{grid-column:1/-1;display:grid !important;grid-template-columns:1.15fr 1fr;gap:20px;align-items:stretch}
  .top>.card:only-child{grid-column:1/-1}
  .score b{font-size:56px}.headline{font-size:22px}
  .wide{display:table-cell}
  .card{padding:20px 22px}
}
"""

if __name__ == "__main__":
    build()
