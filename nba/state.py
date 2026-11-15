"""Small JSON files in state/ that survive between runs (caches, counters)."""
import json
import logging
from pathlib import Path

from .config import ROOT

log = logging.getLogger("nba")
STATE_DIR = ROOT / "state"


class State:
    def __init__(self, readonly: bool = False):
        self.readonly = readonly
        self._data = {}

    def get(self, name: str) -> dict:
        if name not in self._data:
            path = STATE_DIR / f"{name}.json"
            try:
                self._data[name] = json.loads(path.read_text(encoding="utf-8"))
            except FileNotFoundError:
                self._data[name] = {}
            except Exception as e:  # noqa: BLE001
                log.warning("state file %s unreadable, starting fresh: %s", path.name, e)
                self._data[name] = {}
        return self._data[name]

    def save(self):
        if self.readonly:
            log.info("dry run: state not saved")
            return
        STATE_DIR.mkdir(exist_ok=True)
        for name, data in self._data.items():
            path = STATE_DIR / f"{name}.json"
            path.write_text(json.dumps(data, ensure_ascii=False, indent=1, sort_keys=True),
                            encoding="utf-8")
