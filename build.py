"""Builds the NBA morning page.

    python build.py                    build into site/ (the real page)
    python build.py --dry-run          build into preview/ only, caches are not saved
    python build.py --date 2026-11-14  show a specific night (US Eastern date)
"""
import argparse
import logging
import sys
from datetime import date, datetime, timezone

from nba.config import ROOT
from nba.data import collect
from nba.icon import ensure_icons
from nba.render import STATIC, write_site
from nba.state import State


def main() -> int:
    ap = argparse.ArgumentParser(description="NBA בוקר page builder")
    ap.add_argument("--dry-run", action="store_true", help="build into preview/, don't save state")
    ap.add_argument("--date", help="last-night date YYYY-MM-DD (US Eastern), for testing")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        datefmt="%Y-%m-%d %H:%M:%S")
    log = logging.getLogger("nba")

    ensure_icons(STATIC)
    state = State(readonly=args.dry_run)
    ln_date = date.fromisoformat(args.date) if args.date else None

    data = collect(datetime.now(timezone.utc), state, ln_date)
    out = ROOT / ("preview" if args.dry_run else "site")
    write_site(data, out)
    state.save()

    games = data.get("games")
    log.info("built %s: %s games, %s news, %s tonight%s", out / "index.html",
             "?" if games is None else len(games), len(data.get("news") or []),
             len(data.get("tonight") or []),
             f", skipped sections: {', '.join(data['failed'])}" if data["failed"] else "")
    return 0


if __name__ == "__main__":
    sys.exit(main())
