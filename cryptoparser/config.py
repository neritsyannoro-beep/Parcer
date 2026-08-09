"""Все настраиваемые параметры парсера в одном месте.

Хочешь поменять поведение ранжирования — правь здесь, а не в score.py.
"""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DOCS_DIR = ROOT / "docs"
FEED_PATH = DOCS_DIR / "data" / "feed.json"
DB_PATH = DATA_DIR / "news.db"

# ---------------------------------------------------------------- сеть
HTTP_TIMEOUT = int(os.getenv("HTTP_TIMEOUT", "20"))
HTTP_RETRIES = int(os.getenv("HTTP_RETRIES", "2"))
MAX_WORKERS = int(os.getenv("MAX_WORKERS", "12"))
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

# ---------------------------------------------------------------- окна времени
# Новости старше этого срока в ленту не попадают (часы).
MAX_AGE_HOURS = int(os.getenv("MAX_AGE_HOURS", "48"))
# Период полураспада свежести: через столько часов бонус за свежесть падает вдвое.
RECENCY_HALF_LIFE_HOURS = float(os.getenv("RECENCY_HALF_LIFE_HOURS", "7"))
# Сколько дней держать историю в БД.
HISTORY_RETENTION_DAYS = int(os.getenv("HISTORY_RETENTION_DAYS", "30"))

# ---------------------------------------------------------------- размер ленты
MAX_ITEMS_IN_FEED = int(os.getenv("MAX_ITEMS_IN_FEED", "220"))
# Гарантированный минимум карточек в горячем блоке, даже если абсолютные
# пороги не набрались (чтобы лента никогда не выглядела пустой).
MIN_HOT = int(os.getenv("MIN_HOT", "6"))
MIN_INTERESTING = int(os.getenv("MIN_INTERESTING", "12"))

# ---------------------------------------------------------------- пороги тиров
TIER_HOT_THRESHOLD = float(os.getenv("TIER_HOT_THRESHOLD", "68"))
TIER_INTERESTING_THRESHOLD = float(os.getenv("TIER_INTERESTING_THRESHOLD", "42"))

# ---------------------------------------------------------------- веса скоринга
WEIGHTS = {
    "source_authority": 1.0,   # 0..15
    "keywords": 1.0,           # 0..55, основной сигнал
    "magnitude": 1.0,          # 0..18, размер числа в заголовке ($2.1B и т.п.)
    "entities": 1.0,           # 0..12, крупные имена и тикеры
    "recency": 1.0,            # 0..14
    "corroboration": 1.0,      # 0..14, сколько источников написали об этом же
    "onchain_bonus": 1.0,      # 0..10, для сигналов из ончейн-модулей
}

# Порог схожести заголовков для склейки в один сюжет (0..1).
# Метрика — половина Jaccard плюс половина перекрытия, см. score._similarity.
# Ниже 0.4 начинают липнуть разные новости про один и тот же тикер.
CLUSTER_SIMILARITY = float(os.getenv("CLUSTER_SIMILARITY", "0.5"))

# ---------------------------------------------------------------- опциональные ключи
# Всё работает и без них — модули просто тихо отключаются.
ETHERSCAN_API_KEY = os.getenv("ETHERSCAN_API_KEY", "").strip()
COINGECKO_API_KEY = os.getenv("COINGECKO_API_KEY", "").strip()
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()

# LLM-переранжирование топа (стоит денег в API, по умолчанию выключено).
USE_LLM_RERANK = os.getenv("USE_LLM_RERANK", "0") == "1"
LLM_MODEL = os.getenv("LLM_MODEL", "claude-sonnet-5")
LLM_RERANK_TOP_N = int(os.getenv("LLM_RERANK_TOP_N", "30"))

# Включать ли ончейн/рыночные модули.
ENABLE_MARKET_SIGNALS = os.getenv("ENABLE_MARKET_SIGNALS", "1") == "1"
