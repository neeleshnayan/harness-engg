"""Base collector interface for thesis evidence gathering."""

from __future__ import annotations

import abc
import time
from typing import Optional

from app.fund.thesis_generator.models import DataSourceStatus, DataSourceType, EvidenceItem


class BaseCollector(abc.ABC):
    """Abstract base class for all research data collectors."""

    def __init__(self, source_type: DataSourceType, source_name: str, timeout_seconds: float = 4.0):
        self.source_type = source_type
        self.source_name = source_name
        self.timeout_seconds = timeout_seconds

    @abc.abstractmethod
    def collect(self, ticker: str, company_name: Optional[str] = None) -> list[EvidenceItem]:
        """Synchronously collect evidence for a given ticker."""
        pass

    def collect_safe(self, ticker: str, company_name: Optional[str] = None) -> tuple[list[EvidenceItem], DataSourceStatus]:
        """Execute collect with timing and graceful degradation."""
        start_t = time.perf_counter()
        try:
            items = self.collect(ticker, company_name)
            latency_ms = int((time.perf_counter() - start_t) * 1000)
            status = DataSourceStatus(
                source=self.source_type,
                name=self.source_name,
                status="healthy" if items else "degraded",
                item_count=len(items),
                latency_ms=latency_ms,
                message=f"Collected {len(items)} evidence items" if items else "No records found for query",
            )
            return items, status
        except Exception as exc:
            latency_ms = int((time.perf_counter() - start_t) * 1000)
            status = DataSourceStatus(
                source=self.source_type,
                name=self.source_name,
                status="degraded",
                item_count=0,
                latency_ms=latency_ms,
                message=f"Collector error: {exc}",
            )
            return [], status
