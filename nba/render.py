"""Turns the collected data into static HTML pages."""
import re
import shutil
from html import escape
from pathlib import Path

from .config import ROOT

STATIC = ROOT / "static"
DAYS_HE = ["שני", "שלישי", "רביעי", "חמישי", "שישי", "שבת", "ראשון"]
ARCHIVE_DAYS = 14


def e(v) -> str:
    return escape("" if v is None else str(v), quote=True)


def pct(m, a) -> str:
    return f"{round(100 * m / a)}%" if a else "—"


def frac(ma) -> str:
    return f"<bdi>{ma[0]}/{ma[1]}</bdi>"


def ago_he(minutes: int) -> str:
    if minutes < 60:
        return f"לפני {max(minutes, 1)} דק'"
    h = minutes // 60
    return "לפני שעה" if h == 1 else ("לפני שעתיים" if h == 2 else f"לפני {h} שעות")


PLAY = ('<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M8 5.5v13a1 1 0 0 0 1.5.86l10.5-6.5'
        'a1 1 0 0 0 0-1.72L9.5 4.64A1 1 0 0 0 8 5.5z"/></svg>')
SEARCH = ('<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M10.5 3a7.5 7.5 0 0 1 5.96 12.05l4.25 '
          '4.24-1.42 1.42-4.24-4.25A7.5 7.5 0 1 1 10.5 3zm0 2a5.5 5.5 0 1 0 0 11 5.5 5.5 0 0 0 0-11z"/></svg>')


def video_button(v, label_found: str, label_search: str, big=False) -> str:
    if not v:
        return ""
    if v.get("is_search"):
        return (f'<a class="vbtn search" href="{e(v["url"])}" target="_blank" rel="noopener">'
                f'{SEARCH}<span>{e(label_search)}</span></a>')
    if big and v.get("thumb"):
        return (f'<a class="vthumb" href="{e(v["url"])}" target="_blank" rel="noopener">'
                f'<img src="{e(v["thumb"])}" alt="" loading="lazy"><span class="vplay">{PLAY}</span>'
                f'<span class="vtitle">{e(v.get("title"))}</span></a>')
    return (f'<a class="vbtn" href="{e(v["url"])}" target="_blank" rel="noopener">'
            f'{PLAY}<span>{e(label_found)}</span></a>')


def logo(url, cls="logo") -> str:
    return f'<img class="{cls}" src="{e(url)}" alt="" loading="lazy">' if url else ""


# ---------- sections ----------

def hero(potn) -> str:
    p, t, opp = potn["player"], potn["team"], potn["opp"]
    score = f'{t["score"]}-{opp["score"]}'
    result = "ניצחון" if potn["won"] else "הפסד"
    tiles = "".join(
        f'<div class="tile{" main" if k == "pts" else ""}"><b>{p[k]}</b><span>{lbl}</span></div>'
        for k, lbl in (("pts", "נקודות"), ("reb", "ריבאונדים"), ("ast", "אסיסטים"),
                       ("stl", "חטיפות"), ("blk", "חסימות")))
    shooting = "".join(
        f'<div class="shot"><span class="slabel">{lbl}</span><span class="sval">{frac(ma)}</span>'
        f'<span class="spct">{pct(*ma)}</span>'
        f'<span class="bar"><i style="width:{round(100 * ma[0] / ma[1]) if ma[1] else 0}%"></i></span></div>'
        for lbl, ma in (("מהשדה", p["fg"]), ("לשתיים", p["two"]), ("לשלוש", p["tp"]),
                        ("עונשין", p["ft"])))
    season = ""
    s = potn.get("season")
    if s:
        parts = [f"{s.get('avgPoints', '—')} נק'", f"{s.get('avgRebounds', '—')} ריב'",
                 f"{s.get('avgAssists', '—')} אס'", f"{s.get('fieldGoalPct', '—')}% מהשדה"]
        games = s.get("gamesPlayed")
        season = (f'<div class="season"><span class="eyebrow">ממוצעי עונה'
                  f'{f" · {e(games)} משחקים" if games else ""}</span>'
                  f'<div>{" · ".join(e(x) for x in parts)}</div></div>')
    photo = (f'<img class="hero-photo" src="{e(p["headshot"])}" alt="{e(p["name"])}">'
             if p.get("headshot") else "")
    return f'''
<section class="hero" style="--tc:{t["accent"]}" aria-label="שחקן הלילה">
  <div class="hero-media">{photo}
    <div class="hero-id">
      <span class="badge">⭐ שחקן הלילה</span>
      <h2>{e(p["name"])}</h2>
      <div class="hero-team">{logo(t["logo"])}<span>{e(t["he"])}</span>
        <span class="muted">· {result} <bdi>{score}</bdi> מול {e(opp["he_short"])}</span></div>
    </div>
  </div>
  <div class="tiles">{tiles}</div>
  <div class="shooting">{shooting}</div>
  {season}
</section>'''


