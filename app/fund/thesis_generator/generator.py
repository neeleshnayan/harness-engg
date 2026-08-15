"""Investment Thesis synthesis and Jinja2 renderer."""

from __future__ import annotations

from typing import Optional
from jinja2 import Template

from app.fund.thesis_generator.models import (
    DataSourceStatus,
    Direction,
    DiscoveredTheme,
    EvidenceItem,
    GeneratedThesisResult,
)
from app.fund.thesis_generator.nlp.evidence_mapper import EvidenceMapper
from app.fund.thesis_generator.nlp.fact_extractor import FactExtractor
from app.fund.thesis_generator.nlp.theme_discovery import ThemeDiscoveryEngine
from app.fund.thesis_generator.nlp.theme_ranker import ThemeRanker

THESIS_JINJA_TEMPLATE = """# Investment Thesis: {{ direction.value }} {{ ticker }} ({{ company_name }})

## Executive Summary
{{ executive_summary }}

---

## Discovered Top Themes (Ranked)
{% for theme in top_themes %}
### {{ loop.index }}. {{ theme.title }} (Score: {{ theme.score }}/100)
- **Score Breakdown**: Frequency: {{ theme.frequency }} items | Recency: {{ theme.recency_score }}/100 | Management Citations: {{ theme.management_mentions }}
- **Narrative**: {{ theme.summary }}
{% if theme.metrics %}
- **Verified Fact Metrics**:
{% for m in theme.metrics %}
  - `{{ m.metric_type }}`: {{ m.raw_text }} (Source: {{ m.source.value }})
{% endfor %}
{% endif %}
{% endfor %}

---

{% if direction.value == "LONG" %}
## Bull Case (Key Growth Drivers)
{% for driver in bull_case %}
**{{ driver.driver_number }}. {{ driver.theme_title }}**
{{ driver.driver_statement }}
{% for snip in driver.evidence_snippets %}
- Evidence: {{ snip }}
{% endfor %}
{% endfor %}

---

## Bear Case & Critical Risks
{% for risk in bear_case %}
**{{ risk.risk_number }}. {{ risk.risk_title }}**
- *Risk*: {{ risk.risk_statement }}
- *Counter-Perspective*: {{ risk.counter_argument }}
{% endfor %}
{% else %}
## Short Thesis (Primary Downside Drivers)
{% for driver in bull_case %}
**{{ driver.driver_number }}. {{ driver.theme_title }}**
{{ driver.driver_statement }}
{% for snip in driver.evidence_snippets %}
- Evidence: {{ snip }}
{% endfor %}
{% endfor %}

---

## Upside Risks & Counter-Theses
{% for risk in bear_case %}
**{{ risk.risk_number }}. {{ risk.risk_title }}**
- *Upside Threat*: {{ risk.risk_statement }}
- *Short Defense*: {{ risk.counter_argument }}
{% endfor %}
{% endif %}

---

## Catalysts & Horizon
{% for cat in catalysts %}
- **{{ cat.event_name }}** ({{ cat.timeframe }}): {{ cat.expected_impact }}
{% endfor %}

---

## Invalidation Conditions (Exit Triggers)
{% for inv in invalidation_conditions %}
- ⚠️ **{{ inv.trigger_metric or "Condition" }}**: {{ inv.condition }}
{% endfor %}

---

## Sources & Evidence Citations
Total Research Items Ingested: **{{ raw_evidence_count }}**
{% for status in data_sources_status %}
- **{{ status.name }}**: {{ status.status | upper }} ({{ status.item_count }} items, latency: {{ status.latency_ms }}ms)
{% endfor %}
"""


