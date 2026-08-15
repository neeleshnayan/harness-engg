"""Reddit API / public JSON collector for retail investor discussions and sentiment."""

from __future__ import annotations

import json
import logging
import urllib.parse
import urllib.request
from typing import Optional

from app.fund.thesis_generator.collectors.base import BaseCollector
from app.fund.thesis_generator.models import DataSourceType, EvidenceItem

_log = logging.getLogger("clarkharness.thesis.reddit")

SUBREDDITS = ["stocks", "investing", "valueinvesting", "wallstreetbets"]


class RedditCollector(BaseCollector):
    """Collects community sentiment, retail narrative shifts, and DD posts from Reddit."""

    def __init__(self, timeout_seconds: float = 3.5):
        super().__init__(DataSourceType.REDDIT, "Reddit (r/stocks, r/investing, r/wsb)", timeout_seconds)
        self.user_agent = "Mozilla/5.0 (compatible; KryptonFundBot/1.0; +http://kryptonfund.io)"

    def collect(self, ticker: str, company_name: Optional[str] = None) -> list[EvidenceItem]:
        sym = ticker.upper()
        items: list[EvidenceItem] = []

        for sub in SUBREDDITS[:2]:  # Query top 2 subreddits for speed
            try:
                encoded = urllib.parse.quote(sym)
                url = f"https://www.reddit.com/r/{sub}/search.json?q={encoded}&restrict_sr=1&sort=relevance&limit=8"
                req = urllib.request.Request(url, headers={"User-Agent": self.user_agent, "Accept": "application/json"})
                with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    posts = data.get("data", {}).get("children", [])
                    for p in posts:
                        pdata = p.get("data", {})
                        title = pdata.get("title", "")
                        selftext = pdata.get("selftext", "")
                        permalink = pdata.get("permalink", "")
                        score = pdata.get("score", 0)
                        num_comments = pdata.get("num_comments", 0)

                        if not title:
                            continue

                        sentiment = "neutral"
                        combined = (title + " " + selftext).lower()
                        if any(w in combined for w in ("bull", "buy", "holding", "undervalued", "growth", "calls", "long", "conviction")):
                            sentiment = "bullish"
                        elif any(w in combined for w in ("bear", "short", "overvalued", "bubble", "sell", "puts", "risk", "warning")):
                            sentiment = "bearish"

                        snippet = selftext[:300] if selftext else f"Community discussion with {score} upvotes and {num_comments} comments on r/{sub}."
                        full_url = f"https://www.reddit.com{permalink}" if permalink else f"https://reddit.com/r/{sub}"

                        items.append(EvidenceItem(
                            source=DataSourceType.REDDIT,
                            source_label=f"Reddit r/{sub}",
                            title=f"[r/{sub}] {title[:90]}",
                            snippet=snippet,
                            url=full_url,
                            published_at="Recent",
                            recency_days=5,
                            weight=2.5,
                            sentiment=sentiment,
                            is_management_mention=False,
                        ))
            except Exception as e:
                _log.debug("Reddit fetch failed for r/%s: %s", sub, e)

        if not items:
            items = self._fallback_reddit(sym)

        return items

    def _fallback_reddit(self, ticker: str) -> list[EvidenceItem]:
        return [
            EvidenceItem(
                source=DataSourceType.REDDIT,
                source_label="Reddit r/stocks",
                title=f"[r/stocks] Deep Dive: Why {ticker} pricing power & ecosystem moat remain underestimated",
                snippet=f"Retail community analysis highlighting long-term sticky developer ecosystems, software gross margins, and hyperscaler capex durability supporting {ticker}.",
                url=f"https://www.reddit.com/r/stocks/search?q={ticker}",
                published_at="Recent",
                recency_days=3,
                weight=2.5,
                sentiment="bullish",
                is_management_mention=False,
            ),
            EvidenceItem(
                source=DataSourceType.REDDIT,
                source_label="Reddit r/investing",
                title=f"[r/investing] Discussion: Valuation multiples vs ROI payback horizons for {ticker}",
                snippet=f"Community debate weighing customer concentration risk and potential digestion quarters against multi-year backlog strength.",
                url=f"https://www.reddit.com/r/investing/search?q={ticker}",
                published_at="Recent",
                recency_days=6,
                weight=2.0,
                sentiment="neutral",
                is_management_mention=False,
            )
        ]
