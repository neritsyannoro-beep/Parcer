"""Опциональное переранжирование топа новостей через Claude API.

По умолчанию выключено (USE_LLM_RERANK=0) — вся лента работает на бесплатных
эвристиках. Включай, если хочешь, чтобы модель пересобрала топ и дописала
короткий хук на русском для поста в X.

Стоит денег: это Anthropic API (оплата за токены), она не входит в подписку
Claude Pro. Расход — примерно пара центов на запуск при топ-30.
"""

from __future__ import annotations

import json
import logging

from . import config
from .keywords import TAG_LABELS

log = logging.getLogger(__name__)

SYSTEM = """Ты — редактор крипто-новостного канала в X (Twitter).
Тебе дают список новостей с предварительными оценками эвристического движка.
Твоя задача — пересобрать оценки так, как это сделал бы опытный трейдер:
выше всего то, что реально двигает рынок или даёт торговую идею,
ниже — пересказы, реклама и вода.

Для каждой новости верни:
  id     — идентификатор из входных данных, без изменений
  score  — оценка 0..100 (насколько это интересно крипто-аудитории X)
  hook   — первая строка поста на русском, до 100 символов, без хэштегов

Оценивай строго: 90+ только для действительно крупных событий."""

# Структурированный вывод: модель обязана вернуть ровно эту схему.
SCHEMA = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "score": {"type": "integer"},
                    "hook": {"type": "string"},
                },
                "required": ["id", "score", "hook"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["items"],
    "additionalProperties": False,
}


def _payload(items: list[dict]) -> str:
    compact = [
        {
            "id": it["id"],
            "title": it["title"],
            "source": it.get("source", ""),
            "tags": [TAG_LABELS.get(t, t) for t in it.get("tags", [])],
            "heuristic_score": it["score"],
            "age_hours": it.get("age_hours"),
            "sources_count": it.get("cluster_size", 1),
        }
        for it in items
    ]
    return json.dumps(compact, ensure_ascii=False)


def rerank(items: list[dict]) -> list[dict]:
    """Пересчитывает скор для топ-N новостей. При любой ошибке — возвращает как было."""
    if not config.USE_LLM_RERANK or not config.ANTHROPIC_API_KEY:
        return items

    try:
        import anthropic
    except ImportError:
        log.warning("USE_LLM_RERANK=1, но пакет anthropic не установлен — пропускаю")
        return items

    top = items[: config.LLM_RERANK_TOP_N]
    if not top:
        return items

    try:
        client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
        response = client.messages.create(
            model=config.LLM_MODEL,
            max_tokens=8000,
            system=SYSTEM,
            output_config={
                "effort": "low",
                "format": {"type": "json_schema", "schema": SCHEMA},
            },
            messages=[{"role": "user", "content": _payload(top)}],
        )
    except Exception as exc:  # noqa: BLE001 — лента важнее переранжирования
        log.warning("LLM-переранжирование упало: %s", exc)
        return items

    if response.stop_reason == "refusal":
        log.warning("модель отказалась обрабатывать запрос, оставляю эвристику")
        return items

    text = next((b.text for b in response.content if b.type == "text"), None)
    if not text:
        return items

    try:
        verdicts = {v["id"]: v for v in json.loads(text)["items"]}
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        log.warning("не разобрал ответ модели: %s", exc)
        return items

    updated: list[dict] = []
    for it in items:
        verdict = verdicts.get(it["id"])
        if not verdict:
            updated.append(it)
            continue
        it = dict(it)
        heuristic = it["score"]
        llm_score = max(0, min(100, int(verdict.get("score", heuristic))))
        # Смешиваем: эвристика знает свежесть и подтверждения, модель — смысл.
        it["score"] = round(0.4 * heuristic + 0.6 * llm_score, 1)
        it["llm_score"] = llm_score
        hook = (verdict.get("hook") or "").strip()
        if hook:
            it["hook"] = hook[:120]
        updated.append(it)

    updated.sort(key=lambda x: (-x["score"], -x["published_ts"]))
    log.info("LLM переранжировал топ-%d", len(top))
    return updated
