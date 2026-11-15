"""English to Hebrew via the free MyMemory service, cached in state/.
If translation fails, the original English text is kept."""
import logging
import re
import time

from .http import get_json

log = logging.getLogger("nba")
KEEP_DAYS = 14


class Translator:
    def __init__(self, state):
        self.cache = state.get("translations")
        self.disabled = False
        cutoff = time.time() - KEEP_DAYS * 86400
        for k in [k for k, v in self.cache.items() if v.get("ts", 0) < cutoff]:
            del self.cache[k]

    def he(self, text: str) -> str | None:
        """Hebrew translation, or None if unavailable."""
        text = (text or "").strip()
        if not text:
            return None
        text = _shorten(text, 450)
        if text in self.cache:
            return self.cache[text]["he"]
        if self.disabled:
            return None
        try:
            data = get_json("https://api.mymemory.translated.net/get",
                            {"q": text, "langpair": "en|he"}, retries=1, timeout=15)
            out = (data.get("responseData") or {}).get("translatedText") or ""
            if data.get("quotaFinished") or "MYMEMORY WARNING" in out.upper():
                log.warning("translation quota reached; keeping English")
                self.disabled = True
                return None
            if data.get("responseStatus") != 200 or not re.search(r"[֐-׿]", out):
                return None
            self.cache[text] = {"he": out, "ts": time.time()}
            return out
        except Exception as e:  # noqa: BLE001
            log.warning("translation failed: %s", e)
            self.disabled = True
            return None


def _shorten(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    cut = text[:limit]
    dot = cut.rfind(". ")
    return cut[: dot + 1] if dot > limit // 2 else cut.rsplit(" ", 1)[0] + "…"