def player_line(p, full: bool) -> str:
    base = f"{p['pts']} נק' · {p['reb']} ריב' · {p['ast']} אס'"
    if not full:
        return f'<div class="pl"><span class="pname">{e(p["name"])}</span><span class="pstat">{base}</span></div>'
    more = f" · {p['stl']} חט' · {p['blk']} חס'"
    shoot = (f"שדה {frac(p['fg'])} ({pct(*p['fg'])}) · שלוש {frac(p['tp'])} · "
             f"עונשין {frac(p['ft'])}")
    return (f'<div class="pl top"><span class="pname">{e(p["name"])}</span>'
            f'<span class="pstat">{base}{more}</span><span class="pshoot">{shoot}</span></div>')


def game_card(g, potn_game_id) -> str:
    rows = ""
    for t, win in ((g["winner"], True), (g["loser"], False)):
        rows += (f'<div class="srow{" win" if win else ""}">{logo(t["logo"])}'
                 f'<span class="tname">{e(t["he"])}</span><span class="rec"><bdi>{e(t["record"])}</bdi></span>'
                 f'<span class="pts">{t["score"]}</span></div>')
    teams_html = ""
    for t in (g["winner"], g["loser"]):
        players = "".join(player_line(p, i == 0) for i, p in enumerate(t.get("top", [])))
        teams_html += (f'<div class="tblock" style="--tc:{t["accent"]}"><h4>{e(t["he_short"])}</h4>'
                       f'{players or "<p class=muted>אין נתוני שחקנים</p>"}</div>')
    flag = '<span class="badge small">⭐ המשחק של שחקן הלילה</span>' if g["id"] == potn_game_id else ""
    return f'''
<article class="card game">
  <div class="ghead">{flag}<span class="status">{e(g["status"])}</span></div>
  <div class="score">{rows}</div>
  <div class="tblocks">{teams_html}</div>
  {video_button(g.get("video"), "תקציר המשחק", "חיפוש תקציר ביוטיוב")}
</article>'''


BANDS = [(1, 6, "play", "🟢 פלייאוף"), (7, 10, "playin", "🟡 פליי-אין"),
         (11, 99, "out", "🔴 מחוץ לפלייאוף")]


def standings_html(confs) -> str:
    out = ""
    for c in confs:
        body = ""
        for lo, hi, cls, label in BANDS:
            rows = [r for r in c["rows"] if lo <= r["seed"] <= hi]
            if not rows:
                continue
            body += f'<tr class="band {cls}"><td colspan="4">{label}</td></tr>'
            for r in rows:
                body += (f'<tr class="{cls}"><td class="seed">{r["seed"]}</td>'
                         f'<td class="team">{logo(r["logo"], "logo sm")}<span>{e(r["he_short"])}</span>'
                         f'<span class="abbr">{e(r["abbr"])}</span></td>'
                         f'<td class="num"><bdi>{e(r["record"])}</bdi></td><td class="num">{e(r["gb"])}</td></tr>')
        out += f'''
<div class="card conf {"east" if c["east"] else "west"}">
  <h3>{e(c["name"])}</h3>
  <table><thead><tr><th>#</th><th>קבוצה</th><th>מאזן</th><th>פער</th></tr></thead>
  <tbody>{body}</tbody></table>
</div>'''
    return out


def news_html(items) -> str:
    out = ""
    for it in items:
        head = it.get("headline_he") or it["headline_en"]
        desc = it.get("desc_he") or it["desc_en"]
        img = (f'<img class="nimg" src="{e(it["image"])}" alt="" loading="lazy">'
               if it.get("image") else "")
        brk = '<span class="breaking">Breaking</span>' if it["breaking"] else ""
        link = (f'<a class="more" href="{e(it["link"])}" target="_blank" rel="noopener">לכתבה המלאה ←</a>'
                if it.get("link") else "")
        orig = (f'<p class="orig" dir="ltr">{e(it["headline_en"])}</p>'
                if it.get("headline_he") else "")
        out += f'''
<article class="card news">
  {img}
  <div class="nbody">
    <div class="nmeta">{brk}<span class="tag">{e(it["tag"])}</span><span class="muted">{ago_he(it["age_min"])}</span></div>
    <h4>{e(head)}</h4>{orig}
    <p>{e(desc)}</p>
    {link}
  </div>
</article>'''
    return out


