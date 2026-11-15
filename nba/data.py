"""Collects everything the page shows. Each section fails on its own: if one
source is down, that section is skipped and the rest of the page still builds."""
import logging
import re
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from . import espn, teams
from .config import ODDS_API_KEY, YOUTUBE_API_KEY
from .odds import OddsAPI, from_espn_competition
from .translate import Translator
from .videos import VideoFinder

log = logging.getLogger("nba")

IL = ZoneInfo("Asia/Jerusalem")
ET = ZoneInfo("America/New_York")
MONTHS_EN = ["January", "February", "March", "April", "May", "June", "July",
             "August", "September", "October", "November", "December"]


# ---------- helpers ----------

def season_of(d: date) -> tuple[int, int]:
    """Nov 2026 -> (2026, 2027). The season starts in October."""
    return (d.year, d.year + 1) if d.month >= 10 else (d.year - 1, d.year)


def en_date(d: date) -> str:
    return f"{MONTHS_EN[d.month - 1]} {d.day}, {d.year}"


def _int(v, default=0) -> int:
    try:
        return int(str(v).strip())
    except (TypeError, ValueError):
        return default


def _made_att(v) -> tuple[int, int]:
    try:
        m, a = str(v).split("-")
        return int(m), int(a)
    except (TypeError, ValueError):
        return 0, 0


def _hex(c, default="888888") -> str:
    c = (c or default).lstrip("#")
    return "#" + (c if re.fullmatch(r"[0-9a-fA-F]{6}", c) else default)


def _lum(h: str) -> float:
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (1, 3, 5))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _accent(color: str, alt: str) -> str:
    """A team color that stays readable on a dark background."""
    for c in (color, alt):
        if _lum(c) > 0.16:
            return c
    return "#94a3b8"


def _ts(iso: str) -> datetime:
    return datetime.fromisoformat(iso.replace("Z", "+00:00"))


_failed: list[str] = []


