"""YouTube videos. With a YOUTUBE_API_KEY: real video links (cached, quota-limited).
Without a key: a YouTube search link, so every button still works."""
import logging
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import quote_plus

from .http import get_json

log = logging.getLogger("nba")

NBA_CHANNEL = "UCWJ2lWNubArHWmf3FIHbfcQ"
SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
DAILY_SEARCH_LIMIT = 80          # 80 searches x 100 units = 8,000 of the 10,000 free daily units
MISS_RETRY_SECONDS = 3 * 3600    # a "not found yet" result is retried after 3 hours
KEEP_DAYS = 7


def search_link(query: str) -> dict:
    return {"url": f"https://www.youtube.com/results?search_query={quote_plus(query)}",
            "title": None, "thumb": None, "is_search": True}


class VideoFinder:
    def __init__(self, api_key: str, state):
        self.key = api_key
        self.cache = state.get("youtube_cache")
        self.usage = state.get("youtube_usage")
        self._prune()

    def _prune(self):
        cutoff = time.time() - KEEP_DAYS * 86400
        for q in [q for q, v in self.cache.items() if v.get("ts", 0) < cutoff]:
            del self.cache[q]

    def _can_search(self) -> bool:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if self.usage.get("day") != today:
            self.usage.clear()
            self.usage.update({"day": today, "count": 0})
        return self.usage["count"] < DAILY_SEARCH_LIMIT

    def _search(self, query, channel=None, published_after=None):
        if not self._can_search():
            log.warning("YouTube daily search limit reached; using search links")
            return None
        self.usage["count"] += 1
        params = {"part": "snippet", "q": query, "type": "video", "maxResults": 8,
                  "key": self.key, "order": "relevance"}
        if channel:
            params["channelId"] = channel
        if published_after:
            params["publishedAfter"] = published_after.strftime("%Y-%m-%dT%H:%M:%SZ")
        data = get_json(SEARCH_URL, params, secrets=[self.key], retries=1)
        return data.get("items", [])

    def find(self, query: str, must_contain=(), hours_back: int = 36,
             prefer_nba_channel: bool = True) -> dict:
        """Return {url, title, thumb, is_search}. Never raises."""
        fallback = search_link(query)
        if not self.key:
            return fallback
        hit = self.cache.get(query)
        if hit and (hit.get("url") or time.time() - hit.get("ts", 0) < MISS_RETRY_SECONDS):
            return hit["video"] if hit.get("url") else fallback

        after = datetime.now(timezone.utc) - timedelta(hours=hours_back)
        needles = [n.lower() for n in must_contain]
        video = None
        try:
            channels = [NBA_CHANNEL, None] if prefer_nba_channel else [None]
            for ch in channels:
                items = self._search(query, ch, after)
                if items is None:
                    return fallback
                for it in items:
                    sn = it.get("snippet", {})
                    title = sn.get("title", "")
                    if all(n in title.lower() for n in needles):
                        vid = it["id"]["videoId"]
                        thumbs = sn.get("thumbnails", {})
                        thumb = (thumbs.get("high") or thumbs.get("medium") or {}).get("url")
                        video = {"url": f"https://www.youtube.com/watch?v={vid}",
                                 "title": _unescape(title), "thumb": thumb,
                                 "channel": sn.get("channelTitle"), "is_search": False}
                        break
                if video:
                    break
        except Exception as e:  # noqa: BLE001
            log.warning("YouTube search failed for %r: %s", query, e)
            return fallback

        self.cache[query] = {"ts": time.time(), "url": video["url"] if video else None,
                             "video": video}
        return video or fallback


def _unescape(s: str) -> str:
    import html
    return html.unescape(s)