def live_he(detail: str) -> str:
    """'4th - 2:29' -> 'רבע 4 · 2:29', 'Halftime' -> 'מחצית'."""
    d = (detail or "").strip()
    if d.lower().startswith("half"):
        return "מחצית"
    # ESPN writes either "4th - 2:29" or "2:29 - 4th".
    clock = re.search(r"\b\d{1,2}:\d{2}\b|\b\d{1,2}\.\d\b", d)
    clock = f" · {clock.group(0)}" if clock else ""
    m = re.search(r"\b(\d)(?:st|nd|rd|th)\b", d, re.IGNORECASE)
    if m:
        q = f"רבע {m.group(1)}"
        return f"סוף {q}" if d.lower().startswith("end") else q + clock
    if re.search(r"OT\b", d):
        return "הארכה" + clock
    return d


def _distinct(c1: str, c2: str) -> bool:
    """True when two #rrggbb colors are easy to tell apart."""
    a = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(c2[i:i + 2], 16) for i in (1, 3, 5)]
    return sum((x - y) ** 2 for x, y in zip(a, b)) ** 0.5 > 90


def tonight_card(g) -> str:
    a, h = g["away"], g["home"]
    if g["live"]:
        when = f'<span class="live">● חי</span><span class="muted"><bdi>{e(live_he(g["live_detail"]))}</bdi></span>'
    else:
        when = f'<span class="tip">{g["tip_il"]:%H:%M}</span><span class="muted">שעון ישראל</span>'
    odds = ""
    if g.get("odds"):
        pa, ph, provider = g["odds"]
        h_color = h["accent"] if _distinct(a["accent"], h["accent"]) else "#64748b"
        odds = f'''
  <div class="prob" aria-label="סיכויי ניצחון לפי ההימורים">
    <div class="plabels"><span>{e(a["he_short"])} <b>{pa}%</b></span><span><b>{ph}%</b> {e(h["he_short"])}</span></div>
    <div class="pbar"><i style="width:{pa}%;background:{a["accent"]}"></i><i style="width:{ph}%;background:{h_color}"></i></div>
    <div class="psrc muted">סיכויי ניצחון לפי יחסי ההימורים{f" ({e(provider)})" if provider else ""}</div>
  </div>'''
    elif not g["live"]:
        odds = '<div class="psrc muted">יחסי הימורים עוד לא פורסמו</div>'
    return f'''
<article class="card tonight">
  <div class="matchup">
    <div class="side">{logo(a["logo"], "logo lg")}<span>{e(a["he"])}</span><span class="rec"><bdi>{e(a["record"])}</bdi></span></div>
    <div class="vs">{when}</div>
    <div class="side">{logo(h["logo"], "logo lg")}<span>{e(h["he"])}</span><span class="rec"><bdi>{e(h["record"])}</bdi></span></div>
  </div>
  {odds}
  {video_button(g.get("video"), "סרטון הכנה", "חיפוש סרטון הכנה")}
</article>'''


# ---------- pages ----------

TABS = [
    ("index.html", "בית", '<path d="M3 11.5 12 4l9 7.5V20a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z"/>'),
    ("games.html", "תוצאות", '<path d="M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20zm0 2c1.2 0 2.4.3 3.4.8A12 12 0 0 0 13 11h-2a12 12 0 0 0-2.4-6.2A8 8 0 0 1 12 4zM6.9 6.1A10 10 0 0 1 9 11H4.1a8 8 0 0 1 2.8-4.9zM4.1 13H9a10 10 0 0 1-2.1 4.9A8 8 0 0 1 4.1 13zm4.5 6.2A12 12 0 0 0 11 13h2a12 12 0 0 0 2.4 6.2 8 8 0 0 1-6.8 0zm8.5-1.3A10 10 0 0 1 15 13h4.9a8 8 0 0 1-2.8 4.9zM15 11a10 10 0 0 1 2.1-4.9 8 8 0 0 1 2.8 4.9z"/>'),
    ("standings.html", "טבלה", '<path d="M4 4h16a1 1 0 0 1 1 1v14a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1zm1 2v3h14V6zm0 5v3h14v-3zm0 5v2h14v-2z"/>'),
    ("news.html", "חדשות", '<path d="M5 3h11a1 1 0 0 1 1 1v3h3a1 1 0 0 1 1 1v10a3 3 0 0 1-3 3H6a3 3 0 0 1-3-3V5a2 2 0 0 1 2-2zm12 6v9a1 1 0 0 0 2 0V9zM6 6v4h8V6zm0 6v2h8v-2zm0 4v2h8v-2z"/>'),
    ("tonight.html", "הלילה", '<path d="M14.5 2.5a9.5 9.5 0 1 0 7 15.9A8 8 0 0 1 14.5 2.5z"/>'),
]


