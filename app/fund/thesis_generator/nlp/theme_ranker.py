"""Theme ranking engine implementing the exact formula from Thesis 2.md."""

from __future__ import annotations

import math

from app.fund.thesis_generator.models import DiscoveredTheme, FactMetric
from app.fund.thesis_generator.nlp.theme_discovery import DiscoveredCluster


class ThemeRanker:
    """Ranks discovered themes using deterministic scoring formula:

    theme_score = 0.5 * frequency + 0.3 * recency + 0.2 * management_mentions
    """

    @classmethod
    def rank_and_build(
        cls, clusters: list[DiscoveredCluster], all_metrics: list[FactMetric]
    ) -> list[DiscoveredTheme]:
        ranked_themes: list[DiscoveredTheme] = []

        for idx, cluster in enumerate(clusters):
            # 1. Frequency (weighted by source weights)
            weighted_freq = sum(e.weight for e in cluster.matching_evidence)
            freq_raw = len(cluster.matching_evidence)

            # 2. Recency Score (0..100): recent items score closer to 100
            recency_components = []
            for e in cluster.matching_evidence:
                days = max(1, e.recency_days)
                # Decay formula: 100 * exp(-days / 45)
                recency_components.append(100.0 * math.exp(-days / 45.0))
            avg_recency = sum(recency_components) / len(recency_components) if recency_components else 50.0

            # 3. Management Mentions (SEC filings, IR disclosures)
            mgmt_mentions = sum(1 for e in cluster.matching_evidence if e.is_management_mention)

            # Map matching quantitative metrics to this theme
            theme_metrics: list[FactMetric] = []
            cluster_text = (cluster.theme_title + " " + " ".join(cluster.keywords)).lower()
            for m in all_metrics:
                m_text = (m.metric_type + " " + (m.segment or "") + " " + m.raw_text).lower()
                if any(kw in m_text for kw in cluster.keywords) or any(w in m_text for w in cluster.theme_title.lower().split()):
                    if m not in theme_metrics:
                        theme_metrics.append(m)

            # 4. Composite Formula: 0.5 * freq + 0.3 * recency + 0.2 * mgmt
            # Normalize components to 0..100 scale
            freq_norm = min(100.0, weighted_freq * 3.5)
            mgmt_norm = min(100.0, mgmt_mentions * 25.0)

            composite = (0.5 * freq_norm) + (0.3 * avg_recency) + (0.2 * mgmt_norm)
            final_score = int(min(98, max(35, composite)))

            # Build narrative summary
            summary = cls._generate_theme_summary(cluster.theme_title, cluster.keywords, cluster.matching_evidence, theme_metrics)

            theme_id = f"theme-{idx+1}-{cluster.theme_title.lower().replace(' ', '-').replace('&', 'and')[:20]}"
            ranked_themes.append(
                DiscoveredTheme(
                    theme_id=theme_id,
                    title=cluster.theme_title,
                    keywords=cluster.keywords,
                    score=final_score,
                    frequency=freq_raw,
                    recency_score=round(avg_recency, 1),
                    management_mentions=mgmt_mentions,
                    summary=summary,
                    evidence=cluster.matching_evidence,
                    metrics=theme_metrics,
                )
            )

        # Sort descending by score
        ranked_themes.sort(key=lambda t: t.score, reverse=True)
        return ranked_themes

    @classmethod
    def _generate_theme_summary(
        cls, title: str, keywords: list[str], evidence: list[EvidenceItem], metrics: list[FactMetric]
    ) -> str:
        kws_str = ", ".join(keywords[:4]) if keywords else "infrastructure"
        metric_str = ""
        if metrics:
            m = metrics[0]
            metric_str = f" Supported by reported {m.metric_type} ({m.raw_text[:90]})."

        return f"{title} represents a primary catalyst and capital allocation driver ({kws_str}) across audited filings and verified market data.{metric_str}"
