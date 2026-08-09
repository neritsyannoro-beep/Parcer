"""Реестр источников: RSS-ленты, Reddit и поисковые запросы Google News.

`tier` задаёт авторитетность источника (влияет на скор):
    1 — деловые/профильные редакции, редко пишут мусор
    2 — массовые крипто-медиа
    3 — агрегаторы, соцсети, шум с высокой скоростью

`kind` влияет на то, как обрабатывается запись:
    news    — обычная новость
    social  — обсуждение (Reddit), сильнее штрафуется за отсутствие сигналов
    search  — Google News по запросу, даёт широкое покрытие «всех источников»
"""

from __future__ import annotations

# --------------------------------------------------------------------------
# Профильные редакции и медиа
# --------------------------------------------------------------------------
RSS_SOURCES: list[dict] = [
    # tier 1
    {"name": "The Block", "url": "https://www.theblock.co/rss.xml", "tier": 1},
    {"name": "CoinDesk", "url": "https://www.coindesk.com/arc/outboundfeeds/rss/", "tier": 1},
    {"name": "Blockworks", "url": "https://blockworks.co/feed", "tier": 1},
    {"name": "DL News", "url": "https://www.dlnews.com/arc/outboundfeeds/rss/", "tier": 1},
    {"name": "The Defiant", "url": "https://thedefiant.io/api/feed", "tier": 1},
    {"name": "Protos", "url": "https://protos.com/feed/", "tier": 1},
    {"name": "Bitcoin Magazine", "url": "https://bitcoinmagazine.com/feed", "tier": 1},

    # tier 2
    {"name": "Cointelegraph", "url": "https://cointelegraph.com/rss", "tier": 2},
    {"name": "Decrypt", "url": "https://decrypt.co/feed", "tier": 2},
    {"name": "CryptoSlate", "url": "https://cryptoslate.com/feed/", "tier": 2},
    {"name": "BeInCrypto", "url": "https://beincrypto.com/feed/", "tier": 2},
    {"name": "Crypto Briefing", "url": "https://cryptobriefing.com/feed/", "tier": 2},
    {"name": "Cryptonews", "url": "https://cryptonews.com/news/feed/", "tier": 2},
    {"name": "CoinGape", "url": "https://coingape.com/feed/", "tier": 2},
    {"name": "U.Today", "url": "https://u.today/rss", "tier": 2},
    {"name": "Coinspeaker", "url": "https://www.coinspeaker.com/feed/", "tier": 2},
    {"name": "CoinJournal", "url": "https://coinjournal.net/feed/", "tier": 2},
    {"name": "AMBCrypto", "url": "https://ambcrypto.com/feed/", "tier": 2},

    # tier 3 — быстрые, но шумные
    {"name": "NewsBTC", "url": "https://www.newsbtc.com/feed/", "tier": 3},
    {"name": "Bitcoinist", "url": "https://bitcoinist.com/feed/", "tier": 3},
    {"name": "CryptoPotato", "url": "https://cryptopotato.com/feed/", "tier": 3},
    {"name": "ZyCrypto", "url": "https://zycrypto.com/feed/", "tier": 3},
    {"name": "The Daily Hodl", "url": "https://dailyhodl.com/feed/", "tier": 3},
    {"name": "CryptoDaily", "url": "https://cryptodaily.co.uk/feed", "tier": 3},
]

# --------------------------------------------------------------------------
# Reddit — раньше всех ловит слухи, инсайды и новые монеты
# --------------------------------------------------------------------------
REDDIT_SOURCES: list[dict] = [
    {"name": "r/CryptoCurrency", "url": "https://www.reddit.com/r/CryptoCurrency/hot/.rss", "tier": 3},
    {"name": "r/CryptoMarkets", "url": "https://www.reddit.com/r/CryptoMarkets/hot/.rss", "tier": 3},
    {"name": "r/Bitcoin", "url": "https://www.reddit.com/r/Bitcoin/hot/.rss", "tier": 3},
    {"name": "r/ethereum", "url": "https://www.reddit.com/r/ethereum/hot/.rss", "tier": 3},
    {"name": "r/defi", "url": "https://www.reddit.com/r/defi/hot/.rss", "tier": 3},
    {"name": "r/altcoin", "url": "https://www.reddit.com/r/altcoin/new/.rss", "tier": 3},
    {"name": "r/CryptoMoonShots", "url": "https://www.reddit.com/r/CryptoMoonShots/new/.rss", "tier": 3},
    {"name": "r/SatoshiStreetBets", "url": "https://www.reddit.com/r/SatoshiStreetBets/hot/.rss", "tier": 3},
]

# --------------------------------------------------------------------------
# Google News RSS — покрывает «все остальные ресурсы» одним запросом.
# Это то, что закрывает требование «новости из всех источников»: сюда попадают
# Reuters, Bloomberg, Forbes, локальные издания и всё, что индексирует Google.
# --------------------------------------------------------------------------
GOOGLE_NEWS_QUERIES: list[dict] = [
    {"name": "Google: whales", "q": "crypto whale accumulation OR whale transfer", "tier": 2},
    {"name": "Google: on-chain", "q": "on-chain data smart money crypto", "tier": 2},
    {"name": "Google: listings", "q": "Binance OR Coinbase OR Upbit listing new token", "tier": 2},
    {"name": "Google: new coins", "q": "new crypto token launch OR mainnet OR TGE", "tier": 2},
    {"name": "Google: airdrops", "q": "crypto airdrop snapshot eligibility", "tier": 3},
    {"name": "Google: regulation", "q": "SEC OR CFTC OR MiCA crypto ruling OR approval", "tier": 1},
    {"name": "Google: ETF flows", "q": "bitcoin ETF inflows OR outflows BlackRock", "tier": 1},
    {"name": "Google: hacks", "q": "crypto hack OR exploit OR drained protocol", "tier": 1},
    {"name": "Google: liquidations", "q": "crypto liquidations open interest funding rate", "tier": 2},
    {"name": "Google: treasuries", "q": "company buys bitcoin treasury OR ethereum treasury", "tier": 1},
    {"name": "Google: insiders", "q": "crypto insider leak OR confidential OR rumor", "tier": 2},
    {"name": "Google: macro", "q": "Fed rate decision impact bitcoin", "tier": 2},
]


def google_news_url(query: str, window: str = "1d") -> str:
    """Google News RSS по запросу, ограниченный последними сутками."""
    from urllib.parse import quote_plus

    q = quote_plus(f"{query} when:{window}")
    return f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"


def all_feeds() -> list[dict]:
    """Полный список фидов для загрузки."""
    feeds: list[dict] = []
    for s in RSS_SOURCES:
        feeds.append({**s, "kind": "news"})
    for s in REDDIT_SOURCES:
        feeds.append({**s, "kind": "social"})
    for s in GOOGLE_NEWS_QUERIES:
        feeds.append(
            {
                "name": s["name"],
                "url": google_news_url(s["q"]),
                "tier": s["tier"],
                "kind": "search",
            }
        )
    return feeds
