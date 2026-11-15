"""Static results site in the format of chessbench.ai (Skyline / Leaderboard / Games views),
generated from the database. Ranking is plain round-robin results: games won (ties broken by
fewer losses, then crown difference). No rating model.

    uv run python -m cr_arena.site                 # writes runs/site/index.html
    uv run python -m cr_arena.site --classic classic-v2 --build build-v2
"""

from __future__ import annotations

import argparse
import base64
import json
import re
import time
import tomllib
from collections import defaultdict
from pathlib import Path

from .db import DB

OUT = Path("runs/site/index.html")
LOGOS = {
    "claude": ("Anthropic", "anthropic"), "gpt": ("OpenAI", "openai"),
    "gemini": ("Google", "google-color"), "grok": ("xAI", "xai"),
    "deepseek": ("DeepSeek", "deepseek-color"), "mistral": ("Mistral AI", "mistral-color"),
    "llama": ("Meta", "meta-color"), "qwen": ("Qwen", "qwen-color"),
    "inkling": ("Thinking Machines", "thinking-machines"),
    "kimi": ("Kimi", "kimi-color"),
}


def result_runs(db: DB) -> list[dict]:
    """Describe competition format separately from the deck rules actually used."""
    matches = defaultdict(list)
    for match in db.query("SELECT job_id, blue, red, deck, status FROM matches"):
        matches[match["job_id"]].append(match)
    runs = []
    for job in db.query("SELECT * FROM jobs ORDER BY created_at DESC"):
        if job["name"] == "human-play":
            continue
        rows = matches[job["id"]]
        players = set(json.loads(job.get("players") or "[]"))
        players.update(p for row in rows for p in (row["blue"], row["red"]) if p)
        scored = [row for row in rows if row["status"] == "done"]
        modes = set()
        for row in scored or rows:
            deck = json.loads(row["deck"]) if row.get("deck") else None
            if isinstance(deck, dict):
                modes.add("built")
            elif isinstance(deck, list):
                modes.add("preset")
        deck_rules = ("Model-built decks" if modes == {"built"} else "Preset decks" if modes == {"preset"}
                      else "Mixed deck rules" if modes else "Deck rules pending")
        runs.append({**job, "format": "duel" if len(players) == 2 else "round_robin",
                     "player_count": len(players), "deck_rules": deck_rules, "scored_games": len(scored)})
    return runs


def _family(name: str, llm: bool) -> str:
    if not llm:
        return "bot"
    name = name.lower()
    aliases = {"claude": r"claude|anthropic", "gpt": r"gpt|chatgpt|openai|o[134](?:\b|[-_])",
               "gemini": r"gemini|google", "grok": r"grok|xai", "deepseek": r"deepseek",
               "mistral": r"mistral|mixtral|codestral|magistral", "llama": r"llama|meta", "qwen": r"qwen|qwq",
               "inkling": r"inkling|thinking[-_ ]?machines", "kimi": r"kimi|moonshot(?:ai)?"}
    # OpenAI-compatible endpoints can serve other model families.
    for candidate in (name.rsplit("/", 1)[-1], name):
        for family, pattern in aliases.items():
            if re.search(r"(?:^|[/\s_-])(?:" + pattern + r")", candidate):
                return family
    return "other"


def _llm_names(jobs: list[dict]) -> set[str]:
    out = set()
    for j in jobs:
        try:
            for p in tomllib.loads(j["config_toml"] or "").get("players", []):
                if p.get("type", "llm") in ("llm", "mock"):
                    out.add(p["name"])
        except Exception:
            pass
    return out


