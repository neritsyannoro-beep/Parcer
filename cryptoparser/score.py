"""Движок скоринга: превращает набор новостей в отранжированную ленту.

Итоговый скор складывается из семи независимых компонентов, каждый из которых
ограничен сверху, — так ни один сигнал не может «сломать» ранжирование
в одиночку. Все веса лежат в config.WEIGHTS, словари — в keywords.py.
"""

from __future__ import annotations

import math
import re
from datetime import datetime, timezone

from . import config
from .keywords import (
    BIG_ENTITIES,
    PENALTIES,
    SIGNALS,
    STALE_MARKERS,
    TAG_LABELS,
)

# ---------------------------------------------------------------- подготовка регулярок


def _phrase_regex(phrase: str) -> re.Pattern:
    """Короткие слова матчим целиком, длинные — как префикс (accumulat -> accumulating)."""
    escaped = re.escape(phrase)
    if len(phrase) <= 5:
        pattern = rf"\b{escaped}\b"
    else:
        pattern = rf"\b{escaped}"
    return re.compile(pattern, re.IGNORECASE)


_SIGNAL_RE: dict[str, list[tuple[re.Pattern, float, str]]] = {
    tag: [(_phrase_regex(p), w, p) for p, w in pairs] for tag, pairs in SIGNALS.items()
}
_ENTITY_RE = [(_phrase_regex(e), w, e) for e, w in BIG_ENTITIES.items()]
_PENALTY_RE = [(_phrase_regex(p), w, p) for p, w in PENALTIES.items()]
_STALE_RE = [(_phrase_regex(p), w, p) for p, w in STALE_MARKERS.items()]

# Числа вида $1.2B, 450 million, 12,5%
_MONEY_RE = re.compile(
    r"\$\s?([\d,.]+)\s?(k|m|b|t|thousand|million|billion|trillion)?\b", re.IGNORECASE
)
_AMOUNT_RE = re.compile(
    r"\b([\d,.]+)\s?(k|m|b|thousand|million|billion)\s?"
    r"(btc|eth|sol|xrp|usdt|usdc|doge|tokens?|coins?)\b",
    re.IGNORECASE,
)
_PERCENT_RE = re.compile(r"\b(\d{1,4}(?:[.,]\d+)?)\s?%")

_MULTIPLIER = {
    None: 1.0, "": 1.0,
    "k": 1e3, "thousand": 1e3,
    "m": 1e6, "million": 1e6,
    "b": 1e9, "billion": 1e9,
    "t": 1e12, "trillion": 1e12,
}

_STOPWORDS = {
    "the", "and", "for", "with", "from", "that", "this", "into", "over", "after",
    "amid", "says", "said", "will", "have", "has", "not", "but", "its", "his",
    "her", "their", "was", "were", "are", "how", "why", "what", "when", "who",
    "new", "more", "than", "all", "can", "could", "would", "may", "might",
    "about", "against", "just", "now", "you", "your", "our", "out", "off",
    "crypto", "cryptocurrency", "price", "market", "markets", "news",
}


def _to_float(raw: str) -> float | None:
    """'1,234.5' и '1.234,5' -> float."""
    txt = raw.strip()
    if not txt:
        return None
    if "," in txt and "." in txt:
        txt = txt.replace(",", "") if txt.rfind(".") > txt.rfind(",") else txt.replace(".", "").replace(",", ".")
    elif "," in txt:
        parts = txt.split(",")
        txt = txt.replace(",", "") if len(parts[-1]) == 3 else txt.replace(",", ".")
    try:
        return float(txt)
    except ValueError:
        return None


# ---------------------------------------------------------------- компоненты скора


def _authority(item: dict) -> float:
    base = {1: 15.0, 2: 10.0, 3: 5.0}.get(item.get("tier", 3), 5.0)
    if item.get("kind") == "social":
        base -= 3.0  # соцсети быстрые, но им нужен подтверждающий сигнал
    return max(0.0, base)


def _keyword_score(text: str) -> tuple[float, dict[str, float], list[str]]:
    """Возвращает (общий скор, скор по тегам, найденные фразы)."""
    per_tag: dict[str, float] = {}
    matched: list[str] = []

    for tag, patterns in _SIGNAL_RE.items():
        hits = [(w, phrase) for rx, w, phrase in patterns if rx.search(text)]
        if not hits:
            continue
        hits.sort(reverse=True)
        # Затухание: второе и последующие совпадения в одной категории дают
        # меньше — иначе перечисление синонимов накручивало бы скор.
        total = 0.0
        for i, (w, phrase) in enumerate(hits):
            total += w * (0.55**i)
            if i < 2:
                matched.append(phrase)
        per_tag[tag] = min(total, 26.0)

    # Сумма по категориям с мягким сжатием: важно, чтобы новость,
    # закрывающая две сильные темы, обходила новость с одной.
    raw = sum(per_tag.values())
    score = min(55.0, 55.0 * (1 - math.exp(-raw / 34.0)))
    return score, per_tag, matched