def layout(data, base: str, active: str, body: str) -> str:
    now = data["now_il"]
    games = data.get("games")
    n = len(games) if games is not None else None
    count = f"{n} משחקים אמש" if n else ("לא היו משחקים אמש" if n == 0 else "")
    tabs = "".join(
        f'<a href="{f}"{" class=on aria-current=page" if f == active else ""}>'
        f'<svg viewBox="0 0 24 24" aria-hidden="true">{icon}</svg><span>{label}</span></a>'
        for f, label, icon in TABS)
    title = next(label for f, label, _ in TABS if f == active)
    return f'''<!doctype html>
<html lang="he" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{"" if active == "index.html" else title + " · "}בוקר NBA | {now.day}/{now.month}</title>
<meta name="theme-color" content="#0a0e16">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="NBA בוקר">
<link rel="manifest" href="{base}manifest.webmanifest">
<link rel="apple-touch-icon" href="{base}assets/icon-180.png">
<link rel="icon" type="image/png" href="{base}assets/icon-192.png">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Heebo:wght@400;500;700;800;900&display=swap" rel="stylesheet">
<link rel="stylesheet" href="{base}assets/style.css">
</head>
<body>
<header class="topbar">
  <div class="wrap">
    <h1>בוקר NBA <span class="sep">|</span> <bdi>{now.day}/{now.month}</bdi></h1>
    <p class="sub">יום {DAYS_HE[now.weekday()]} · {count}{" · " if count else ""}עודכן ב-<bdi>{now:%H:%M}</bdi></p>
  </div>
</header>
<main class="wrap">
{body}
</main>
<nav class="tabbar" aria-label="ניווט"><div class="tabs">{tabs}</div></nav>
</body>
</html>'''


def mini_result(g) -> str:
    w, l = g["winner"], g["loser"]
    return (f'<a class="mini" href="games.html#g{e(g["id"])}">'
            f'<span class="mside win">{logo(w["logo"], "logo sm")}<span>{e(w["he_short"])}</span></span>'
            f'<b class="mscore win">{w["score"]}</b><span class="mdash">-</span><b class="mscore">{l["score"]}</b>'
            f'<span class="mside lose"><span>{e(l["he_short"])}</span>{logo(l["logo"], "logo sm")}</span></a>')


def mini_tonight(g) -> str:
    a, h = g["away"], g["home"]
    when = "חי" if g["live"] else f'{g["tip_il"]:%H:%M}'
    return (f'<a class="mini" href="tonight.html">'
            f'<span class="mside">{logo(a["logo"], "logo sm")}<span>{e(a["he_short"])}</span></span>'
            f'<b class="mtime{" live" if g["live"] else ""}">{when}</b>'
            f'<span class="mside lose"><span>{e(h["he_short"])}</span>{logo(h["logo"], "logo sm")}</span></a>')


def sec_title(text, extra="", more_href=None, more_label="הכל"):
    more = f'<a class="seemore" href="{more_href}">{more_label} ‹</a>' if more_href else ""
    extra = f' <span class="muted">{extra}</span>' if extra else ""
    return f'<h2 class="sec"><span>{text}{extra}</span>{more}</h2>'


def home_body(data, base, archive_links) -> str:
    parts = []
    breaking = next((n for n in (data.get("news") or []) if n["breaking"]), None)
    if breaking:
        head = breaking.get("headline_he") or breaking["headline_en"]
        parts.append(f'<a class="breaking-bar" href="news.html"><span class="breaking">Breaking</span>'
                     f'<span>{e(head)}</span></a>')
    if data.get("potn"):
        parts.append(hero(data["potn"]))
    games = data.get("games")
    if games:
        rows = "".join(mini_result(g) for g in games)
        parts.append(f'<section>{sec_title("תוצאות אמש", "", "games.html", "לכל הנתונים")}'
                     f'<div class="card list">{rows}</div></section>')
    elif games == []:
        parts.append('<section><div class="card empty">לא היו משחקים אמש</div></section>')
    if data.get("top10"):
        parts.append(f'<section>{sec_title("טופ 10 מהלכים")}<div class="card top10">'
                     f'{video_button(data["top10"], "צפייה בטופ 10", "חיפוש טופ 10 ביוטיוב", big=True)}</div></section>')
    tn = data.get("tonight")
    if tn:
        rows = "".join(mini_tonight(g) for g in tn[:4])
        parts.append(f'<section>{sec_title("הלילה ב-NBA", f"{len(tn)} משחקים", "tonight.html", "סיכויים ותצוגה מקדימה")}'
                     f'<div class="card list">{rows}</div></section>')
    if archive_links:
        links = " ".join(f'<a href="{base}archive/{d}/index.html">{d[8:10]}/{d[5:7]}</a>'
                         for d in archive_links)
        parts.append(f'<div class="archive"><span class="muted">ימים קודמים:</span> {links}</div>')
    parts.append('<p class="credits muted">נתונים: ESPN · סרטונים: YouTube · מתעדכן אוטומטית</p>')
    return "".join(parts)