def track_data(db: DB, jobs: list[dict]) -> dict:
    ids = [j["id"] for j in jobs]
    if not ids:
        return {"players": [], "games": [], "jobs": []}
    ph = ",".join("?" * len(ids))
    matches = db.query(f"SELECT * FROM matches WHERE status = 'done' AND job_id IN ({ph}) ORDER BY finished_at DESC", tuple(ids))
    dec = {r["player"]: r for r in db.query(
        f"""SELECT player, SUM(asked) AS asked, SUM(CASE WHEN asked = 1 AND ok = 1 THEN 1 ELSE 0 END) AS good,
                   AVG(CASE WHEN asked = 1 THEN latency_s END) AS latency, SUM(COALESCE(cost_usd, 0)) AS cost,
                   COUNT(*) AS decisions
            FROM decisions d WHERE job_id IN ({ph}) AND EXISTS (SELECT 1 FROM matches m WHERE m.job_id = d.job_id
                 AND m.match_id = d.match_id AND m.status = 'done') GROUP BY player""", tuple(ids))}
    llm = _llm_names(jobs)
    jobname = {j["id"]: j["name"] for j in jobs}
    P = defaultdict(lambda: {"games": 0, "W": 0, "L": 0, "D": 0, "cf": 0, "ca": 0, "three": 0, "build_n": 0,
                             "build_ok": 0, "build_cost": 0.0, "blue": [0, 0, 0], "red": [0, 0, 0]})
    games = []
    for m in matches:
        crowns = json.loads(m["crowns"]) if m["crowns"] else [0, 0]
        w = m["winner"]
        for team, name in ((0, m["blue"]), (1, m["red"])):
            p = P[name]
            p["games"] += 1
            p["cf"] += crowns[team]
            p["ca"] += crowns[1 - team]
            side = "blue" if team == 0 else "red"
            if w == 2:
                p["D"] += 1
                p[side][2] += 1
            elif w == team:
                p["W"] += 1
                p[side][0] += 1
                p["three"] += int(crowns[team] >= 3)
            else:
                p["L"] += 1
                p[side][1] += 1
            st = json.loads(m["stats_blue" if team == 0 else "stats_red"] or "{}")
            b = st.get("deck_build")
            if b:
                p["build_n"] += 1
                p["build_ok"] += int(bool(b.get("ok")))
                p["build_cost"] += (b.get("usage") or {}).get("cost", 0.0)
        deck = json.loads(m["deck"]) if m["deck"] else None
        parts = m["match_id"].split("__")
        games.append({
            "id": m["match_id"], "job": jobname[m["job_id"]], "blue": m["blue"], "red": m["red"], "winner": w,
            "crowns": crowns, "ticks": m["ticks"], "deck_name": parts[-1] if len(parts) >= 5 else None,
            "deck": deck, "t": m["finished_at"], "replay": bool(m["replay_path"]),
        })
    players = []
    for name, p in P.items():
        d = dec.get(name, {})
        is_llm = name in llm
        g = p["games"]
        cost = ((d.get("cost") or 0.0) + p["build_cost"]) if is_llm else None
        players.append({
            "name": name, "family": _family(name, is_llm), "llm": is_llm, "games": g, "W": p["W"], "L": p["L"], "D": p["D"],
            "win_rate": p["W"] / g if g else 0.0, "crowns": p["cf"] / g if g else 0.0, "conceded": p["ca"] / g if g else 0.0,
            "crown_diff": p["cf"] - p["ca"], "three_crowns": p["three"],
            "reliability": (d["good"] / d["asked"]) if (is_llm and d.get("asked")) else None,
            "think_s": d.get("latency") if is_llm else None,
            "cost_per_game": (cost / g) if (cost is not None and g) else None,
            "deck_valid": (p["build_ok"] / p["build_n"]) if (is_llm and p["build_n"]) else None,
            "decisions": d.get("decisions", 0), "as_blue": p["blue"], "as_red": p["red"],
        })
    players.sort(key=lambda r: (-r["W"], r["L"], -r["crown_diff"], r["name"]))
    for i, r in enumerate(players, 1):
        r["rank"] = i
    return {"players": players, "games": games, "jobs": [j["name"] for j in jobs],
            "running": [j["name"] for j in jobs if j["status"] == "running"]}


def build(db: DB, classic: str = "classic-v2", build_job: str = "build-v2", out: Path = OUT,
          dashboard_url: str = "http://localhost:8000", *, embedded: bool = False, theme: str = "light",
          job_name: str | None = None) -> Path:
    jobs = {j["name"]: j for j in db.query("SELECT * FROM jobs")}
    tracks = {}
    sel = [jobs[n] for n in dict.fromkeys((classic, build_job)) if n in jobs]
    if job_name is not None:
        run = next((run for run in result_runs(db) if run["name"] == job_name), None)
        sel = [jobs[job_name]] if run else []
        if run:
            track = track_data(db, sel)
            track.update(format=run["format"], deck_rules=run["deck_rules"], name=run["name"])
            tracks["Selected run"] = track
    else:
        for run in result_runs(db):
            if run["name"] in {job["name"] for job in sel}:
                track = track_data(db, [jobs[run["name"]]])
                track.update(format=run["format"], deck_rules=run["deck_rules"], name=run["name"])
                tracks[run["name"]] = track
    updated = max((j.get("finished_at") or j.get("started_at") or j["created_at"] for j in sel), default=time.time())
    date = time.localtime(updated)
    updated_label = f"{time.strftime('%B', date)} {date.tm_mday}, {date.tm_year}"
    data = {"tracks": tracks, "updated": updated_label, "dashboard": dashboard_url}
    out.parent.mkdir(parents=True, exist_ok=True)
    logos = {family: {"name": provider, "src": "data:image/svg+xml;base64," + base64.b64encode(
        (Path(__file__).parent / "assets" / "logos" / f"{asset}.svg").read_bytes()).decode("ascii")}
        for family, (provider, asset) in LOGOS.items()}
    html = TEMPLATE.replace("/*DATA*/null", json.dumps(data)).replace("/*LOGOS*/{}", json.dumps(logos))
    if theme == "dark":
        html = html.replace("</head>", """<style>
        :root{color-scheme:dark;--text-1:#e9e8e3;--text-2:#b1b2ab;--text-3:#969891;--border:#393a35;--bg:#171716;--surface:#222220;
        --f-claude:#dc9b7d;--f-gpt:#6ec9a8;--f-gemini:#88acf1;--f-grok:#c5c5ce;--f-deepseek:#ab95ed;--f-bot:#969891;--f-other:#b5b5be}
        th.sorted,td.sortedc{background:#2b2c27}.sky .axis{background:var(--border)}
        .provider-logo{background:white;border-radius:6px;padding:3px;width:24px;height:24px;flex-basis:24px}
        .model-options button{color:var(--text-1)}
        </style></head>""")
    if embedded:
        html = html.replace("</head>", "<style>header{padding:0 16px}header h1,header .tag{display:none}nav.icons{margin-top:12px}main{padding-bottom:40px}footer{padding-bottom:20px}</style></head>")
    out.write_text(html, encoding="utf-8")
    return out


