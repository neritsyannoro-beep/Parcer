"""Словари сигналов: что делает крипто-новость интересной.

Веса подобраны по принципу «сколько ценности несёт факт для инфлюенсера»:
чем реже и чем сильнее новость двигает рынок, тем выше вес.
"""

from __future__ import annotations

# Ярлыки категорий (id -> человекочитаемое имя для интерфейса).
TAG_LABELS: dict[str, str] = {
    "insides": "Инсайды",
    "whales": "Киты",
    "new_coins": "Новые монеты",
    "listings": "Листинги",
    "trends": "Тренды",
    "regulation": "Регуляторы",
    "security": "Взломы",
    "institutions": "Институционалы",
    "macro": "Макро",
    "onchain": "Ончейн",
}

TAG_EMOJI: dict[str, str] = {
    "insides": "🕵️",
    "whales": "🐋",
    "new_coins": "🌱",
    "listings": "📈",
    "trends": "🔥",
    "regulation": "⚖️",
    "security": "🚨",
    "institutions": "🏦",
    "macro": "🌍",
    "onchain": "⛓️",
}

# --------------------------------------------------------------------------
# Ключевые фразы: tag -> [(фраза, вес)]
# Фразы ищутся как подстроки по границам слов, регистр не важен.
# --------------------------------------------------------------------------
SIGNALS: dict[str, list[tuple[str, float]]] = {
    "insides": [
        ("insider", 9), ("leaked", 10), ("leak", 7), ("confidential", 9),
        ("people familiar", 11), ("sources say", 9), ("according to sources", 10),
        ("unnamed source", 9), ("rumor", 6), ("rumour", 6), ("scoop", 8),
        ("exclusive", 7), ("behind closed doors", 8), ("internal memo", 10),
        ("whistleblower", 10), ("court filing", 8), ("unsealed", 9),
        ("secretly", 8), ("quietly", 5), ("ahead of announcement", 9),
    ],
    "whales": [
        ("whale", 10), ("whales", 10), ("large holder", 8), ("mega whale", 12),
        ("accumulat", 8),  # accumulate / accumulating / accumulation
        ("smart money", 9), ("dormant wallet", 12), ("dormant address", 12),
        ("moved to exchange", 9), ("exchange outflow", 9), ("exchange inflow", 9),
        ("withdrew from", 7), ("deposited to binance", 9), ("wallet transferred", 8),
        ("accumulation zone", 6), ("top holders", 7), ("insider wallet", 11),
        ("early investor sold", 9), ("team wallet", 8), ("unstaked", 7),
        ("accumulated", 8), ("накопление", 8),
    ],
    "new_coins": [
        ("token launch", 9), ("mainnet launch", 9), ("goes live", 6),
        ("tge", 10), ("token generation event", 10), ("presale", 7),
        ("ido", 7), ("ico", 6), ("fair launch", 8), ("airdrop", 9),
        ("snapshot", 6), ("testnet incentiv", 8), ("points program", 7),
        ("new token", 8), ("debut", 6), ("launchpad", 8), ("stealth launch", 9),
        ("first trading day", 7), ("genesis", 5),
    ],
    "listings": [
        ("will list", 12), ("lists", 7), ("listing", 9), ("perpetual futures", 8),
        ("spot trading", 8), ("coinbase roadmap", 12), ("binance listing", 13),
        ("upbit listing", 11), ("delisting", 10), ("delist", 10),
        ("trading pairs", 6), ("now available on", 7), ("added support for", 6),
    ],
    "trends": [
        ("all-time high", 11), ("all time high", 11), ("ath", 8),
        ("surge", 7), ("surges", 7), ("soar", 7), ("skyrocket", 8),
        ("plunge", 8), ("crash", 9), ("collapse", 9), ("tumble", 7),
        ("liquidation", 10), ("liquidations", 10), ("short squeeze", 10),
        ("long squeeze", 10), ("funding rate", 8), ("open interest", 8),
        ("breakout", 7), ("bull run", 7), ("bear market", 6),
        ("dominance", 6), ("outperform", 6), ("rally", 6), ("selloff", 8),
        ("capitulation", 9), ("golden cross", 7), ("death cross", 7),
        ("altseason", 9), ("rotation", 6), ("volume spike", 8),
    ],
    "regulation": [
        ("sec approves", 15), ("sec approval", 14), ("sec sues", 13),
        ("sec lawsuit", 12), ("lawsuit", 8), ("subpoena", 11),
        ("indicted", 12), ("indictment", 12), ("guilty", 10),
        ("settlement", 9), ("fined", 8), ("ban", 8), ("bans", 8),
        ("crackdown", 10), ("etf approved", 15), ("etf approval", 14),
        ("etf filing", 10), ("s-1", 9), ("19b-4", 10),
        ("cftc", 8), ("mica", 8), ("regulator", 6), ("legislation", 7),
        ("executive order", 11), ("congress", 7), ("senate", 7),
        ("tax", 6), ("license", 6), ("investigation", 9),
    ],
    "security": [
        ("hack", 13), ("hacked", 13), ("exploit", 12), ("exploited", 12),
        ("drained", 12), ("stolen", 11), ("breach", 10), ("rug pull", 12),
        ("rugged", 11), ("scam", 8), ("vulnerability", 9), ("backdoor", 11),
        ("private key", 9), ("bridge attack", 13), ("flash loan attack", 12),
        ("halted withdrawals", 14), ("insolvent", 14), ("bankruptcy", 13),
        ("depeg", 13), ("depegged", 13), ("frozen funds", 10),
        ("phishing", 7), ("post-mortem", 7),
    ],
    "institutions": [
        ("blackrock", 12), ("fidelity", 9), ("grayscale", 9), ("ark invest", 8),
        ("vanguard", 9), ("jpmorgan", 9), ("goldman sachs", 9),
        ("etf inflow", 12), ("etf outflow", 11), ("net inflow", 9),
        ("institutional", 7), ("pension fund", 10), ("sovereign wealth", 11),
        ("treasury strategy", 10), ("buys bitcoin", 11), ("bought bitcoin", 11),
        ("adds bitcoin", 10), ("microstrategy", 10), ("strategy inc", 8),
        ("corporate treasury", 10), ("custody", 6), ("nasdaq-listed", 8),
        ("ipo", 8), ("acquisition", 9), ("merger", 9), ("raises", 7),
        ("funding round", 8), ("series a", 6), ("valuation", 6),
    ],
    "macro": [
        ("federal reserve", 9), ("the fed", 8), ("rate cut", 11),
        ("rate hike", 10), ("interest rates", 8), ("cpi", 9), ("inflation", 7),
        ("jobs report", 7), ("recession", 8), ("tariff", 8),
        ("dollar index", 7), ("dxy", 7), ("treasury yields", 8),
        ("quantitative easing", 9), ("liquidity injection", 9),
        ("gold", 5), ("s&p 500", 6), ("nasdaq", 5),
    ],
    "onchain": [
        ("on-chain", 8), ("onchain", 8), ("tvl", 8), ("stablecoin supply", 11),
        ("net flows", 9), ("mint", 6), ("minted", 7), ("burned", 7),
        ("staking", 6), ("unstaking queue", 9), ("validator", 6),
        ("gas fees", 6), ("active addresses", 8), ("hashrate", 7),
        ("miner reserves", 9), ("realized profit", 8), ("supply shock", 11),
    ],
}

