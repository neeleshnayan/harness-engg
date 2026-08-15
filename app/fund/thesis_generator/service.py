"""Thesis generator service orchestrating collection, synthesis, and fund event promotion."""

from __future__ import annotations

import logging
from typing import Any, Optional

from app.fund.events import EventStore
from app.fund.memo import MemoService
from app.fund.thesis import ThesisService
from app.fund.thesis_generator.collectors.aggregator import ResearchAggregator
from app.fund.thesis_generator.generator import ThesisGenerator
from app.fund.thesis_generator.models import (
    DataSourceStatus,
    Direction,
    GeneratedThesisResult,
)
from app.fund.thesis_generator.query_parser import QueryParser

_log = logging.getLogger("clarkharness.thesis.service")


class ThesisGeneratorService:
    """Orchestrates automatic theme discovery, thesis generation, and fund promotion."""

    def __init__(
        self,
        store: Optional[EventStore] = None,
        thesis_service: Optional[ThesisService] = None,
        memo_service: Optional[MemoService] = None,
    ):
        self._store = store or EventStore()
        self._thesis_service = thesis_service or ThesisService(self._store)
        self._memo_service = memo_service or MemoService(self._store)
        self._aggregator = ResearchAggregator(timeout_seconds=4.0)

    def generate_thesis(self, query_str: str, direction_override: Optional[str] = None) -> GeneratedThesisResult:
        """Parses query, aggregates multi-source evidence, clusters themes, and generates investment thesis."""
        parsed = QueryParser.parse(query_str)
        direction = Direction(direction_override.upper()) if direction_override else parsed.direction

        # 1. Concurrently collect multi-source evidence
        all_evidence, statuses, company_name = self._aggregator.collect_all(parsed.ticker)

        # 2. Generate structured investment thesis
        result = ThesisGenerator.generate(
            ticker=parsed.ticker,
            company_name=company_name,
            direction=direction,
            all_evidence=all_evidence,
            data_sources_status=statuses,
            theme_hint=parsed.theme_hint,
        )

        return result

    def promote_to_fund(
        self,
        result: GeneratedThesisResult,
        actor: str = "operator",
        target_exposure_pct: float = 5.0,
        horizon: str = "3-6 months",
    ) -> dict[str, Any]:
        """Creates a formal event-sourced Thesis and initial Memo in the fund spine."""
        top_theme_names = [t.title for t in result.top_themes[:3]]

        # 1. Create fund Thesis
        thesis_body = {
            "title": result.title,
            "claim": f"{result.direction.value} conviction on {result.ticker} driven by {', '.join(top_theme_names)}",
            "assets": [result.ticker],
            "owner": actor,
            "horizon": horizon,
            "entry_rationale": result.executive_summary,
            "key_risks": [r.risk_statement for r in result.bear_case],
            "invalidation_conditions": [inv.condition for inv in result.invalidation_conditions],
            "target_exposure_pct": target_exposure_pct,
            "review_cadence": "monthly",
        }

        created_thesis = self._thesis_service.create(thesis_body, actor=actor)
        thesis_id = created_thesis["thesis_id"]

        # 2. Draft initial formal Investment Memo linked to the thesis
        memo_sections = {
            "Executive Summary": result.executive_summary,
            "Top Themes": "\n\n".join(
                f"**{t.title}** (Score: {t.score}/100)\n{t.summary}" for t in result.top_themes
            ),
            "Bull Case Drivers": "\n\n".join(
                f"**Driver {d.driver_number}: {d.theme_title}**\n{d.driver_statement}" for d in result.bull_case
            ),
            "Bear Risks & Counter-Theses": "\n\n".join(
                f"**Risk {r.risk_number}: {r.risk_title}**\n{r.risk_statement}\n*Counter*: {r.counter_argument}"
                for r in result.bear_case
            ),
            "Catalysts": "\n".join(f"- **{c.event_name}** ({c.timeframe}): {c.expected_impact}" for c in result.catalysts),
            "Invalidation Rules": "\n".join(f"- {inv.condition}" for inv in result.invalidation_conditions),
        }

        memo_body = {
            "thesis_id": thesis_id,
            "title": f"Investment Memo: {result.title}",
            "recommendation": f"{result.direction.value} {result.ticker} target {target_exposure_pct}% NAV exposure",
            "conviction": "high" if result.top_themes and result.top_themes[0].score >= 85 else "medium",
            "summary": result.executive_summary,
            "sections": memo_sections,
            "sources": [f"{s.name} ({s.item_count} items)" for s in result.data_sources_status],
            "author": "Clark Research Agent",
        }

        created_memo = self._memo_service.create(memo_body, actor=actor)

        return {
            "thesis": created_thesis,
            "memo": created_memo,
            "message": f"Successfully created Fund Thesis {thesis_id} and initial Investment Memo",
        }

    def get_data_sources_status(self) -> list[DataSourceStatus]:
        """Returns baseline health status of all data source connectors."""
        # Quick health probe with a benchmark ticker
        _, statuses, _ = self._aggregator.collect_all("NVDA")
        return statuses