def safe(name, fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except Exception:  # noqa: BLE001
        log.exception("section '%s' failed, skipping it", name)
        _failed.append(name)
        return None


# ---------- games ----------

def _team(c: dict) -> dict:
    t = c.get("team", {})
    abbr = t.get("abbreviation", "")
    color, alt = _hex(t.get("color")), _hex(t.get("alternateColor"))
    record = next((r.get("summary") for r in c.get("records", [])
                   if r.get("type") == "total"), "")
    return {
        "abbr": abbr,
        "he": teams.full_name(abbr, t.get("displayName", "")),
        "he_short": teams.short_name(abbr, t.get("name", "")),
        "nick": t.get("name") or t.get("shortDisplayName", ""),
        "logo": t.get("logo"),
        "accent": _accent(color, alt),
        "score": _int(c.get("score")),
        "record": record,
        "home": c.get("homeAway") == "home",
    }


def _box(summary: dict) -> dict:
    """{team abbr: [players sorted by points]}"""
    out = {}
    for tb in summary.get("boxscore", {}).get("players", []):
        abbr = tb.get("team", {}).get("abbreviation", "")
        st = (tb.get("statistics") or [{}])[0]
        keys = st.get("keys", [])
        players = []
        for a in st.get("athletes", []):
            if a.get("didNotPlay") or not a.get("stats"):
                continue
            row = dict(zip(keys, a["stats"]))
            ath = a.get("athlete", {})
            fg = _made_att(row.get("fieldGoalsMade-fieldGoalsAttempted"))
            tp = _made_att(row.get("threePointFieldGoalsMade-threePointFieldGoalsAttempted"))
            ft = _made_att(row.get("freeThrowsMade-freeThrowsAttempted"))
            players.append({
                "id": ath.get("id"),
                "name": ath.get("displayName", ""),
                "headshot": (ath.get("headshot") or {}).get("href"),
                "min": row.get("minutes", ""),
                "pts": _int(row.get("points")),
                "reb": _int(row.get("rebounds")),
                "ast": _int(row.get("assists")),
                "stl": _int(row.get("steals")),
                "blk": _int(row.get("blocks")),
                "fg": fg, "tp": tp, "ft": ft,
                "two": (fg[0] - tp[0], fg[1] - tp[1]),
            })
        players.sort(key=lambda p: (p["pts"], p["ast"], p["reb"]), reverse=True)
        out[abbr] = players
    return out


def _status_he(status: dict) -> str:
    detail = (status.get("type") or {}).get("shortDetail") or ""
    m = re.search(r"(\d*)OT", detail)
    if not m:
        return "סיום"
    n = m.group(1)
    return "סיום · הארכה" if n in ("", "1") else f"סיום · {n} הארכות"


def _season_averages(athlete_id: str) -> dict | None:
    data = espn.athlete_overview(athlete_id)
    stats = data.get("statistics") or {}
    names = stats.get("names", [])
    for split in stats.get("splits", []):
        if split.get("displayName") == "Regular Season":
            return dict(zip(names, split.get("stats", [])))
    return None


def last_night(d: date, videos: VideoFinder) -> dict:
    sb = espn.scoreboard(d)
    games = []
    for ev in sb.get("events", []):
        comp = ev["competitions"][0]
        status = comp.get("status") or ev.get("status") or {}
        if not (status.get("type") or {}).get("completed"):
            continue
        cs = [_team(c) for c in comp.get("competitors", [])]
        away = next(c for c in cs if not c["home"])
        home = next(c for c in cs if c["home"])
        winner, loser = (away, home) if away["score"] > home["score"] else (home, away)
        box = safe(f"box score {ev['id']}", lambda: _box(espn.summary(ev["id"]))) or {}
        for t in (winner, loser):
            t["top"] = box.get(t["abbr"], [])[:2]
        games.append({"id": ev["id"], "start": ev.get("date", ""), "away": away, "home": home,
                      "winner": winner, "loser": loser, "status": _status_he(status),
                      "box": box})

    # Player of the night: most points, then assists, then rebounds.
    best = None
    for g in games:
        for t in (g["winner"], g["loser"]):
            for p in g["box"].get(t["abbr"], []):
                key = (p["pts"], p["ast"], p["reb"])
                if best is None or key > best[0]:
                    best = (key, p, t, g)
    potn = None
    if best:
        _, p, t, g = best
        opp = g["loser"] if t is g["winner"] else g["winner"]
        potn = {"player": p, "team": t, "opp": opp, "game_id": g["id"],
                "won": t is g["winner"],
                "season": safe("season averages", _season_averages, p["id"]) if p["id"] else None}

    games.sort(key=lambda g: (g["id"] != (potn or {}).get("game_id"), g["start"]))

    for g in games:
        a, h = g["away"], g["home"]
        g["video"] = videos.find(f"{a['nick']} at {h['nick']} full game highlights {en_date(d)}",
                                 must_contain=[a["nick"], h["nick"]])
        del g["box"]

    top10 = videos.find(f"NBA Top 10 Plays of the Night {en_date(d)}",
                        must_contain=["top 10"]) if games else None
    return {"games": games, "potn": potn, "top10": top10}


# ---------- standings ----------

def standings(season_end: int) -> list[dict]:
    data = espn.standings(season_end)
    confs = []
    for conf in data.get("children", []):
        rows = []
        for ent in conf.get("standings", {}).get("entries", []):
            s = {x["name"]: x.get("displayValue") for x in ent.get("stats", [])}
            t = ent.get("team", {})
            abbr = t.get("abbreviation", "")
            rows.append({
                "seed": _int(s.get("playoffSeed"), 99),
                "abbr": abbr,
                "he_short": teams.short_name(abbr, t.get("name", "")),
                "logo": (t.get("logos") or [{}])[0].get("href"),
                "record": s.get("overall") or f"{s.get('wins', 0)}-{s.get('losses', 0)}",
                "gb": s.get("gamesBehind") or "-",
                "streak": s.get("streak") or "",
            })
        rows.sort(key=lambda r: r["seed"])
        east = "east" in conf.get("name", "").lower()
        confs.append({"name": "המזרח" if east else "המערב", "east": east, "rows": rows})
    confs.sort(key=lambda c: not c["east"])
    return confs


# ---------- news ----------

TAGS = [
    ("פציעה", r"\b(injur\w*|sprain\w*|strain\w*|surgery|torn|tears?|fractur\w*|concussion|"
              r"sidelined|day-to-day|mri|out indefinitely|ruled out|will miss)\b"),
    ("טרייד", r"\b(trade[sd]?|trading|acquir\w+|deal sends)\b"),
    ("השעיה", r"\b(suspen\w+)\b"),
    ("שיא", r"\b(records?|career-high|franchise-high|milestone|all-time|history|historic)\b"),
    ("החתמה", r"\b(extension|re-sign\w*|signs?\b.*\b(deal|contract)|signed\b.*\b(deal|contract))\b"),
    ("שחרור", r"\b(waive[sd]?|waiving|released?|buyout)\b"),
    ("פיטורים", r"\b(fire[sd]?|dismiss\w*|parts? ways)\b"),
    ("מינוי", r"\b(hire[sd]?|hiring|appoint\w*|named (head )?coach)\b"),
]


def _tag(text: str) -> str | None:
    for tag, rx in TAGS:
        if re.search(rx, text, re.IGNORECASE):
            return tag
    return None


def news(now_utc: datetime, tr: Translator, hours=24, limit=5) -> list[dict]:
    data = espn.news(50)
    items, seen = [], set()
    for a in data.get("articles", []):
        aid = a.get("id")
        headline = (a.get("headline") or "").strip()
        if not headline or aid in seen or a.get("type") == "Media":
            continue
        try:
            published = _ts(a.get("published") or a.get("lastModified"))
        except (TypeError, ValueError):
            continue
        age = now_utc - published
        if age > timedelta(hours=hours) or age < timedelta(minutes=-30):
            continue
        desc = (a.get("description") or "").strip()
        tag = _tag(f"{headline} {desc}")
        if not tag:
            continue
        seen.add(aid)
        link = ((a.get("links") or {}).get("web") or {}).get("href")
        img = next((i.get("url") for i in a.get("images", []) if i.get("url")), None)
        items.append({"id": aid, "tag": tag, "headline_en": headline, "desc_en": desc,
                      "link": link, "image": img, "published": published,
                      "age_min": int(age.total_seconds() // 60),
                      "breaking": age <= timedelta(hours=3)})
    items.sort(key=lambda x: x["published"], reverse=True)
    items = items[:limit]
    for it in items:
        it["headline_he"] = tr.he(it["headline_en"])
        it["desc_he"] = tr.he(it["desc_en"])
    return items


# ---------- tonight ----------

def tonight(d: date, videos: VideoFinder, odds_api: OddsAPI) -> list[dict]:
    sb = espn.scoreboard(d)
    games = []
    for ev in sb.get("events", []):
        comp = ev["competitions"][0]
        status = comp.get("status") or ev.get("status") or {}
        state = (status.get("type") or {}).get("state")
        if state == "post":
            continue
        cs = [_team(c) for c in comp.get("competitors", [])]
        away = next(c for c in cs if not c["home"])
        home = next(c for c in cs if c["home"])
        odds = from_espn_competition(comp) or odds_api.lookup(away["nick"], home["nick"])
        games.append({
            "away": away, "home": home,
            "tip_il": _ts(ev["date"]).astimezone(IL),
            "live": state == "in",
            "live_detail": (status.get("type") or {}).get("shortDetail", ""),
            "odds": odds,
            "video": videos.find(f"{away['nick']} vs {home['nick']} preview prediction",
                                 must_contain=[away["nick"], home["nick"]],
                                 hours_back=48, prefer_nba_channel=False),
        })
    games.sort(key=lambda g: g["tip_il"])
    return games


# ---------- everything ----------

def collect(now_utc: datetime, state, last_night_date: date | None = None) -> dict:
    _failed.clear()
    now_il, now_et = now_utc.astimezone(IL), now_utc.astimezone(ET)
    ln_date = last_night_date or (now_et.date() - timedelta(days=1))
    tn_date = ln_date + timedelta(days=1)
    s_start, s_end = season_of(ln_date)
    log.info("last night (US Eastern) = %s, tonight = %s, season %d-%02d",
             ln_date, tn_date, s_start, s_end % 100)

    videos = VideoFinder(YOUTUBE_API_KEY, state)
    tr = Translator(state)
    odds_api = OddsAPI(ODDS_API_KEY)

    ln = safe("last night", last_night, ln_date, videos) or {}
    data = {
        "now_il": now_il,
        "ln_date": ln_date,
        "season": f"{s_start}-{s_end % 100:02d}",
        "games": ln.get("games"),
        "potn": ln.get("potn"),
        "top10": ln.get("top10"),
        "standings": safe("standings", standings, s_end),
        "news": safe("news", news, now_utc, tr),
        "tonight": safe("tonight", tonight, tn_date, videos, odds_api),
        "has_youtube_key": bool(YOUTUBE_API_KEY),
        "failed": list(_failed),
    }
    return data