# --------------------------------------------------------------------------
# Крупные имена и тикеры — упоминание повышает охват новости.
# --------------------------------------------------------------------------
BIG_ENTITIES: dict[str, float] = {
    "bitcoin": 4, "btc": 4, "ethereum": 4, "eth": 4,
    "solana": 3.5, "sol": 3, "xrp": 3, "ripple": 3,
    "binance": 4, "coinbase": 4, "tether": 4, "usdt": 3.5, "usdc": 3,
    "circle": 3, "kraken": 3, "okx": 2.5, "bybit": 2.5, "bitget": 2,
    "blackrock": 5, "trump": 4.5, "sec": 4, "fed": 3.5,
    "microstrategy": 3.5, "tesla": 3, "paypal": 2.5, "visa": 2.5,
    "nvidia": 2.5, "elon musk": 4, "cz": 3, "saylor": 3.5,
    "vitalik": 3.5, "solana etf": 4, "hyperliquid": 3, "base": 2,
    "arbitrum": 2.5, "sui": 2.5, "ton": 2.5, "doge": 3, "dogecoin": 3,
    "pepe": 2.5, "shiba": 2.5, "chainlink": 2.5, "link": 1.5,
    "avalanche": 2.5, "polygon": 2.5, "cardano": 2.5, "ada": 2,
    "monero": 2, "litecoin": 2, "tron": 2.5, "aave": 2.5, "uniswap": 3,
    "lido": 2.5, "ondo": 2, "worldcoin": 2.5, "polymarket": 3,
}

# --------------------------------------------------------------------------
# Штрафы: клик-бейт, реклама и «вода», которую инфлюенсеру публиковать нельзя.
# --------------------------------------------------------------------------
PENALTIES: dict[str, float] = {
    "sponsored": -25, "press release": -22, "partnered content": -25,
    "advertorial": -25, "paid post": -25, "disclaimer": -8,
    "price prediction": -14, "price analysis": -9,
    "coins to buy": -18, "coins to watch": -14, "best crypto": -16,
    "top 5": -10, "top 10": -9, "top 3": -9,
    "here's why": -6, "here is why": -6, "what to expect": -6,
    "everything you need to know": -10, "explained": -5,
    "beginner": -8, "guide": -7, "how to buy": -14, "tutorial": -9,
    "giveaway": -20, "casino": -22, "betting": -14, "gambling": -18,
    "review": -8, "sponsored content": -25, "webinar": -12,
    "moon soon": -12, "1000x": -10, "to the moon": -10,
    "could hit": -7, "may hit": -7, "eyes": -4,
}

# Фразы, которые означают «это уже не новость, а пересказ».
STALE_MARKERS: dict[str, float] = {
    "weekly recap": -12, "daily digest": -10, "market wrap": -8,
    "week in review": -12, "roundup": -9, "recap": -8,
    "opinion": -7, "op-ed": -8, "interview": -5, "podcast": -8,
}
