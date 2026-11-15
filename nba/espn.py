"""ESPN public API: scores, box scores, standings, news, odds. No key needed."""
from datetime import date

from .http import get_json

SITE = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba"


def scoreboard(d: date) -> dict:
    return get_json(f"{SITE}/scoreboard", {"dates": d.strftime("%Y%m%d")})


def summary(event_id: str) -> dict:
    return get_json(f"{SITE}/summary", {"event": event_id})


def standings(season_end_year: int) -> dict:
    return get_json("https://site.api.espn.com/apis/v2/sports/basketball/nba/standings",
                    {"season": season_end_year})


def news(limit: int = 50) -> dict:
    return get_json(f"{SITE}/news", {"limit": limit})


def athlete_overview(athlete_id: str) -> dict:
    return get_json("https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba/"
                    f"athletes/{athlete_id}/overview")
