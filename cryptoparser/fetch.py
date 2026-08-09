"""Загрузка и нормализация записей из RSS-источников."""

from __future__ import annotations

import hashlib
import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse, parse_qs

import feedparser
import requests

from . import config

log = logging.getLogger(__name__)

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": config.USER_AGENT, "Accept": "*/*"})
    return s


def clean_text(raw: str | None, limit: int = 400) -> str:
    """Убирает HTML-теги и лишние пробелы из описания."""
    if not raw:
        return ""
    txt = _TAG_RE.sub(" ", raw)
    txt = (
        txt.replace("&nbsp;", " ")
        .replace("&amp;", "&")
        .replace("&quot;", '"')
        .replace("&#39;", "'")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
    )
    txt = _WS_RE.sub(" ", txt).strip()
    return txt[:limit]


def _unwrap_google_link(url: str) -> str:
    """Google News прячет исходную ссылку в параметре ?url= — достаём её."""
    try:
        parsed = urlparse(url)
        if "news.google.com" in parsed.netloc:
            qs = parse_qs(parsed.query)
            if "url" in qs and qs["url"]:
                return qs["url"][0]
    except Exception:  # noqa: BLE001 — ссылка не критична, оставляем как есть
        pass
    return url


def _publisher_from_google_title(title: str) -> tuple[str, str | None]:
    """В Google News заголовок выглядит как 'Текст - Издание'."""
    if " - " in title:
        head, _, tail = title.rpartition(" - ")
        if head and len(tail) < 45:
            return head.strip(), tail.strip()
    return title, None


def _parse_date(entry) -> datetime | None:
    for key in ("published_parsed", "updated_parsed"):
        val = getattr(entry, key, None) or entry.get(key) if hasattr(entry, "get") else None
        if val:
            try:
                return datetime.fromtimestamp(time.mktime(val), tz=timezone.utc)
            except Exception:  # noqa: BLE001
                continue
    return None


def make_id(url: str, title: str) -> str:
    base = (_unwrap_google_link(url) or title).strip().lower().rstrip("/")
    return hashlib.sha1(base.encode("utf-8", "ignore")).hexdigest()[:16]


def fetch_feed(feed: dict, session: requests.Session) -> list[dict]:
    """Скачивает один фид и возвращает нормализованные записи."""
    last_err: Exception | None = None
    for attempt in range(config.HTTP_RETRIES + 1):
        try:
            resp = session.get(feed["url"], timeout=config.HTTP_TIMEOUT)
            if resp.status_code >= 400:
                raise requests.HTTPError(f"HTTP {resp.status_code}")
            parsed = feedparser.parse(resp.content)
            break
        except Exception as exc:  # noqa: BLE001 — падение одного фида не должно ронять запуск
            last_err = exc
            if attempt < config.HTTP_RETRIES:
                time.sleep(1.5 * (attempt + 1))
    else:
        parsed = None

    if parsed is None:
        log.warning("не удалось загрузить %s: %s", feed["name"], last_err)
        return []

    cutoff = datetime.now(timezone.utc) - timedelta(hours=config.MAX_AGE_HOURS)
    now = datetime.now(timezone.utc)
    items: list[dict] = []

    for entry in parsed.entries[:60]:
        title = clean_text(getattr(entry, "title", ""), 300)
        link = getattr(entry, "link", "") or ""
        if not title or not link:
            continue

        source_name = feed["name"]
        if feed["kind"] == "search":
            title, publisher = _publisher_from_google_title(title)
            if publisher:
                source_name = publisher
            link = _unwrap_google_link(link)

        published = _parse_date(entry)
        # Записи без даты считаем свежими наполовину: не выбрасываем, но и
        # полный бонус за свежесть не даём.
        if published is None:
            published = now - timedelta(hours=config.RECENCY_HALF_LIFE_HOURS)
        if published < cutoff:
            continue
        if published > now + timedelta(minutes=30):
            published = now  # кривые таймзоны в некоторых фидах

        summary = clean_text(
            getattr(entry, "summary", None) or getattr(entry, "description", None)
        )

        items.append(
            {
                "id": make_id(link, title),
                "title": title,
                "url": link,
                "summary": summary,
                "source": source_name,
                "feed_name": feed["name"],
                "tier": feed["tier"],
                "kind": feed["kind"],
                "published": published.isoformat(),
                "published_ts": published.timestamp(),
            }
        )

    log.info("%-22s %3d записей", feed["name"], len(items))
    return items


def fetch_all(feeds: list[dict]) -> list[dict]:
    """Параллельно загружает все фиды и дедуплицирует по id."""
    session = _session()
    collected: dict[str, dict] = {}
    ok_feeds = 0

    with ThreadPoolExecutor(max_workers=config.MAX_WORKERS) as pool:
        futures = {pool.submit(fetch_feed, f, session): f for f in feeds}
        for fut in as_completed(futures):
            feed = futures[fut]
            try:
                items = fut.result()
            except Exception as exc:  # noqa: BLE001
                log.warning("фид %s упал: %s", feed["name"], exc)
                continue
            if items:
                ok_feeds += 1
            for item in items:
                prev = collected.get(item["id"])
                # При дубликате оставляем запись из более авторитетного источника.
                if prev is None or item["tier"] < prev["tier"]:
                    collected[item["id"]] = item

    log.info("загружено %d уникальных записей из %d/%d фидов",
             len(collected), ok_feeds, len(feeds))
    return list(collected.values())
