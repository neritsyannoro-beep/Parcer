"""Сборка feed.json для фронтенда + генерация черновиков постов для X."""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

from . import config
from .keywords import TAG_EMOJI, TAG_LABELS

log = logging.getLogger(__name__)

TWEET_LIMIT = 280
# X сокращает любую ссылку до 23 символов вне зависимости от её длины.
TCO_LENGTH = 23

TIER_ORDER = ["hot", "interesting", "medium"]
TIER_META = {
    "hot": {"label": "Горячие", "emoji": "🔥"},
    "interesting": {"label": "Интересные", "emoji": "⚡"},
    "medium": {"label": "Средние", "emoji": "📊"},
}

_HOOKS = {
    "security": "🚨",
    "insides": "🕵️",
    "whales": "🐋",
    "regulation": "⚖️",
    "listings": "📈",
    "new_coins": "🌱",
    "institutions": "🏦",
    "macro": "🌍",
    "onchain": "⛓️",
    "trends": "🔥",
}

_HASHTAGS = {
    "bitcoin": "#Bitcoin", "btc": "#BTC", "ethereum": "#Ethereum", "eth": "#ETH",
    "solana": "#Solana", "sol": "#SOL", "xrp": "#XRP", "ripple": "#XRP",
    "binance": "#Binance", "coinbase": "#Coinbase", "tether": "#USDT",
    "blackrock": "#BlackRock", "sec": "#SEC", "doge": "#DOGE",
    "dogecoin": "#DOGE", "microstrategy": "#MSTR",
}


def _trim(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    cut = text[: limit - 1]
    if " " in cut:
        cut = cut[: cut.rfind(" ")]
    return cut.rstrip(" ,.;:—-") + "…"


def build_tweet(item: dict) -> str:
    """Черновик поста: хук, заголовок, цифра, хэштеги, ссылка.

    Считаем длину по правилам X (ссылка = 23 символа) и подрезаем заголовок,
    чтобы черновик всегда влезал без ручной правки.
    """
    tags = item.get("tags") or []
    hook = next((_HOOKS[t] for t in tags if t in _HOOKS), "📰")

    tail_parts: list[str] = []
    if item.get("magnitude"):
        tail_parts.append(item["magnitude"])
    if item.get("cluster_size", 1) >= 3:
        tail_parts.append(f"{item['cluster_size']} sources")
    tail = f"\n\n{' · '.join(tail_parts)}" if tail_parts else ""

    hashtags: list[str] = []
    for ent in item.get("entities") or []:
        tag = _HASHTAGS.get(ent.lower())
        if tag and tag not in hashtags:
            hashtags.append(tag)
    if not hashtags:
        hashtags.append("#crypto")
    hashtag_line = f"\n\n{' '.join(hashtags[:3])}"

    fixed = len(hook) + 1 + len(tail) + len(hashtag_line) + 2 + TCO_LENGTH
    title_budget = max(40, TWEET_LIMIT - fixed)
    title = _trim(item["title"], title_budget)

    return f"{hook} {title}{tail}{hashtag_line}\n\n{item['url']}"


def _domain(url: str) -> str:
    m = re.match(r"https?://(?:www\.)?([^/]+)", url or "")
    return m.group(1) if m else ""


def build_feed(items: list[dict], seen: dict[str, dict], stats_extra: dict) -> dict:
    """Формирует итоговую структуру feed.json."""
    now = datetime.now(timezone.utc)
    items = items[: config.MAX_ITEMS_IN_FEED]

    out_items: list[dict] = []
    tag_counts: dict[str, int] = {}
    tier_counts: dict[str, int] = {t: 0 for t in TIER_ORDER}

    for it in items:
        prev = seen.get(it["id"])
        # «Новое» = запись, которой не было в предыдущих запусках.
        is_new = prev is None
        rising = bool(prev and it["score"] > (prev.get("best_score") or 0) + 4)

        tier = it.get("tier_label", "medium")
        tier_counts[tier] = tier_counts.get(tier, 0) + 1
        for t in it.get("tags") or []:
            tag_counts[t] = tag_counts.get(t, 0) + 1

        out_items.append(
            {
                "id": it["id"],
                "title": it["title"],
                "summary": it.get("summary", ""),
                "url": it["url"],
                "domain": _domain(it["url"]),
                "source": it.get("source", ""),
                "kind": it.get("kind", "news"),
                "published": it.get("published"),
                "age_hours": it.get("age_hours", 0),
                "score": it["score"],
                "tier": tier,
                "tags": it.get("tags", []),
                "reasons": it.get("reasons", []),
                "breakdown": it.get("breakdown", {}),
                "magnitude": it.get("magnitude"),
                "entities": it.get("entities", []),
                "cluster_size": it.get("cluster_size", 1),
                "also_in": it.get("also_in", []),
                "is_new": is_new,
                "is_rising": rising,
                "tweet": build_tweet(it),
            }
        )

    tags_meta = [
        {
            "id": tag,
            "label": TAG_LABELS.get(tag, tag),
            "emoji": TAG_EMOJI.get(tag, "•"),
            "count": count,
        }
        for tag, count in sorted(tag_counts.items(), key=lambda kv: -kv[1])
    ]

    return {
        "generated_at": now.isoformat(),
        "generated_ts": int(now.timestamp()),
        "tiers": [
            {"id": t, **TIER_META[t], "count": tier_counts.get(t, 0)} for t in TIER_ORDER
        ],
        "tags": tags_meta,
        "stats": {
            "total": len(out_items),
            "new": sum(1 for i in out_items if i["is_new"]),
            "sources": len({i["source"] for i in out_items if i["source"]}),
            **stats_extra,
        },
        "items": out_items,
    }


def write_feed(feed: dict, path: Path | None = None) -> Path:
    target = path or config.FEED_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    # Пишем через временный файл: фронтенд не должен прочитать половину JSON.
    tmp = target.with_suffix(".json.tmp")
    tmp.write_text(
        json.dumps(feed, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )
    tmp.replace(target)
    log.info("лента записана: %s (%d записей)", target, len(feed["items"]))
    return target