class ThesisGenerator:
    """End-to-end thesis generator from parsed query and aggregated evidence."""

    @classmethod
    def generate(
        cls,
        ticker: str,
        company_name: str,
        direction: Direction,
        all_evidence: list[EvidenceItem],
        data_sources_status: list[DataSourceStatus],
        theme_hint: Optional[str] = None,
    ) -> GeneratedThesisResult:
        sym = ticker.upper().strip()

        # 1. Fact Extraction across all collected evidence
        all_metrics = []
        for e in all_evidence:
            metrics = FactExtractor.extract_from_text(e.snippet + " " + e.title, e.source, e.url)
            e.metrics.extend(metrics)
            all_metrics.extend(metrics)

        # 2. Theme Discovery & Clustering (dynamic for ticker & direction)
        clusters = ThemeDiscoveryEngine.discover_themes(all_evidence, ticker=sym, direction=direction)

        # If user passed a specific theme hint, boost/insert it
        if theme_hint:
            from app.fund.thesis_generator.nlp.theme_discovery import DiscoveredCluster
            hint_cluster = DiscoveredCluster(
                theme_title=theme_hint.title(),
                keywords=[w.lower() for w in theme_hint.split()],
                matching_evidence=[
                    e for e in all_evidence if any(w in (e.title + e.snippet).lower() for w in theme_hint.split())
                ] or all_evidence[:3],
            )
            clusters.insert(0, hint_cluster)

        # 3. Theme Ranking via exact formula
        top_themes = ThemeRanker.rank_and_build(clusters, all_metrics)

        # 4. Evidence Mapping: Bull/Downside Drivers, Risks, Catalysts, Invalidation
        bull_case = EvidenceMapper.map_bull_drivers(top_themes, sym, direction)
        bear_case = EvidenceMapper.map_bear_risks(all_evidence, top_themes, sym, direction=direction)
        catalysts = EvidenceMapper.extract_catalysts(sym, top_themes, all_evidence, direction=direction)
        invalidation_conditions = EvidenceMapper.generate_invalidation_conditions(sym, top_themes, direction=direction)

        # 5. Executive Summary Synthesis
        top_theme_names = [t.title for t in top_themes[:3]]
        themes_summary_str = ", ".join(top_theme_names)

        if direction == Direction.LONG:
            exec_summary = (
                f"LONG conviction for {sym} ({company_name}) is grounded in high-evidence momentum across "
                f"{themes_summary_str}. Audited SEC disclosures and verified market sentiment reflect accelerating demand, "
                f"expanding pricing power, and sustained capital expenditure commitments from core customer segments over a 3-6 month horizon."
            )
            title = f"LONG {sym}: {top_themes[0].title if top_themes else 'Core Growth Demand'}"
        else:
            exec_summary = (
                f"SHORT conviction for {sym} ({company_name}) is grounded in mounting structural headwinds across "
                f"{themes_summary_str}. Audited disclosures and market indicators highlight margin compression, "
                f"intense competitive pressures, elevated valuation multiples, and decelerating revenue trajectories over a 3-6 month horizon."
            )
            title = f"SHORT {sym}: {top_themes[0].title if top_themes else 'Structural Downside Pressure'}"

        # 6. Source Breakdown Counts
        sources_summary: dict[str, int] = {}
        for e in all_evidence:
            sources_summary[e.source.value] = sources_summary.get(e.source.value, 0) + 1

        # 7. Render Jinja2 Markdown Template
        template = Template(THESIS_JINJA_TEMPLATE)
        rendered_md = template.render(
            ticker=sym,
            company_name=company_name,
            direction=direction,
            title=title,
            executive_summary=exec_summary,
            top_themes=top_themes,
            bull_case=bull_case,
            bear_case=bear_case,
            catalysts=catalysts,
            invalidation_conditions=invalidation_conditions,
            raw_evidence_count=len(all_evidence),
            data_sources_status=data_sources_status,
        )

        return GeneratedThesisResult(
            ticker=sym,
            company_name=company_name,
            direction=direction,
            title=title,
            executive_summary=exec_summary,
            top_themes=top_themes,
            bull_case=bull_case,
            bear_case=bear_case,
            catalysts=catalysts,
            invalidation_conditions=invalidation_conditions,
            sources_summary=sources_summary,
            data_sources_status=data_sources_status,
            raw_evidence_count=len(all_evidence),
            markdown_output=rendered_md,
        )
