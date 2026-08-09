"""Генератор фикстур для офлайн-прогона парсера.

Сеть в проверочных окружениях часто закрыта, поэтому набор реалистичных
заголовков позволяет проверить скоринг, кластеризацию и вёрстку без интернета.

    python tests/make_fixtures.py && python -m cryptoparser.main --fixtures tests/fixtures
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptoparser.fetch import make_id

OUT = Path(__file__).parent / "fixtures"

# (заголовок, источник, tier, kind, часов назад)
SAMPLES: list[tuple[str, str, int, str, float]] = [
    # --- должно попасть в «горячие» ---
    ("SEC approves spot Solana ETF applications from BlackRock and Fidelity",
     "The Block", 1, "news", 0.4),
    ("BlackRock's spot Solana ETF approved by SEC in landmark decision",
     "CoinDesk", 1, "news", 0.6),
    ("Breaking: SEC greenlights Solana ETFs, BlackRock and Fidelity first to launch",
     "Blockworks", 1, "news", 0.8),
    ("Dormant whale wallet moves 12,400 BTC worth $1.2B to Binance after 9 years",
     "CoinDesk", 1, "news", 1.2),
    ("Cross-chain bridge exploited for $210M in largest hack of the year",
     "The Block", 1, "news", 2.0),
    ("Leaked internal memo shows exchange halted withdrawals days before insolvency",
     "DL News", 1, "news", 3.0),
    ("Bitcoin surges 11% to new all-time high above $124,000 as ETF inflows hit $2.4B",
     "Cointelegraph", 2, "news", 1.5),

    # --- «интересные» ---
    ("Binance will list new Layer 2 token with spot trading pairs on Friday",
     "CoinGape", 2, "news", 2.4),
    ("Whale accumulation in ETH hits 3-month high as exchange outflows accelerate",
     "CryptoSlate", 2, "news", 4.0),
    ("Stablecoin supply grows $1.8B in a week, signaling fresh capital inflow",
     "Decrypt", 2, "news", 5.0),
    ("$840M in crypto liquidations hit traders as funding rates flip negative",
     "BeInCrypto", 2, "news", 3.5),
    ("Coinbase roadmap adds three new assets ahead of listing",
     "Decrypt", 2, "news", 6.0),
    ("MicroStrategy buys additional 4,200 bitcoin for $390M",
     "Bitcoin Magazine", 1, "news", 8.0),
    ("New token launch on Base draws $95M TVL in first 24 hours after fair launch",
     "The Defiant", 1, "news", 7.0),
    ("Fed signals rate cut in September, risk assets rally",
     "Cryptonews", 2, "news", 9.0),
    ("Sources say major market maker is quietly unwinding altcoin positions",
     "Protos", 1, "news", 5.5),
    ("Airdrop snapshot for restaking protocol confirmed for next week",
     "CryptoSlate", 2, "news", 10.0),

    # --- «средние» и мусор (должны уйти вниз) ---
    ("XRP price prediction: could XRP hit $10 this cycle?",
     "NewsBTC", 3, "news", 4.5),
    ("Top 5 altcoins to buy before the next bull run",
     "ZyCrypto", 3, "news", 6.5),
    ("Sponsored: new casino accepts crypto deposits with 200% bonus",
     "CryptoDaily", 3, "news", 3.0),
    ("Everything you need to know about crypto wallets: a beginner's guide",
     "Bitcoinist", 3, "news", 12.0),
    ("Weekly recap: what happened in crypto markets last week",
     "AMBCrypto", 3, "news", 20.0),
    ("What do you all think about the market right now?",
     "r/CryptoCurrency", 3, "social", 2.0),
    ("This new moonshot gem is going 1000x soon, do not miss it",
     "r/CryptoMoonShots", 3, "social", 1.0),
    ("Discussion: is Ethereum still undervalued in 2026?",
     "r/ethereum", 3, "social", 5.0),
    ("Solana network hits 4,200 TPS record during NFT mint",
     "U.Today", 2, "news", 14.0),
    ("Ethereum gas fees drop to 3 gwei as L2 activity shifts demand",
     "Blockworks", 1, "news", 16.0),
    ("Interview: exchange CEO on the future of regulation",
     "Decrypt", 2, "news", 18.0),
    ("Cardano developers propose new governance framework",
     "CoinJournal", 2, "news", 22.0),
]


def build() -> list[dict]:
    now = datetime.now(timezone.utc)
    items: list[dict] = []
    for i, (title, source, tier, kind, hours_ago) in enumerate(SAMPLES):
        published = now - timedelta(hours=hours_ago)
        url = f"https://example.test/{i}-{title[:40].lower().replace(' ', '-')}"
        items.append(
            {
                "id": make_id(url, title),
                "title": title,
                "url": url,
                "summary": "",
                "source": source,
                "feed_name": source,
                "tier": tier,
                "kind": kind,
                "published": published.isoformat(),
                "published_ts": published.timestamp(),
            }
        )
    return items


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    items = build()
    (OUT / "news.json").write_text(
        json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"записано {len(items)} фикстур в {OUT / 'news.json'}")
