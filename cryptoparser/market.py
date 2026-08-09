"""Рыночные и ончейн-сигналы: киты, новые монеты, потоки денег.

Всё на бесплатных публичных API без ключей (CoinGecko, DefiLlama).
Etherscan-модуль включается, только если задан ETHERSCAN_API_KEY.
Любой сбой модуля не влияет на остальную ленту — возвращается пустой список.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import requests

from . import config

log = logging.getLogger(__name__)

CG_BASE = "https://api.coingecko.com/api/v3"
LLAMA_BASE = "https://api.llama.fi"
STABLE_BASE = "https://stablecoins.llama.fi"

# Известные горячие кошельки биржи — публичная информация из блок-эксплореров.
EXCHANGE_WALLETS = {
    "0x28c6c06298d514db089934071355e5743bf21d60": "Binance 14",
    "0x21a31ee1afc51d94c2efccaa2092ad1028285549": "Binance 15",
    "0xdfd5293d8e347dfe59e90efd55b2956a1343963d": "Binance 16",
    "0x71660c4005ba85c37ccec55d0c4493e66fe775d3": "Coinbase 1",
    "0x503828976d22510aad0201ac7ec88293211d23da": "Coinbase 2",
    "0x2910543af39aba0cd09dbb2d50200b3e800a63d2": "Kraken 1",
}


def _get(url: str, params: dict | None = None, timeout: int | None = None) -> dict | list | None:
    """GET с мягкой обработкой ошибок — модули не должны ронять запуск."""
    headers = {"User-Agent": config.USER_AGENT, "Accept": "application/json"}
    if config.COINGECKO_API_KEY and "coingecko" in url:
        headers["x-cg-demo-api-key"] = config.COINGECKO_API_KEY
    try:
        resp = requests.get(
            url, params=params, headers=headers,
            timeout=timeout or config.HTTP_TIMEOUT,
        )
        if resp.status_code >= 400:
            log.warning("API %s -> HTTP %s", url, resp.status_code)
            return None
        return resp.json()
    except Exception as exc:  # noqa: BLE001
        log.warning("API %s упал: %s", url, exc)
        return None


def _signal(
    title: str,
    summary: str,
    url: str,
    tags: list[str],
    bonus: float,
    source: str,
    uid: str,
) -> dict:
    now = datetime.now(timezone.utc)
    return {
        "id": f"sig-{uid}",
        "title": title,
        "summary": summary,
        "url": url,
        "source": source,
        "feed_name": source,
        "tier": 1,
        "kind": "signal",
        "published": now.isoformat(),
        "published_ts": now.timestamp(),
        "onchain_bonus": bonus,
        "forced_tags": tags,
    }


# --------------------------------------------------------------------------- CoinGecko


def trending_coins() -> list[dict]:
    """Что сейчас ищут — самый быстрый индикатор внимания рынка."""
    data = _get(f"{CG_BASE}/search/trending")
    if not isinstance(data, dict):
        return []
    out: list[dict] = []
    for entry in (data.get("coins") or [])[:7]:
        item = entry.get("item") or {}
        name, symbol = item.get("name"), (item.get("symbol") or "").upper()
        if not name:
            continue
        pct = None
        try:
            pct = float(item["data"]["price_change_percentage_24h"]["usd"])
        except Exception:  # noqa: BLE001
            pass
        rank = item.get("market_cap_rank")
        pct_txt = f", {pct:+.1f}% за 24ч" if pct is not None else ""
        rank_txt = f"место по капитализации: {rank}" if rank else "вне топ-1000 по капитализации"
        out.append(
            _signal(
                title=f"Trending: {name} ({symbol}) в топе поиска CoinGecko{pct_txt}",
                summary=f"{name} растёт по числу запросов — {rank_txt}. "
                        f"Ранний сигнал внимания розницы.",
                url=f"https://www.coingecko.com/en/coins/{item.get('id', '')}",
                tags=["trends"],
                bonus=6.0 if (pct or 0) > 15 else 4.0,
                source="CoinGecko Trending",
                uid=f"trend-{item.get('id')}",
            )
        )
    return out


def top_gainers() -> list[dict]:
    """Резкие движения в ликвидных монетах — почти всегда есть причина."""
    data = _get(
        f"{CG_BASE}/coins/markets",
        params={
            "vs_currency": "usd",
            "order": "market_cap_desc",
            "per_page": 250,
            "page": 1,
            "price_change_percentage": "24h",
        },
    )
    if not isinstance(data, list):
        return []

    movers: list[tuple[float, dict]] = []
    for c in data:
        pct = c.get("price_change_percentage_24h_in_currency")
        mcap = c.get("market_cap") or 0
        vol = c.get("total_volume") or 0
        if pct is None or mcap < 20_000_000 or vol < 3_000_000:
            continue
        if abs(pct) >= 18:
            movers.append((abs(pct), c))

    movers.sort(key=lambda x: -x[0])
    out: list[dict] = []
    for _, c in movers[:6]:
        pct = c["price_change_percentage_24h_in_currency"]
        direction = "растёт" if pct > 0 else "падает"
        vol_ratio = (c.get("total_volume") or 0) / max(1, c.get("market_cap") or 1)
        vol_note = (
            f" Объём — {vol_ratio * 100:.0f}% от капитализации, это аномально высоко."
            if vol_ratio > 0.3 else ""
        )
        out.append(
            _signal(
                title=f"{c.get('name')} ({(c.get('symbol') or '').upper()}) {direction} на {abs(pct):.1f}% за 24ч",
                summary=f"Цена ${c.get('current_price')}, капитализация "
                        f"${(c.get('market_cap') or 0) / 1e6:.0f}M, объём "
                        f"${(c.get('total_volume') or 0) / 1e6:.0f}M.{vol_note}",
                url=f"https://www.coingecko.com/en/coins/{c.get('id', '')}",
                tags=["trends"],
                bonus=8.0 if abs(pct) >= 35 else 5.5,
                source="CoinGecko Markets",
                uid=f"mover-{c.get('id')}-{datetime.now(timezone.utc):%Y%m%d%H}",
            )
        )
    return out


def new_coins(known_ids: set[str]) -> tuple[list[dict], set[str]]:
    """Новые монеты = дифф списка CoinGecko со прошлым запуском.

    Возвращает (сигналы, полный набор id для сохранения). На первом запуске
    сигналов нет — только фиксируется базовый снимок.
    """
    data = _get(f"{CG_BASE}/coins/list", timeout=45)
    if not isinstance(data, list) or len(data) < 1000:
        return [], known_ids

    current = {c["id"]: c for c in data if c.get("id")}
    current_ids = set(current)

    if not known_ids:
        log.info("новые монеты: сохранён базовый снимок (%d монет)", len(current_ids))
        return [], current_ids

    fresh = current_ids - known_ids
    log.info("новые монеты: +%d к прошлому снимку", len(fresh))

    out: list[dict] = []
    for coin_id in sorted(fresh)[:12]:
        c = current[coin_id]
        symbol = (c.get("symbol") or "").upper()
        out.append(
            _signal(
                title=f"Новая монета в листинге CoinGecko: {c.get('name')} ({symbol})",
                summary="Токен только что добавлен в базу CoinGecko — обычно это "
                        "происходит в первые дни после запуска. Проверь контракт "
                        "и ликвидность перед публикацией.",
                url=f"https://www.coingecko.com/en/coins/{coin_id}",
                tags=["new_coins"],
                bonus=6.5,
                source="CoinGecko Listings",
                uid=f"newcoin-{coin_id}",
            )
        )
    return out, current_ids


# --------------------------------------------------------------------------- DefiLlama


def stablecoin_flows() -> list[dict]:
    """Приток/отток стейблов — это буквально деньги, входящие в рынок."""
    data = _get(f"{STABLE_BASE}/stablecoins", params={"includePrices": "false"})
    if not isinstance(data, dict):
        return []

    total_now = total_prev = 0.0
    movers: list[tuple[float, str, float]] = []
    for coin in data.get("peggedAssets") or []:
        try:
            now_v = float(coin["circulating"]["peggedUSD"])
            prev_v = float(coin["circulatingPrevDay"]["peggedUSD"])
        except Exception:  # noqa: BLE001
            continue
        total_now += now_v
        total_prev += prev_v
        delta = now_v - prev_v
        if abs(delta) > 50_000_000:
            movers.append((delta, coin.get("symbol") or coin.get("name") or "?", now_v))

    out: list[dict] = []
    total_delta = total_now - total_prev
    if abs(total_delta) > 150_000_000:
        direction = "приток" if total_delta > 0 else "отток"
        out.append(
            _signal(
                title=f"Стейблкоины: {direction} ${abs(total_delta) / 1e9:.2f}B за сутки",
                summary=f"Совокупная эмиссия стейблкоинов — ${total_now / 1e9:.1f}B. "
                        f"{'Новые деньги заходят на рынок' if total_delta > 0 else 'Деньги выходят из рынка'} — "
                        f"опережающий индикатор для рисковых активов.",
                url="https://defillama.com/stablecoins",
                tags=["onchain", "trends"],
                bonus=9.0 if abs(total_delta) > 1e9 else 6.0,
                source="DefiLlama Stablecoins",
                uid=f"stables-{datetime.now(timezone.utc):%Y%m%d%H}",
            )
        )

    movers.sort(key=lambda x: -abs(x[0]))
    for delta, symbol, now_v in movers[:2]:
        verb = "выпущено" if delta > 0 else "сожжено"
        out.append(
            _signal(
                title=f"{symbol}: {verb} ${abs(delta) / 1e6:.0f}M за 24 часа",
                summary=f"Текущая эмиссия {symbol} — ${now_v / 1e9:.2f}B. Крупные минты "
                        f"часто идут перед покупками на споте.",
                url="https://defillama.com/stablecoins",
                tags=["onchain", "whales"],
                bonus=7.0,
                source="DefiLlama Stablecoins",
                uid=f"stable-{symbol}-{datetime.now(timezone.utc):%Y%m%d%H}",
            )
        )
    return out


def tvl_movers() -> list[dict]:
    """Резкий рост TVL — деньги идут в конкретный протокол раньше новостей."""
    data = _get(f"{LLAMA_BASE}/protocols", timeout=45)
    if not isinstance(data, list):
        return []

    candidates: list[tuple[float, dict]] = []
    for p in data:
        tvl = p.get("tvl") or 0
        chg = p.get("change_1d")
        if not isinstance(chg, (int, float)) or tvl < 30_000_000:
            continue
        if abs(chg) >= 20:
            candidates.append((abs(chg), p))

    candidates.sort(key=lambda x: -x[0])
    out: list[dict] = []
    for _, p in candidates[:4]:
        chg = p["change_1d"]
        direction = "вырос" if chg > 0 else "упал"
        out.append(
            _signal(
                title=f"TVL {p.get('name')} {direction} на {abs(chg):.0f}% за сутки "
                      f"(${(p.get('tvl') or 0) / 1e6:.0f}M)",
                summary=f"Категория: {p.get('category') or 'DeFi'}, сети: "
                        f"{', '.join((p.get('chains') or [])[:3])}. "
                        f"{'Приток капитала' if chg > 0 else 'Вывод капитала'} такого размера "
                        f"обычно опережает новостной фон.",
                url=p.get("url") or f"https://defillama.com/protocol/{p.get('slug', '')}",
                tags=["onchain", "whales"],
                bonus=7.5 if abs(chg) >= 40 else 5.5,
                source="DefiLlama TVL",
                uid=f"tvl-{p.get('slug')}-{datetime.now(timezone.utc):%Y%m%d%H}",
            )
        )
    return out


# --------------------------------------------------------------------------- Etherscan


def whale_transfers() -> list[dict]:
    """Крупные переводы ETH на/с горячих кошельков бирж (нужен ETHERSCAN_API_KEY)."""
    if not config.ETHERSCAN_API_KEY:
        return []

    out: list[dict] = []
    for address, label in list(EXCHANGE_WALLETS.items())[:3]:
        data = _get(
            "https://api.etherscan.io/api",
            params={
                "module": "account", "action": "txlist", "address": address,
                "startblock": 0, "endblock": 99999999, "page": 1, "offset": 25,
                "sort": "desc", "apikey": config.ETHERSCAN_API_KEY,
            },
        )
        if not isinstance(data, dict) or data.get("status") != "1":
            continue
        for tx in data.get("result") or []:
            try:
                eth = int(tx["value"]) / 1e18
                ts = int(tx["timeStamp"])
            except Exception:  # noqa: BLE001
                continue
            age_h = (datetime.now(timezone.utc).timestamp() - ts) / 3600
            if eth < 2000 or age_h > 12:
                continue
            inbound = (tx.get("to") or "").lower() == address
            direction = f"на {label}" if inbound else f"с {label}"
            meaning = (
                "депозит на биржу — часто предвестник продажи"
                if inbound else "вывод с биржи — обычно накопление"
            )
            out.append(
                _signal(
                    title=f"🐋 {eth:,.0f} ETH переведено {direction}",
                    summary=f"Крупный перевод (~${eth * 3000 / 1e6:.1f}M по грубой оценке): {meaning}.",
                    url=f"https://etherscan.io/tx/{tx.get('hash')}",
                    tags=["whales", "onchain"],
                    bonus=9.0 if eth >= 10000 else 7.0,
                    source="Etherscan",
                    uid=f"whale-{tx.get('hash')}",
                )
            )
    return out[:8]


def collect(known_coin_ids: set[str]) -> tuple[list[dict], set[str]]:
    """Собирает все рыночные сигналы. Возвращает (сигналы, новый снимок монет)."""
    if not config.ENABLE_MARKET_SIGNALS:
        return [], known_coin_ids

    signals: list[dict] = []
    for fn in (trending_coins, top_gainers, stablecoin_flows, tvl_movers, whale_transfers):
        try:
            found = fn()
            log.info("сигналы %-18s %d", fn.__name__, len(found))
            signals.extend(found)
        except Exception as exc:  # noqa: BLE001
            log.warning("модуль %s упал: %s", fn.__name__, exc)

    try:
        fresh, snapshot = new_coins(known_coin_ids)
        signals.extend(fresh)
    except Exception as exc:  # noqa: BLE001
        log.warning("модуль new_coins упал: %s", exc)
        snapshot = known_coin_ids

    return signals, snapshot
