"""Точка входа: собрать → отранжировать → записать ленту.

    python -m cryptoparser.main               # полный запуск
    python -m cryptoparser.main --no-market   # только новости, без ончейн-модулей
    python -m cryptoparser.main --fixtures tests/fixtures  # офлайн-прогон
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

from . import config, llm, market, render, score, store
from .sources import all_feeds


def setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s  %(levelname)-7s %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stdout,
    )


def load_fixtures(path: Path) -> list[dict]:
    """Читает заранее сохранённые записи — для тестов без сети."""
    items: list[dict] = []
    for file in sorted(path.glob("*.json")):
        items.extend(json.loads(file.read_text(encoding="utf-8")))
    return items


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Парсер крипто-новостей")
    parser.add_argument("--no-market", action="store_true",
                        help="не запрашивать рыночные и ончейн-сигналы")
    parser.add_argument("--fixtures", type=Path,
                        help="взять записи из каталога с JSON-фикстурами вместо сети")
    parser.add_argument("--out", type=Path, help="куда писать feed.json")
    parser.add_argument("--limit", type=int, help="максимум записей в ленте")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    setup_logging(args.verbose)
    log = logging.getLogger("cryptoparser")
    started = time.time()

    if args.limit:
        config.MAX_ITEMS_IN_FEED = args.limit

    with store.connect() as conn:
        seen = store.get_seen_ids(conn)
        log.info("в базе уже %d записей", len(seen))

        # 1. Новости
        if args.fixtures:
            raw = load_fixtures(args.fixtures)
            log.info("загружено %d записей из фикстур", len(raw))
        else:
            from .fetch import fetch_all  # импорт здесь: фикстурам сеть не нужна
            raw = fetch_all(all_feeds())

        # 2. Рыночные и ончейн-сигналы
        if not args.no_market and not args.fixtures:
            snapshot_before = store.get_coin_snapshot(conn)
            signals, snapshot_after = market.collect(snapshot_before)
            raw.extend(signals)
            if snapshot_after != snapshot_before:
                store.save_coin_snapshot(conn, snapshot_after)

        if not raw:
            log.error("нечего обрабатывать — ни одной записи не загружено")
            return 1

        # 3. Скоринг, кластеризация, тиры
        ranked = score.rank(raw)
        ranked = llm.rerank(ranked)
        ranked = score.assign_tiers(ranked)

        hot = sum(1 for i in ranked[: config.MAX_ITEMS_IN_FEED]
                  if i["tier_label"] == "hot")

        # 4. Запись ленты и истории
        feed = render.build_feed(
            ranked, seen,
            stats_extra={"fetched": len(raw), "feeds": len(all_feeds())},
        )
        render.write_feed(feed, args.out)

        store.upsert_items(conn, ranked[: config.MAX_ITEMS_IN_FEED])
        removed = store.prune(conn)
        store.record_run(conn, len(raw), len(feed["items"]), hot, time.time() - started)

    log.info(
        "готово за %.1f с: %d в ленте (🔥 %d), новых %d, удалено из истории %d",
        time.time() - started, feed["stats"]["total"], hot,
        feed["stats"]["new"], removed,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