TEMPLATE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>RoyaleBench</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Geist:wght@400;500;600&family=Plus+Jakarta+Sans:wght@400;500;600&display=swap" rel="stylesheet">
<style>
:root{--text-1:#4a4d55;--text-2:#6f7279;--text-3:#8a8d93;--border:#e2e0db;--bg:#f4f3f0;--surface:#faf9f7;
--f-claude:#b5613e;--f-gpt:#2b8a6a;--f-gemini:#3b6dc2;--f-grok:#55555e;--f-deepseek:#6b4fbf;--f-bot:#9a9ca1;--f-other:#55555e;
--f-mistral:#df7834;--f-llama:#3676b7;--f-qwen:#6151bc;--f-inkling:#343a40;--f-kimi:#1783ff;
--display:"Plus Jakarta Sans",ui-sans-serif,system-ui,sans-serif;--body:"Geist",ui-sans-serif,system-ui,sans-serif}
*{box-sizing:border-box}html,body{margin:0}body{background:var(--bg);color:var(--text-1);font-family:var(--body);font-size:16px}
a{color:inherit}
header{text-align:center;padding:48px 16px 0}
h1{font-family:var(--display);font-size:24px;font-weight:600;letter-spacing:-.6px;margin:0}
h1 .lite{font-weight:400}
.tag{color:var(--text-2);font-size:14px;margin-top:10px}
nav.icons{display:flex;justify-content:center;gap:34px;margin-top:40px}
nav.icons button{background:none;border:0;padding:6px 6px 10px;cursor:pointer;color:var(--text-3);border-bottom:1.5px solid transparent}
nav.icons button[aria-selected=true]{color:var(--text-1);border-bottom-color:var(--text-3)}
nav.icons svg{display:block;width:19px;height:19px}
nav.icons button{display:flex;align-items:center;gap:8px;font:inherit;font-size:13px}
.results-tools{display:flex;align-items:center;justify-content:space-between;gap:20px;flex-wrap:wrap;margin-top:26px}
.results-tools .search{margin-top:0}
.details-toggle{border:1px solid var(--border);border-radius:6px;background:var(--surface);color:var(--text-2);font:inherit;font-size:12px;padding:8px 12px;cursor:pointer}
.methodology{margin-top:20px;color:var(--text-3);font-size:12px;line-height:1.7}
.methodology summary{cursor:pointer;color:var(--text-2)}
.empty-state{text-align:center;padding:48px 16px;color:var(--text-3)}
.subtabs{display:flex;justify-content:center;gap:30px;margin:44px 0 0;flex-wrap:wrap}
.subtabs button{background:none;border:0;font:inherit;font-size:14px;color:var(--text-3);cursor:pointer;padding:0 0 6px;border-bottom:1.5px solid transparent}
.subtabs button[aria-selected=true]{color:var(--text-1);font-weight:600;border-bottom-color:var(--text-3)}
.subtabs.small{margin-top:18px;gap:22px}.subtabs.small button{font-size:13px}
main{max-width:1320px;margin:0 auto;padding:0 16px 80px;min-height:60vh}
.note{text-align:center;color:var(--text-3);font-size:12px;margin-top:14px}
/* skyline */
.sky{position:relative;margin:40px auto 0;width:100%;max-width:520px}
.sky .axis{position:absolute;left:50%;top:0;bottom:0;width:2px;margin-left:-1px;background:linear-gradient(var(--border),#d9d7d1 10%,#d9d7d1 90%,var(--border))}
.sky .pt{position:absolute;left:0;right:0;display:flex;align-items:center;height:22px;margin-top:-11px}
.sky .val{width:50%;text-align:right;padding-right:16px;font-weight:600;font-size:14px;font-variant-numeric:tabular-nums;color:var(--text-1)}
.sky .dot{position:absolute;left:50%;width:13px;height:13px;margin-left:-6.5px;border-radius:50%}
.sky .nm{width:50%;padding-left:16px;font-size:14px}
/* leaderboard */
.lbwrap{overflow-x:auto;margin-top:26px}
table{border-collapse:collapse;width:100%;font-size:13px}
th{font-size:11px;font-weight:500;color:var(--text-3);letter-spacing:.88px;text-transform:uppercase;padding:10px 10px;border-bottom:1px solid var(--border);white-space:nowrap;cursor:pointer;user-select:none}
th.sorted{color:var(--text-1);background:#efeee9}
td{padding:10px 10px;border-bottom:1px solid var(--border);white-space:nowrap;font-variant-numeric:tabular-nums;color:var(--text-1)}
td.rk{color:var(--text-3);text-align:right}
td.num,th.num{text-align:right}
td.sortedc{background:#efeee9}
.model-label{display:inline-flex;align-items:center;gap:8px;vertical-align:middle;white-space:nowrap}
.provider-logo{display:block;width:20px;height:20px;object-fit:contain;flex:0 0 20px}
.cell{display:inline-flex;align-items:center;gap:8px}.cell .v{min-width:44px;text-align:right}
.bar{position:relative;display:block;width:64px;height:8px;border-radius:4px;background:var(--border);overflow:hidden}
.bar span{display:block;height:100%}
.na{color:var(--text-3)}
.search{display:flex;justify-content:center;margin-top:26px}
.search input{border:0;border-bottom:1px solid var(--border);background:transparent;font:inherit;font-size:14px;padding:8px 4px 8px 26px;width:250px;color:var(--text-1);outline:none;
background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='16' height='16' fill='none' stroke='%233b6dc2' stroke-width='2'%3E%3Ccircle cx='7' cy='7' r='5'/%3E%3Cpath d='M11 11l4 4'/%3E%3C/svg%3E");background-repeat:no-repeat;background-position:2px center}
.caption{color:var(--text-3);font-size:12px;margin-top:10px}
/* games */
.select{display:flex;justify-content:center;margin-top:40px}
.model-picker{position:relative;min-width:min(340px,100%);max-width:100%}
.model-picker summary{list-style:none;cursor:pointer;text-align:center;border-bottom:1px solid var(--border);padding:6px 36px 10px;font-size:20px}
.model-picker summary::-webkit-details-marker{display:none}
.model-picker summary::after{content:'⌄';position:absolute;right:10px;color:var(--text-3)}
.model-options{position:absolute;top:100%;left:0;right:0;z-index:5;max-height:320px;overflow:auto;background:var(--surface);border:1px solid var(--border);border-radius:4px;box-shadow:0 8px 24px #0001;padding:4px}
.model-options button{display:block;width:100%;text-align:left;border:0;background:transparent;font:inherit;color:inherit;padding:10px;cursor:pointer}
.model-options button:hover,.model-options button[aria-pressed=true]{background:var(--border)}
.model-options button:focus-visible,.model-picker summary:focus-visible{outline:2px solid var(--f-gemini);outline-offset:2px}
.stats{display:flex;justify-content:center;gap:52px;margin-top:56px;text-align:center}
.stats b{display:block;font-size:30px;font-weight:500;color:var(--text-1)}
.stats span{display:block;font-size:13px;letter-spacing:1.3px;color:var(--text-3);margin-top:10px;text-transform:uppercase}
.sides{max-width:722px;margin:46px auto 0}
.sides h4{font-size:13px;font-weight:500;letter-spacing:1.3px;color:var(--text-3);margin:28px 0 10px;text-transform:uppercase}
.stack{display:flex;height:9px;border-radius:2px;overflow:hidden;gap:1px;background:var(--bg)}
.stack span{display:block;height:100%}
.sides p{font-size:14px;color:var(--text-2);margin:10px 0 0}
h3{font-weight:400;font-size:20px;text-align:center;margin:70px 0 22px;color:var(--text-1)}
.card{background:var(--surface);border:1px solid var(--border);border-radius:4px;padding:18px 22px}
.card table td{font-size:13px}
.w{color:var(--f-gpt)}.l{color:#b5613e}
footer{border-top:1px solid var(--border);text-align:center;padding:36px 16px 40px;font-size:14px;color:var(--text-2)}
footer .links a{text-decoration:none;color:var(--text-1)}footer .sep{color:#c9c7c1;margin:0 8px}
footer p{color:var(--text-3);margin:18px 0 0}
.about{max-width:720px;margin:40px auto 0;line-height:1.6;font-size:15px;color:var(--text-1)}
.about h4{font-family:var(--display);font-weight:600;font-size:16px;margin:28px 0 6px}
.about code{font-size:13px;background:var(--surface);border:1px solid var(--border);border-radius:3px;padding:0 4px}
</style></head>
<body>
<header>
  <h1><a href="#" onclick="go('leaderboard');return false" style="text-decoration:none"><span>Royale</span><span class="lite">Bench</span></a></h1>
  <div class="tag">A Clash Royale Benchmark for Language Models</div>
  <nav class="icons" aria-label="Result views">
    <button data-view="leaderboard" title="Standings" aria-label="Standings"><svg viewBox="0 0 26 26" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M3 22h20"/><rect x="4" y="13" width="5" height="9"/><rect x="10.5" y="5" width="5" height="17"/><rect x="17" y="10" width="5" height="12"/></svg><span>Standings</span></button>
    <button data-view="skyline" title="Performance" aria-label="Performance"><svg viewBox="0 0 26 26" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M13 3v20"/><path d="M8 6h3M15 6h4M8 11h3M15 11h4M8 16h3M15 16h4M8 21h3M15 21h4"/><circle cx="13" cy="8.5" r="1.6" fill="currentColor"/><circle cx="13" cy="18.5" r="1.6" fill="currentColor"/></svg><span>Performance</span></button>
    <button data-view="games" title="Match history" aria-label="Match history"><svg viewBox="0 0 26 26" fill="currentColor"><path d="M3 3h20v20H3z" fill="none" stroke="currentColor" stroke-width="1.6"/><path d="M3 3h5v5H3zM13 3h5v5h-5zM8 8h5v5H8zM18 8h5v5h-5zM3 13h5v5H3zM13 13h5v5h-5zM8 18h5v5H8zM18 18h5v5h-5z" opacity=".75"/></svg><span>Match history</span></button>
  </nav>
</header>
<main id="main"></main>
<footer>
  <div class="links"><a href="#" onclick="go('about');return false">About</a><span class="sep">·</span><a href="DASH" target="_top">Dashboard</a><span class="sep">·</span><a href="https://github.com/ojas480/LLMRoyaleBench" target="_blank">GitHub</a></div>
  <p id="updated"></p>
  <p>© 2026 RoyaleBench</p>
</footer>
<script>
const DATA = /*DATA*/null;
const LOGOS = /*LOGOS*/{};
const TRACKS = Object.keys(DATA.tracks);
const FAM = {claude:"var(--f-claude)",gpt:"var(--f-gpt)",gemini:"var(--f-gemini)",grok:"var(--f-grok)",deepseek:"var(--f-deepseek)",bot:"var(--f-bot)",other:"var(--f-other)"};
for(const f of Object.keys(LOGOS)) FAM[f] = `var(--f-${f})`;
const METRICS = [
  {k:"W",label:"Wins",fmt:v=>String(v)},
  {k:"win_rate",label:"Win rate",fmt:v=>(v*100).toFixed(1)+"%",max:()=>1},
  {k:"crowns",label:"Crowns / game",fmt:v=>v.toFixed(2),max:()=>3},
  {k:"reliability",label:"Reliability",fmt:v=>(v*100).toFixed(1)+"%",max:()=>1,llm:true},
];
let S = {view:"leaderboard", track:TRACKS[0], metric:"W", sort:"rank", asc:true, q:"", player:"__all", details:false};
// Keep the view across page refreshes (the dashboard reloads this page as new games finish).
try { const saved = JSON.parse(sessionStorage.getItem("rb-results-v2")||"null"); if(saved){ Object.assign(S, saved); if(!TRACKS.includes(S.track)) S.track = TRACKS[0]; } } catch(e) {}
const $ = s => document.querySelector(s);
const esc = s => String(s).replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"})[c]);
function modelLabel(name, family=fam(name)){
  const logo = LOGOS[family];
  return `<span class="model-label">${logo ? `<img class="provider-logo" src="${logo.src}" alt="${logo.name} logo" title="${logo.name}" width="20" height="20">` : ""}<span>${esc(name)}</span></span>`;
}
function go(v){S.view=v;render()}
document.querySelectorAll("nav.icons button").forEach(b=>b.onclick=()=>go(b.dataset.view));
$("#updated").textContent = "Last updated " + DATA.updated;
document.querySelector('footer a[href="DASH"]').href = DATA.dashboard;

function selectTrack(index){S.track=TRACKS[index];S.player="__all";S.q="";render()}
function trackTabs(){
  if(TRACKS.length<2) return "";
  return `<div class="subtabs">${TRACKS.map((t,i)=>`<button aria-selected="${t===S.track}" onclick="selectTrack(${i})">${esc(t)} &middot; ${esc(DATA.tracks[t].deck_rules)}</button>`).join("")}</div>`;
}
function runningNote(T){ return T.running.length ? `<div class="note">In progress &middot; Standings include finished games only.</div>` : ""; }
function toggleDetails(){S.details=!S.details;S.sort="rank";S.asc=true;render()}

function skyline(T){
  const m = METRICS.find(x=>x.k===S.metric);
  let ps = T.players.filter(p=>p[m.k]!=null && (!m.llm || p.llm));
  const mt = `<div class="subtabs small">${METRICS.map(x=>`<button aria-selected="${x.k===S.metric}" onclick="S.metric='${x.k}';render()">${x.label}</button>`).join("")}</div>`;
  if(!ps.length) return trackTabs()+mt+`<div class="note">No games yet.</div>`;
  const vals = ps.map(p=>p[m.k]); const hi=Math.max(...vals), lo=Math.min(...vals);
  const H = Math.max(360, ps.length*46);
  // place by value; push apart labels that would overlap (min 26px), like the original's spacing
  const sorted = [...ps].sort((a,b)=>b[m.k]-a[m.k]);
  let ys = sorted.map(p=> hi===lo ? 0 : (hi-p[m.k])/(hi-lo)*(H-60));
  for(let i=1;i<ys.length;i++) if(ys[i]-ys[i-1]<26) ys[i]=ys[i-1]+26;
  const total = (ys[ys.length-1]||0)+80;
  const pts = sorted.map((p,i)=>`<div class="pt" style="top:${ys[i]+40}px"><div class="val">${m.fmt(p[m.k])}</div><div class="dot" style="background:${FAM[p.family]}"></div><div class="nm" style="color:${FAM[p.family]}">${modelLabel(p.name,p.family)}</div></div>`).join("");
  return trackTabs()+mt+runningNote(T)+`<div class="sky" style="height:${total}px"><div class="axis"></div>${pts}</div>`;
}

function barCell(v, max, fam, fmt){
  if(v==null) return `<td class="num na">–</td>`;
  const w = Math.max(0,Math.min(1, max? v/max : 0))*100;
  return `<td class="num"><span class="cell"><span class="v">${fmt(v)}</span><span class="bar"><span style="width:${w}%;background:color-mix(in srgb, ${FAM[fam]} 65%, transparent)"></span></span></span></td>`;
}
function leaderboard(T){
  const build = T.players.some(p=>p.deck_valid!=null);
  const cols = [
    {k:"rank",label:"#",num:true},{k:"name",label:"Player"},
    {k:"games",label:"Games",num:true},{k:"W",label:"Wins",num:true,bar:true},{k:"L",label:"Losses",num:true},{k:"D",label:"Draws",num:true},
    {k:"win_rate",label:"Win rate",num:true,bar:true},{k:"crowns",label:"Crowns / game",num:true,bar:true},
  ];
  if(S.details){
  cols.push({k:"three_crowns",label:"3-crown wins",num:true},{k:"reliability",label:"Reliability",num:true,bar:true});
  if(build) cols.push({k:"deck_valid",label:"Valid decks",num:true,bar:true});
  cols.push({k:"think_s",label:"Think time",num:true},{k:"cost_per_game",label:"Cost / game",num:true});
  }
  let ps = T.players.filter(p=>p.name.toLowerCase().includes(S.q.toLowerCase()));
  ps.sort((a,b)=>{const x=a[S.sort],y=b[S.sort]; if(x==null) return 1; if(y==null) return -1; const c = typeof x==="string"? x.localeCompare(y) : x-y; return S.asc? c : -c;});
  const maxG = Math.max(1,...T.players.map(p=>p.W));
  const fmt = {W:v=>v, win_rate:v=>(v*100).toFixed(1)+"%", crowns:v=>v.toFixed(2), reliability:v=>(v*100).toFixed(1)+"%", deck_valid:v=>(v*100).toFixed(0)+"%"};
  const maxes = {W:maxG, win_rate:1, crowns:3, reliability:1, deck_valid:1};
  const head = cols.map(c=>`<th class="${c.num?'num':''} ${S.sort===c.k?'sorted':''}" onclick="sortBy('${c.k}')">${c.label}</th>`).join("");
  const rows = ps.map(p=>"<tr>"+cols.map(c=>{
    const sc = S.sort===c.k ? " sortedc" : "";
    if(c.k==="rank") return `<td class="rk${sc}">${p.rank}</td>`;
    if(c.k==="name") return `<td class="${sc}">${modelLabel(p.name,p.family)}</td>`;
    if(c.bar) { const h = barCell(p[c.k], maxes[c.k], p.family, fmt[c.k]); return sc? h.replace('class="num','class="num'+sc) : h; }
    let v = p[c.k];
    if(v==null) return `<td class="num na${sc}">–</td>`;
    if(c.k==="think_s") v = v.toFixed(1)+" s";
    if(c.k==="cost_per_game") v = "$"+v.toFixed(3);
    return `<td class="num${sc}">${v}</td>`;
  }).join("")+"</tr>").join("");
  const scope = T.format==="duel" ? "This battle" : "This tournament";
  return trackTabs()+runningNote(T)+`<div class="results-tools"><div class="search"><input aria-label="Find a player" placeholder="Find a player…" value="${esc(S.q)}" oninput="S.q=this.value;renderTable()"></div><button class="details-toggle" aria-pressed="${S.details}" onclick="toggleDetails()">${S.details ? "Hide" : "Show"} model metrics</button></div>`+
    `<div class="lbwrap" id="lbt"><table><thead><tr>${head}</tr></thead><tbody>${rows || `<tr><td colspan="${cols.length}" class="empty-state">${T.games.length ? "No players match your search." : "No finished games yet. Results appear as games finish."}</td></tr>`}</tbody></table></div>`+
    `<div class="caption">${scope} only &middot; ${T.players.length} players &middot; ${T.games.length} finished games &middot; ${esc(T.deck_rules || "")}. Ranked by wins; ties use fewer losses, then crown difference.</div>`+
    `<details class="methodology"><summary>How to read these results</summary><p>Round robin describes the competition: every player is scheduled against every other player. A 1 v 1 contains just two players. Deck rules are separate: preset decks are supplied to the players; model-built decks are chosen by each model. Different runs are kept separate.</p><p>Win rate = wins / games. Crowns / game = average crowns won. Model metrics include legal-move reliability, valid deck rate when available, average thinking time, and cost per game. Ongoing runs may have unequal game counts.</p></details>`;

}
function sortBy(k){ if(S.sort===k) S.asc=!S.asc; else {S.sort=k; S.asc = (k==="rank"||k==="name"||k==="L"||k==="cost_per_game"||k==="think_s");} render(); }
function renderTable(){ const el=$("#lbt"); const T=DATA.tracks[S.track]; const tmp=document.createElement("div"); tmp.innerHTML=leaderboard(T); el.replaceWith(tmp.querySelector("#lbt")); }

function selectPlayer(index){
  S.player = index < 0 ? "__all" : DATA.tracks[S.track].players[index].name;
  render();
  $(".model-picker summary")?.focus();
}
function games(T){
  if(S.player!=="__all" && !T.players.some(p=>p.name===S.player)) S.player="__all";
  const opts = `<button type="button" aria-pressed="${S.player==="__all"}" onclick="selectPlayer(-1)">All models</button>` + T.players.map((p,i)=>`<button type="button" aria-pressed="${S.player===p.name}" onclick="selectPlayer(${i})">${modelLabel(p.name,p.family)}</button>`).join("");
  const gs = S.player==="__all" ? T.games : T.games.filter(g=>g.blue===S.player||g.red===S.player);
  const ps = S.player==="__all" ? T.players : T.players.filter(p=>p.name===S.player);
  const dec = ps.reduce((a,p)=>a+p.decisions,0);
  let blue=[0,0,0], red=[0,0,0];
  if(S.player==="__all"){ for(const g of gs){ if(g.winner===0){blue[0]++;red[1]++} else if(g.winner===1){blue[1]++;red[0]++} else {blue[2]++;red[2]++} } }
  else { const p=ps[0]; blue=p.as_blue; red=p.as_red; }
  const stack = a => { const n=a[0]+a[1]+a[2]||1; const pc=x=>(x/n*100).toFixed(1);
    return `<div class="stack"><span style="width:${pc(a[0])}%;background:#6f7279"></span><span style="width:${pc(a[1])}%;background:#a3a5aa"></span><span style="width:${pc(a[2])}%;background:#d2d0cb"></span></div><p>Wins ${pc(a[0])}% · Losses ${pc(a[1])}% · Draws ${pc(a[2])}%</p>`; };
  // matchups: pair -> W/L/D from the selected player's (or row player's) view
  const mu = {};
  for(const g of gs){
    let a=g.blue,b=g.red,r=g.winner===0?0:g.winner===1?1:2;
    if(S.player!=="__all" && a!==S.player){[a,b]=[b,a]; r = r===2?2:1-r;}
    if(S.player==="__all" && a>b){[a,b]=[b,a]; r = r===2?2:1-r;}
    const k=a+"|"+b; mu[k]=mu[k]||{a,b,W:0,L:0,D:0,last:0}; mu[k][["W","L","D"][r]]++; mu[k].last=Math.max(mu[k].last,g.t||0);
  }
  const murows = Object.values(mu).sort((x,y)=>y.last-x.last).map(m=>`<tr><td>${modelLabel(m.a)}</td><td>${modelLabel(m.b)}</td><td class="num">${m.W}</td><td class="num">${m.L}</td><td class="num">${m.D}</td></tr>`).join("");
  const recent = gs.slice(0,25).map(g=>{
    const w = g.winner===0?g.blue:g.winner===1?g.red:"draw";
    const len = g.ticks? (()=>{const s=Math.round(g.ticks*0.05);return Math.floor(s/60)+":"+String(s%60).padStart(2,"0")})() : "";
    const link = g.replay ? `${DATA.dashboard}/legacy/matches/${encodeURIComponent(g.job)}/${encodeURIComponent(g.id)}` : "";
    return `<tr><td>${modelLabel(g.blue)}</td><td>${modelLabel(g.red)}</td><td class="num">${g.crowns[0]}–${g.crowns[1]}</td><td>${w==="draw" ? "draw" : modelLabel(w)}</td><td>${esc(g.deck_name || (g.deck && !Array.isArray(g.deck) ? "Model-built" : "Preset deck"))}</td><td class="num">${len}</td><td>${link ? `<a href="${link}" target="_top">replay ↗</a>` : ""}</td></tr>`;}).join("");
  return trackTabs()+`<div class="select"><details class="model-picker"><summary aria-label="Filter games by model">${S.player==="__all" ? "All models" : modelLabel(S.player)}</summary><div class="model-options">${opts}</div></details></div>`+
    `<div class="stats"><div><b>${gs.length.toLocaleString()}</b><span>Games</span></div><div><b>${dec.toLocaleString()}</b><span>Decisions</span></div><div><b>${gs.length? (dec/(S.player==="__all"?gs.length:gs.length)/(S.player==="__all"?1:1)).toFixed(1):"0"}</b><span>Decisions / game</span></div></div>`+
    `<div class="sides"><h4>As blue</h4>${stack(blue)}<h4>As red</h4>${stack(red)}</div>`+
    `<h3>Matchups</h3><div class="card"><table><thead><tr><th>Player</th><th>Opponent</th><th class="num">W</th><th class="num">L</th><th class="num">D</th></tr></thead><tbody>${murows}</tbody></table></div>`+
    `<h3>Most Recent Games</h3><div class="card"><table><thead><tr><th>Blue</th><th>Red</th><th class="num">Crowns</th><th>Winner</th><th>Deck</th><th class="num">Length</th><th></th></tr></thead><tbody>${recent}</tbody></table></div>`;
}
function fam(n){ for(const t of Object.values(DATA.tracks)) for(const p of t.players) if(p.name===n) return p.family; return "other"; }

function about(){
  return `<div class="about">
<h4>What is this?</h4><p>Language models play full Clash Royale battles against each other on a deterministic open-source simulator (RoyaleGym). Every 2 seconds of game time each side gets a text view of the board (only what that player could see) and a numbered list of legal moves: wait, or a card from its hand at one of a fixed set of placement zones; spells can be aimed at visible enemy units or towers. It answers with <code>MOVE: n</code>. The game pauses while both sides decide, so only decisions matter, not speed.</p>
<h4>How are models ranked?</h4><p>Standings are calculated within the selected run, sorted by games won. Ties are broken by fewer losses, then by crown difference. Only finished games count. During an ongoing run, players may have different game counts; win rate is shown alongside wins for context.</p>
<h4>Competition and deck rules</h4><p><b>Round robin</b> is a tournament where every player is scheduled against the others. <b>1 v 1</b> shows a single two-player battle. Each run has its own standings. <b>Preset decks</b> are supplied to the players; <b>model-built decks</b> are chosen by each model. Deck rules are shown from the recorded games, independently of the competition format.</p>
<h4>What happens with bad answers?</h4><p>A reply without a legal move number is played as a wait and lowers <b>Reliability</b>. An invalid deck is replaced by a default deck and lowers <b>Valid decks</b>. If the model cannot be reached at all (rate limit, network), the game is thrown away and replayed, never scored. When waiting is the only legal move (no elixir), the model is not asked.</p>
<h4>Settings</h4><p>Models use the configuration recorded with each run. Game counts, deck rules, and reasoning settings may differ between runs. Only finished games contribute to the displayed results.</p></div>`;
}

function render(){
  try { sessionStorage.setItem("rb-results-v2", JSON.stringify(S)); } catch(e) {}
  document.querySelectorAll("nav.icons button").forEach(b=>b.setAttribute("aria-selected", b.dataset.view===S.view));
  const T = DATA.tracks[S.track];
  const el = $("#main");
  if(!T){ el.innerHTML = `<div class="note">No results yet.</div>`; return; }
  el.innerHTML = S.view==="skyline" ? skyline(T) : S.view==="games" ? games(T) : S.view==="about" ? about() : leaderboard(T);
}
render();
</script></body></html>
"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", help="SQLite database path (default: CR_ARENA_DB or runs/arena.db)")
    ap.add_argument("--classic", default="classic-v2")
    ap.add_argument("--build", default="build-v2")
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args()
    print("wrote", build(DB(args.db), args.classic, args.build, Path(args.out)))


if __name__ == "__main__":
    main()
