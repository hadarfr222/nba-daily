"""Win probability from moneyline odds.
Primary: odds ESPN publishes on its scoreboard (DraftKings), no key needed.
Fallback: The Odds API (h2h market) if ODDS_API_KEY is set."""
import logging

from .http import get_json

log = logging.getLogger("nba")


def implied(american) -> float | None:
    try:
        s = str(american).strip().upper()
        if s in ("EVEN", "EV"):
            return 0.5
        v = float(s.replace("+", ""))
    except (TypeError, ValueError):
        return None
    if v == 0:
        return None
    return (-v) / (-v + 100) if v < 0 else 100 / (v + 100)


def normalize(p_away, p_home):
    if not p_away or not p_home:
        return None
    total = p_away + p_home
    away = round(100 * p_away / total)
    return away, 100 - away


def _pick_line(side: dict):
    for k in ("current", "close", "open"):
        odds = (side.get(k) or {}).get("odds")
        if odds:
            return odds
    return side.get("odds")


def from_espn_competition(comp: dict):
    """(away%, home%, provider) or None."""
    for o in comp.get("odds") or []:
        ml = o.get("moneyline") or {}
        a = implied(_pick_line(ml.get("away") or {}))
        h = implied(_pick_line(ml.get("home") or {}))
        if a is None or h is None:
            a = implied((o.get("awayTeamOdds") or {}).get("moneyLine"))
            h = implied((o.get("homeTeamOdds") or {}).get("moneyLine"))
        res = normalize(a, h)
        if res:
            return res[0], res[1], (o.get("provider") or {}).get("name")
    return None


class OddsAPI:
    """The Odds API, fetched at most once per build."""

    def __init__(self, key: str):
        self.key = key
        self._events = None

    def _load(self):
        if self._events is not None:
            return self._events
        self._events = []
        if not self.key:
            return self._events
        try:
            self._events = get_json(
                "https://api.the-odds-api.com/v4/sports/basketball_nba/odds",
                {"regions": "us", "markets": "h2h", "oddsFormat": "american",
                 "apiKey": self.key}, secrets=[self.key], retries=1)
        except Exception as e:  # noqa: BLE001
            log.warning("Odds API failed: %s", e)
        return self._events

    def lookup(self, away_nick: str, home_nick: str):
        """Match by team nickname ("Celtics"); average over bookmakers."""
        for ev in self._load():
            home, away = ev.get("home_team", ""), ev.get("away_team", "")
            if not (home.endswith(home_nick) and away.endswith(away_nick)):
                continue
            pa, ph = [], []
            for b in ev.get("bookmakers", []):
                for m in b.get("markets", []):
                    if m.get("key") != "h2h":
                        continue
                    prices = {o["name"]: o["price"] for o in m.get("outcomes", [])}
                    a, h = implied(prices.get(away)), implied(prices.get(home))
                    if a and h:
                        pa.append(a)
                        ph.append(h)
            if pa:
                res = normalize(sum(pa) / len(pa), sum(ph) / len(ph))
                return res[0], res[1], "The Odds API"
        return None