def _magnitude(text: str) -> tuple[float, str | None]:
    """Чем крупнее сумма или процент в тексте, тем громче новость."""
    best_usd = 0.0
    for m in _MONEY_RE.finditer(text):
        val = _to_float(m.group(1))
        if val is None:
            continue
        best_usd = max(best_usd, val * _MULTIPLIER.get((m.group(2) or "").lower(), 1.0))

    for m in _AMOUNT_RE.finditer(text):
        val = _to_float(m.group(1))
        if val is None:
            continue
        units = val * _MULTIPLIER.get((m.group(2) or "").lower(), 1.0)
        asset = m.group(3).lower()
        # Грубая оценка в долларах, чтобы сравнивать «1000 BTC» и «$50M».
        rough_price = {"btc": 60000, "eth": 3000, "sol": 150, "xrp": 0.6}.get(asset, 1.0)
        best_usd = max(best_usd, units * rough_price)

    label: str | None = None
    money_score = 0.0
    if best_usd >= 1e6:
        # $1M -> ~4, $100M -> ~11, $1B -> ~14.5, $10B -> ~18
        money_score = min(18.0, 4.0 + 4.7 * math.log10(best_usd / 1e6))
        if best_usd >= 1e9:
            label = f"${best_usd / 1e9:.1f}B"
        else:
            label = f"${best_usd / 1e6:.0f}M"

    pct_score = 0.0
    for m in _PERCENT_RE.finditer(text):
        val = _to_float(m.group(1))
        if val is None or val > 100000:
            continue
        if val >= 15:
            pct_score = max(pct_score, min(9.0, (val - 10) / 12.0))
            if label is None and val >= 25:
                label = f"{val:.0f}%"

    return min(18.0, money_score + pct_score * 0.6), label


def _entities(text: str) -> tuple[float, list[str]]:
    hits = [(w, name) for rx, w, name in _ENTITY_RE if rx.search(text)]
    if not hits:
        return 0.0, []
    hits.sort(reverse=True)
    total = sum(w * (0.6**i) for i, (w, _) in enumerate(hits))
    return min(12.0, total), [name for _, name in hits[:3]]


def _recency(published_ts: float, now_ts: float) -> tuple[float, float]:
    age_h = max(0.0, (now_ts - published_ts) / 3600.0)
    score = 14.0 * (0.5 ** (age_h / config.RECENCY_HALF_LIFE_HOURS))
    return score, age_h


def _penalty(text: str) -> tuple[float, list[str]]:
    total = 0.0
    reasons: list[str] = []
    for rx, w, phrase in _PENALTY_RE + _STALE_RE:
        if rx.search(text):
            total += w
            reasons.append(phrase)
    return max(-38.0, total), reasons[:3]


# ---------------------------------------------------------------- кластеризация сюжетов


def _tokens(title: str) -> frozenset[str]:
    """Значимые токены заголовка с грубой нормализацией числа (etfs -> etf)."""
    words = re.findall(r"[a-zA-Zа-яА-Я0-9$]{3,}", title.lower())
    out = set()
    for w in words:
        if w in _STOPWORDS:
            continue
        if len(w) >= 4 and w.endswith("s") and not w.endswith("ss"):
            w = w[:-1]
        out.add(w)
    return frozenset(out)


def _similarity(a: frozenset[str], b: frozenset[str]) -> tuple[float, int]:
    """Смешанная метрика: Jaccard + коэффициент перекрытия.

    Чистого Jaccard мало: одно и то же событие в разных изданиях называют
    по-разному и заголовки разной длины, из-за чего знаменатель раздувается.
    Перекрытие (по меньшему из двух наборов) это компенсирует.
    """
    inter = len(a & b)
    if inter == 0:
        return 0.0, 0
    jaccard = inter / len(a | b)
    overlap = inter / min(len(a), len(b))
    return 0.5 * jaccard + 0.5 * overlap, inter


def cluster_items(items: list[dict]) -> list[list[dict]]:
    """Группирует записи об одном событии (Jaccard по токенам заголовка).

    Один сюжет из пяти изданий — это сильный признак «горячего», поэтому
    склейка нужна не только чтобы убрать дубли, но и как сигнал.
    """
    # Сначала самые свежие — представителем кластера станет актуальная запись.
    ordered = sorted(items, key=lambda x: -x["published_ts"])
    clusters: list[list[dict]] = []
    # Токены каждого участника кластера отдельно: объединять их в одну подпись
    # нельзя — она разрастается и перестаёт совпадать с новыми заголовками.
    members: list[list[frozenset[str]]] = []

    for item in ordered:
        toks = _tokens(item["title"])
        if len(toks) < 3:
            clusters.append([item])
            members.append([toks])
            continue

        placed = False
        for idx, member_tokens in enumerate(members):
            # Достаточно совпасть с любым из участников — сюжет обрастает
            # разными формулировками одного события.
            for sig in member_tokens[:6]:
                if len(sig) < 3:
                    continue
                similarity, inter = _similarity(toks, sig)
                # Три общих значимых слова — минимум, иначе склеиваются любые
                # две новости про «bitcoin price».
                if inter >= 3 and similarity >= config.CLUSTER_SIMILARITY:
                    clusters[idx].append(item)
                    member_tokens.append(toks)
                    placed = True
                    break
            if placed:
                break
        if not placed:
            clusters.append([item])
            members.append([toks])

    return clusters