def games_body(data) -> str:
    games = data.get("games")
    if games is None:
        return '<div class="card empty">התוצאות לא זמינות כרגע</div>'
    if not games:
        return '<div class="card empty">לא היו משחקים אמש</div>'
    potn_id = (data.get("potn") or {}).get("game_id")
    return sec_title("תוצאות אמש", f"{len(games)} משחקים") + "".join(
        game_card(g, potn_id).replace('<article class="card game">',
                                      f'<article class="card game" id="g{e(g["id"])}">', 1)
        for g in games)


def standings_body(data) -> str:
    if not data.get("standings"):
        return '<div class="card empty">הטבלה לא זמינה כרגע</div>'
    return (sec_title("טבלת הליגה", f'עונת {e(data["season"])}')
            + '<input type="radio" name="conf" id="c-east" checked><input type="radio" name="conf" id="c-west">'
            + '<div class="seg"><label for="c-east">מזרח</label><label for="c-west">מערב</label></div>'
            + f'<div class="confs">{standings_html(data["standings"])}</div>')


def news_body(data) -> str:
    items = data.get("news")
    if items is None:
        return '<div class="card empty">החדשות לא זמינות כרגע</div>'
    return sec_title("חדשות", "24 השעות האחרונות") + (
        news_html(items) or '<div class="card empty">אין חדשות משמעותיות ב-24 השעות האחרונות</div>')


def tonight_body(data) -> str:
    tn = data.get("tonight")
    if tn is None:
        return '<div class="card empty">משחקי הלילה לא זמינים כרגע</div>'
    return sec_title("הלילה ב-NBA", f"{len(tn)} משחקים") + (
        "".join(tonight_card(g) for g in tn) or '<div class="card empty">אין משחקים הלילה</div>')


MANIFEST = '''{
  "name": "NBA בוקר",
  "short_name": "NBA בוקר",
  "start_url": "./",
  "scope": "./",
  "display": "standalone",
  "dir": "rtl",
  "lang": "he",
  "background_color": "#0a0e16",
  "theme_color": "#0a0e16",
  "icons": [
    {"src": "assets/icon-192.png", "sizes": "192x192", "type": "image/png"},
    {"src": "assets/icon-512.png", "sizes": "512x512", "type": "image/png"}
  ]
}
'''


def _write_pages(data, folder: Path, base: str, archive_links):
    folder.mkdir(parents=True, exist_ok=True)
    bodies = {
        "index.html": home_body(data, base, archive_links),
        "games.html": games_body(data),
        "standings.html": standings_body(data),
        "news.html": news_body(data),
        "tonight.html": tonight_body(data),
    }
    for name, body in bodies.items():
        (folder / name).write_text(layout(data, base, name, body), encoding="utf-8")


def write_site(data, out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)
    archive = out_dir / "archive"
    archive.mkdir(exist_ok=True)
    for old in archive.glob("*.html"):   # old one-file-per-day archive format
        old.unlink()
    assets = out_dir / "assets"
    assets.mkdir(exist_ok=True)
    for f in STATIC.iterdir():
        if f.is_file():
            shutil.copy2(f, assets / f.name)
    (out_dir / "manifest.webmanifest").write_text(MANIFEST, encoding="utf-8")
    (out_dir / ".nojekyll").write_text("", encoding="utf-8")

    today = data["now_il"].date().isoformat()
    days = sorted((p.name for p in archive.iterdir() if p.is_dir()), reverse=True)
    older = [d for d in days if d < today][:ARCHIVE_DAYS]

    _write_pages(data, out_dir, "", older)
    _write_pages(data, archive / today, "../../", [])
