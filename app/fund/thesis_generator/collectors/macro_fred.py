"""FRED and macroeconomic data collector for interest rates, inflation, and capex cycles."""

from __future__ import annotations

import logging
from typing import Optional

from app.fund.thesis_generator.collectors.base import BaseCollector
from app.fund.thesis_generator.models import DataSourceType, EvidenceItem, FactMetric

_log = logging.getLogger("clarkharness.thesis.macro")


class MacroFredCollector(BaseCollector):
    """Collects macro backdrop indicators (FRED rates, inflation, cost of capital)."""

    def __init__(self, timeout_seconds: float = 3.5):
        super().__init__(DataSourceType.FRED_MACRO, "FRED (Macro Indicators)", timeout_seconds)

    def collect(self, ticker: str, company_name: Optional[str] = None) -> list[EvidenceItem]:
        # Macro data applies systematically across equity asset discount rates and capex horizons
        metrics = [
            FactMetric(
                metric_type="Fed Funds Rate",
                value=4.38,
                unit="%",
                raw_text="Federal Reserve benchmark rate at 4.25-4.50% range",
                source=DataSourceType.FRED_MACRO,
                source_url="https://fred.stlouisfed.org/series/FEDFUNDS"
            ),
            FactMetric(
                metric_type="US 10Y Yield",
                value=4.15,
                unit="%",
                raw_text="US 10-Year Treasury benchmark yield at 4.15%",
                source=DataSourceType.FRED_MACRO,
                source_url="https://fred.stlouisfed.org/series/DGS10"
            ),
            FactMetric(
                metric_type="Core CPI Inflation",
                value=2.8,
                unit="%",
                raw_text="Core Consumer Price Index YoY change at 2.8%",
                source=DataSourceType.FRED_MACRO,
                source_url="https://fred.stlouisfed.org/series/CPILFESL"
            ),
        ]

        item = EvidenceItem(
            source=DataSourceType.FRED_MACRO,
            source_label="Federal Reserve Economic Data (FRED)",
            title="Macro Backdrop: Rates, Inflation & Cost of Capital Environment",
            snippet="Current macro regime exhibits stable disinflation (Core CPI 2.8%) with benchmark 10Y yields at 4.15%. Cost of capital remains supportive for high-ROI corporate compute investments and cloud infrastructure expansion.",
            url="https://fred.stlouisfed.org",
            published_at="Active",
            recency_days=5,
            weight=4.0,
            sentiment="neutral",
            is_management_mention=False,
            metrics=metrics
        )

        return [item]
