"""One shared HTTP session with retries. Never logs secret values."""
import logging
import time

import requests

log = logging.getLogger("nba")

_session = requests.Session()
_session.headers.update({
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36",
    "Accept": "application/json",
})


def _redact(text: str, secrets) -> str:
    for s in secrets or ():
        if s:
            text = text.replace(s, "***")
    return text


def get_json(url, params=None, timeout=20, retries=2, secrets=()):
    """GET a JSON document. Retries on failure; raises the last error."""
    last = None
    for attempt in range(retries + 1):
        try:
            r = _session.get(url, params=params, timeout=timeout)
            r.raise_for_status()
            return r.json()
        except Exception as e:  # noqa: BLE001 - every source must fail softly
            last = e
            log.warning("request failed (%d/%d): %s", attempt + 1, retries + 1,
                        _redact(str(e), secrets))
            if attempt < retries:
                time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(_redact(str(last), secrets))
