"""Evidence mapping engine connecting parsed facts and sources to themes and thesis cases."""

from __future__ import annotations

from app.fund.thesis_generator.models import (
    BearRisk,
    BullDriver,
    Catalyst,
    Direction,
    DiscoveredTheme,
    EvidenceItem,
    InvalidationCondition,
)
from app.fund.thesis_generator.tickers_data import get_profile_for_ticker


class EvidenceMapper:
    """Maps deterministic evidence to Top 5 primary drivers, risk factors, catalysts, and invalidation rules."""

    @classmethod
    def map_bull_drivers(
        cls, top_themes: list[DiscoveredTheme], ticker: str, direction: Direction
    ) -> list[BullDriver]:
        sym = ticker.upper().strip()
        profile = get_profile_for_ticker(sym)
        drivers: list[BullDriver] = []

        # Drivers are either Bullish (for LONG) or Bearish Downside (for SHORT)
        if direction == Direction.LONG:
            driver_pairs = profile.get("bull_drivers", [])
        else:
            driver_pairs = profile.get("bear_drivers", [])

        themes_to_use = top_themes[:5]

        for i, theme in enumerate(themes_to_use, start=1):
            snippets = [
                f"[{e.source_label}] {e.title}: {e.snippet[:160]}..."
                for e in theme.evidence[:2]
            ]
            metric_strs = [m.raw_text for m in theme.metrics[:2]]

            # Fallback to profile driver statement if available
            if i - 1 < len(driver_pairs):
                title_override, statement = driver_pairs[i - 1]
                driver_title = theme.title if theme.title else title_override
            else:
                driver_title = theme.title
                if direction == Direction.LONG:
                    statement = f"{theme.title} expands operational tailwinds and revenue visibility for {sym}, supported by robust market demand."
                else:
                    statement = f"{theme.title} introduces structural headwind and margin pressure for {sym}, increasing downside execution sensitivity."

            drivers.append(
                BullDriver(
                    driver_number=i,
                    theme_title=driver_title,
                    driver_statement=statement,
                    evidence_snippets=snippets,
                    key_metrics=metric_strs,
                )
            )

        return drivers

    @classmethod
    def map_bear_risks(
        cls,
        all_evidence: list[EvidenceItem],
        top_themes: list[DiscoveredTheme],
        ticker: str,
        direction: Direction = Direction.LONG,
    ) -> list[BearRisk]:
        sym = ticker.upper().strip()
        profile = get_profile_for_ticker(sym)

        # For LONG, risks are bear risks. For SHORT, risks are upside risks (threats to the short).
        if direction == Direction.LONG:
            raw_risks = profile.get("bear_drivers", [])
            counter_label = "Long Counter-Perspective"
        else:
            raw_risks = profile.get("bull_drivers", [])
            counter_label = "Short Risk Consideration"

        bear_items = [e for e in all_evidence if e.sentiment == ("bearish" if direction == Direction.LONG else "bullish")]

        risks: list[BearRisk] = []
        for i in range(min(3, len(raw_risks))):
            r_title, r_stmt = raw_risks[i]
            if direction == Direction.LONG:
                counter = f"{sym} product moat, pricing power, and expanding enterprise customer retention provide mitigating resilience against this risk."
            else:
                counter = f"If {sym} accelerates gross margins or beats consensus on new product cycles, the short thesis faces near-term multiple re-rating."

            snips = [f"[{e.source_label}] {e.snippet[:140]}" for e in bear_items[:1]] or [
                f"SEC periodic disclosures & market analysis outline key risk factors across {r_title}."
            ]

            risks.append(
                BearRisk(
                    risk_number=i + 1,
                    risk_title=r_title,
                    risk_statement=r_stmt,
                    counter_argument=counter,
                    evidence_snippets=snips,
                )
            )

        if not risks:
            risks.append(
                BearRisk(
                    risk_number=1,
                    risk_title=f"{sym} Execution & Market Risk",
                    risk_statement=f"Operational shifts in core product segments or macroeconomic volatility could affect financial projections for {sym}.",
                    counter_argument=f"Disciplined capital allocation and balance sheet strength mitigate downside volatility.",
                    evidence_snippets=[f"SEC Form 10-Q Item 1A: Outlines standard operational and market risks for {sym}."],
                )
            )

        return risks

    @classmethod
    def extract_catalysts(
        cls, ticker: str, top_themes: list[DiscoveredTheme], all_evidence: list[EvidenceItem], direction: Direction = Direction.LONG
    ) -> list[Catalyst]:
        sym = ticker.upper().strip()
        profile = get_profile_for_ticker(sym)
        raw_cats = profile.get("catalysts", [])

        catalysts: list[Catalyst] = []
        for cat_tuple in raw_cats:
            event_name, timeframe, impact = cat_tuple
            catalysts.append(
                Catalyst(
                    event_name=event_name,
                    timeframe=timeframe,
                    expected_impact=impact,
                    source_ref=f"{sym} Corporate Disclosures & Financial Calendar",
                )
            )

        if not catalysts:
            catalysts = [
                Catalyst(
                    event_name=f"{sym} Upcoming Quarterly Earnings & Guidance Print",
                    timeframe="Next Earnings Cycle",
                    expected_impact="Validates revenue growth trajectory, segment margins, and capital expenditures.",
                    source_ref=f"{sym} Investor Relations",
                ),
                Catalyst(
                    event_name=f"{sym} Product Roadmap & Commercial Milestones",
                    timeframe="Next 3-6 Months",
                    expected_impact="Determines market share trajectory and pricing power in core business segments.",
                    source_ref="SEC Periodic Filings & News",
                ),
            ]

        return catalysts

    @classmethod
    def generate_invalidation_conditions(
        cls, ticker: str, top_themes: list[DiscoveredTheme], direction: Direction = Direction.LONG
    ) -> list[InvalidationCondition]:
        sym = ticker.upper().strip()
        profile = get_profile_for_ticker(sym)

        if direction == Direction.LONG:
            raw_inv = profile.get("long_invalidation", [])
        else:
            raw_inv = profile.get("short_invalidation", [])

        conditions: list[InvalidationCondition] = []
        for inv_str in raw_inv:
            conditions.append(
                InvalidationCondition(
                    condition=inv_str,
                    trigger_metric=inv_str.split(" ")[0] + " " + inv_str.split(" ")[1] if len(inv_str.split(" ")) > 2 else "Threshold",
                    threshold="Exit Trigger",
                )
            )

        if not conditions:
            conditions = [
                InvalidationCondition(
                    condition=f"{sym} reported revenue growth decelerates below 5.0% YoY for two consecutive quarters.",
                    trigger_metric="Revenue Growth < 5.0%",
                    threshold="5.0% YoY",
                ),
                InvalidationCondition(
                    condition=f"{sym} operating margin contracts by >300bps YoY on structural cost inflation.",
                    trigger_metric="Operating Margin Contraction",
                    threshold="-300bps",
                ),
            ]

        return conditions