# ---------------------------------------------------------------- публичный API


def score_item(item: dict, cluster_size: int = 1, now_ts: float | None = None) -> dict:
    """Считает скор одной записи и обогащает её метаданными для интерфейса."""
    now_ts = now_ts if now_ts is not None else datetime.now(timezone.utc).timestamp()
    text = f"{item['title']} {item.get('summary', '')}"

    authority = _authority(item)
    kw_score, per_tag, matched = _keyword_score(text)
    mag_score, mag_label = _magnitude(text)
    ent_score, ent_names = _entities(text)
    rec_score, age_h = _recency(item["published_ts"], now_ts)
    pen_score, pen_reasons = _penalty(text)

    corr_score = 0.0
    if cluster_size > 1:
        corr_score = min(14.0, 14.0 * (1.0 - 1.0 / cluster_size))

    onchain_bonus = float(item.get("onchain_bonus", 0.0))

    w = config.WEIGHTS
    total = (
        authority * w["source_authority"]
        + kw_score * w["keywords"]
        + mag_score * w["magnitude"]
        + ent_score * w["entities"]
        + rec_score * w["recency"]
        + corr_score * w["corroboration"]
        + onchain_bonus * w["onchain_bonus"]
        + pen_score
    )

    # Соцсети без ни одного тематического сигнала — почти наверняка болтовня.
    if item.get("kind") == "social" and not per_tag:
        total -= 12.0

    total = max(0.0, min(100.0, total))

    tags = sorted(per_tag, key=lambda t: -per_tag[t])[:4]
    if item.get("forced_tags"):
        for t in item["forced_tags"]:
            if t not in tags:
                tags.insert(0, t)
        tags = tags[:4]

    reasons: list[str] = []
    if cluster_size > 1:
        reasons.append(f"{cluster_size} источника пишут об этом")
    if mag_label:
        reasons.append(f"крупная сумма {mag_label}")
    for t in tags[:2]:
        reasons.append(TAG_LABELS.get(t, t).lower())
    if ent_names:
        reasons.append(", ".join(ent_names[:2]))
    if age_h <= 1.5:
        reasons.append("опубликовано только что")
    if pen_reasons:
        reasons.append(f"понижено: {pen_reasons[0]}")

    item = dict(item)
    item.update(
        {
            "score": round(total, 1),
            "tags": tags,
            "tag_scores": {k: round(v, 1) for k, v in per_tag.items()},
            "matched": matched[:6],
            "entities": ent_names,
            "magnitude": mag_label,
            "age_hours": round(age_h, 1),
            "cluster_size": cluster_size,
            "reasons": reasons[:4],
            "breakdown": {
                "источник": round(authority, 1),
                "сигналы": round(kw_score, 1),
                "масштаб": round(mag_score, 1),
                "имена": round(ent_score, 1),
                "свежесть": round(rec_score, 1),
                "подтверждения": round(corr_score, 1),
                "ончейн": round(onchain_bonus, 1),
                "штрафы": round(pen_score, 1),
            },
        }
    )
    return item


def rank(items: list[dict]) -> list[dict]:
    """Кластеризует, скорит и сортирует все записи."""
    now_ts = datetime.now(timezone.utc).timestamp()
    clusters = cluster_items(items)
    scored: list[dict] = []

    for cluster in clusters:
        size = len(cluster)
        variants = [score_item(it, size, now_ts) for it in cluster]
        variants.sort(key=lambda x: -x["score"])
        best = variants[0]
        best["also_in"] = [
            {"source": v["source"], "url": v["url"]} for v in variants[1:6]
        ]
        scored.append(best)

    scored.sort(key=lambda x: (-x["score"], -x["published_ts"]))
    return scored


def assign_tiers(items: list[dict]) -> list[dict]:
    """Раскладывает по трём категориям: hot / interesting / medium."""
    out: list[dict] = []
    for i, item in enumerate(items):
        if item["score"] >= config.TIER_HOT_THRESHOLD or i < config.MIN_HOT:
            tier = "hot"
        elif (
            item["score"] >= config.TIER_INTERESTING_THRESHOLD
            or i < config.MIN_HOT + config.MIN_INTERESTING
        ):
            tier = "interesting"
        else:
            tier = "medium"
        item = dict(item)
        item["tier_label"] = tier
        out.append(item)
    return out
