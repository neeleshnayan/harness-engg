"""Deterministic fact and quantitative metric extraction using regex and rules."""

from __future__ import annotations

import re
from typing import Optional

from app.fund.thesis_generator.models import DataSourceType, FactMetric


class FactExtractor:
    """Extracts financial metrics, growth rates, capex figures, and guidance statements from text."""

    PATTERNS = [
        # Revenue / Segment Growth: "datacenter revenue increased 82% YoY", "up +45% year over year"
        (
            "Revenue Growth",
            re.compile(
                r"(?:([A-Za-z]+)\s+)?(?:revenue|sales|income|demand|bookings)\s+(?:grew|increased|up|surged|accelerated)\s+(?:by\s+)?(\+?\d+(?:\.\d+)?)\s*%\s*(?:YoY|year[- ]over[- ]year|quarter[- ]over[- ]quarter|QoQ)?",
                re.IGNORECASE,
            ),
            "%",
        ),
        # Generic percentage growth: "+82% YoY", "120% year over year"
        (
            "Growth Rate",
            re.compile(r"(\+?\d+(?:\.\d+)?)\s*%\s*(YoY|year[- ]over[- ]year)", re.IGNORECASE),
            "%",
        ),
        # Capex & Capital Commitments: "$12.5 billion capex", "capex of $45B"
        (
            "Capex",
            re.compile(
                r"(?:capex|capital expenditures?|infrastructure spend)\s*(?:of|at|reached|projected at)?\s*\$?(\d+(?:\.\d+)?)\s*(billion|million|B|M)",
                re.IGNORECASE,
            ),
            "$B",
        ),
        # Dollar amounts: "$30 billion in revenue", "$500M investment"
        (
            "Financial Volume",
            re.compile(
                r"\$?(\d+(?:\.\d+)?)\s*(billion|million|B|M)\s*(?:in\s+([A-Za-z]+))?",
                re.IGNORECASE,
            ),
            "$B",
        ),
        # Gross Margin / Operating Margin: "gross margin of 75.4%", "operating margins expanded to 62%"
        (
            "Margin",
            re.compile(
                r"(gross|operating|net)\s*margins?\s*(?:of|at|was|reached)?\s*(\d+(?:\.\d+)?)\s*%",
                re.IGNORECASE,
            ),
            "%",
        ),
        # Guidance / Forecast statements: "guidance of $32.5B", "expects revenue between $30B and $32B"
        (
            "Guidance",
            re.compile(
                r"(?:expects|guidance|forecasts|projects|targets)\s+(?:revenue|sales|growth)?\s*(?:of|at|between)?\s*([^.,;\n]{5,60})",
                re.IGNORECASE,
            ),
            "text",
        ),
    ]

    @classmethod
    def extract_from_text(
        cls, text: str, source: DataSourceType, source_url: Optional[str] = None
    ) -> list[FactMetric]:
        facts: list[FactMetric] = []
        if not text:
            return facts

        # Split into sentences
        sentences = re.split(r"[.\n;]", text)
        for s in sentences:
            s_clean = s.strip()
            if not s_clean or len(s_clean) < 10:
                continue

            for metric_type, regex, unit in cls.PATTERNS:
                m = regex.search(s_clean)
                if m:
                    val_float: Optional[float] = None
                    segment: Optional[str] = None
                    groups = m.groups()

                    if metric_type == "Revenue Growth":
                        segment = groups[0] if groups[0] else None
                        try:
                            val_float = float(groups[1].replace("+", ""))
                        except (ValueError, TypeError):
                            val_float = None
                    elif metric_type == "Growth Rate":
                        try:
                            val_float = float(groups[0].replace("+", ""))
                        except (ValueError, TypeError):
                            val_float = None
                    elif metric_type == "Capex":
                        try:
                            base = float(groups[0])
                            mag = groups[1].upper()
                            val_float = base if ("B" in mag or "BILLION" in mag) else round(base / 1000, 3)
                        except (ValueError, TypeError):
                            val_float = None
                    elif metric_type == "Margin":
                        segment = groups[0]
                        try:
                            val_float = float(groups[1])
                        except (ValueError, TypeError):
                            val_float = None

                    facts.append(
                        FactMetric(
                            metric_type=metric_type,
                            segment=segment,
                            value=val_float,
                            unit=unit,
                            raw_text=s_clean,
                            source=source,
                            source_url=source_url,
                        )
                    )
                    break  # Matched one high-fidelity metric for this sentence

        return facts
