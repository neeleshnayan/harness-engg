"""Concurrent research collector aggregator."""

from __future__ import annotations

import concurrent.futures
import logging

from app.fund.thesis_generator.collectors.base import BaseCollector
from app.fund.thesis_generator.collectors.github import GitHubCollector
from app.fund.thesis_generator.collectors.hacker_news import HackerNewsCollector
from app.fund.thesis_generator.collectors.macro_fred import MacroFredCollector
from app.fund.thesis_generator.collectors.news_rss import NewsRssCollector
from app.fund.thesis_generator.collectors.reddit import RedditCollector
from app.fund.thesis_generator.collectors.sec_edgar import KNOWN_CIKS, SecEdgarCollector
from app.fund.thesis_generator.models import DataSourceStatus, EvidenceItem

_log = logging.getLogger("clarkharness.thesis.aggregator")


class ResearchAggregator:
    """Coordinates parallel data collection across SEC, News, Reddit, HN, GitHub, and FRED."""

    def __init__(self, timeout_seconds: float = 4.0):
        self.timeout_seconds = timeout_seconds
        self.collectors: list[BaseCollector] = [
            SecEdgarCollector(timeout_seconds=timeout_seconds),
            NewsRssCollector(timeout_seconds=timeout_seconds),
            RedditCollector(timeout_seconds=timeout_seconds),
            HackerNewsCollector(timeout_seconds=timeout_seconds),
            GitHubCollector(timeout_seconds=timeout_seconds),
            MacroFredCollector(timeout_seconds=timeout_seconds),
        ]

    def collect_all(self, ticker: str) -> tuple[list[EvidenceItem], list[DataSourceStatus], str]:
        """Runs all collectors concurrently, returning aggregated evidence, per-source statuses, and company name."""
        sym = ticker.upper()
        known = KNOWN_CIKS.get(sym)
        company_name = known["title"] if known else sym

        all_evidence: list[EvidenceItem] = []
        all_statuses: list[DataSourceStatus] = []

        with concurrent.futures.ThreadPoolExecutor(max_workers=len(self.collectors)) as executor:
            future_to_collector = {
                executor.submit(c.collect_safe, sym, company_name): c
                for c in self.collectors
            }

            for future in concurrent.futures.as_completed(future_to_collector):
                collector = future_to_collector[future]
                try:
                    items, status = future.result(timeout=self.timeout_seconds + 1.0)
                    all_evidence.extend(items)
                    all_statuses.append(status)
                except Exception as exc:
                    _log.warning("Collector %s failed: %s", collector.source_name, exc)
                    all_statuses.append(
                        DataSourceStatus(
                            source=collector.source_type,
                            name=collector.source_name,
                            status="degraded",
                            item_count=0,
                            latency_ms=int(self.timeout_seconds * 1000),
                            message=str(exc)
                        )
                    )

        # Sort statuses in predictable order
        order = [c.source_type for c in self.collectors]
        all_statuses.sort(key=lambda s: order.index(s.source) if s.source in order else 99)

        return all_evidence, all_statuses, company_name
