"""Theme discovery and clustering engine using scikit-learn TF-IDF, semantic clustering, and company profiles."""

from __future__ import annotations

import collections
import logging
from typing import Optional

import numpy as np
from sklearn.cluster import AgglomerativeClustering
from sklearn.feature_extraction.text import TfidfVectorizer

from app.fund.thesis_generator.models import Direction, EvidenceItem
from app.fund.thesis_generator.nlp.keyword_extractor import KeywordExtractor
from app.fund.thesis_generator.tickers_data import get_profile_for_ticker

_log = logging.getLogger("clarkharness.thesis.themes")


class DiscoveredCluster:
    def __init__(self, theme_title: str, keywords: list[str], matching_evidence: list[EvidenceItem]):
        self.theme_title = theme_title
        self.keywords = keywords
        self.matching_evidence = matching_evidence


class ThemeDiscoveryEngine:
    """Discovers emerging narratives and clusters evidence into ticker-specific investment themes."""

    @classmethod
    def discover_themes(
        cls,
        evidence_items: list[EvidenceItem],
        ticker: str,
        direction: Direction = Direction.LONG,
        target_k: int = 5,
    ) -> list[DiscoveredCluster]:
        sym = ticker.upper().strip()
        profile = get_profile_for_ticker(sym)

        # Base candidate themes from profile based on direction
        profile_themes = (
            profile.get("long_themes", []) if direction == Direction.LONG else profile.get("short_themes", [])
        )
        if not profile_themes:
            profile_themes = profile.get("long_themes", [])

        if not evidence_items:
            return [
                DiscoveredCluster(
                    theme_title=t_title,
                    keywords=[w.lower() for w in t_title.split() if len(w) > 3],
                    matching_evidence=[],
                )
                for t_title in profile_themes[:target_k]
            ]

        # Aggregate all textual content from evidence
        texts = [f"{e.title}. {e.snippet}" for e in evidence_items]
        full_corpus_lower = " ".join(texts).lower()

        theme_matches: dict[str, list[EvidenceItem]] = collections.defaultdict(list)
        theme_keywords_map: dict[str, set[str]] = collections.defaultdict(set)

        # 1. Map evidence items to profile themes based on keyword overlaps
        for theme_title in profile_themes:
            theme_words = [w.lower() for w in theme_title.replace("&", " ").replace("/", " ").replace("-", " ").split() if len(w) > 3]
            theme_keywords_map[theme_title] = set(theme_words)

            for item in evidence_items:
                item_text = (item.title + " " + item.snippet).lower()
                # Check if item matches theme words or if sentiments match direction
                if any(w in item_text for w in theme_words) or (direction == Direction.SHORT and item.sentiment == "bearish") or (direction == Direction.LONG and item.sentiment == "bullish"):
                    if item not in theme_matches[theme_title]:
                        theme_matches[theme_title].append(item)

        # 2. Dynamic clustering via TF-IDF on actual evidence corpus
        if len(texts) >= 3:
            try:
                vectorizer = TfidfVectorizer(max_features=80, stop_words="english")
                X = vectorizer.fit_transform(texts)
                n_clusters = min(target_k, len(texts))
                if n_clusters >= 2:
                    clustering = AgglomerativeClustering(n_clusters=n_clusters)
                    labels = clustering.fit_predict(X.toarray())
                    feature_names = np.array(vectorizer.get_feature_names_out())

                    for cluster_id in range(n_clusters):
                        cluster_indices = [i for i, lbl in enumerate(labels) if lbl == cluster_id]
                        if not cluster_indices:
                            continue
                        cluster_center = np.asarray(X[cluster_indices].mean(axis=0)).ravel()
                        top_feat_indices = cluster_center.argsort()[-3:][::-1]
                        top_words = [feature_names[idx] for idx in top_feat_indices]
                        dynamic_theme_name = f"{sym} " + " & ".join(w.capitalize() for w in top_words) + (" Acceleration" if direction == Direction.LONG else " Pressure")

                        cluster_evidence = [evidence_items[i] for i in cluster_indices]
                        if len(cluster_evidence) >= 1 and len(theme_matches) < target_k:
                            theme_matches[dynamic_theme_name] = cluster_evidence
                            theme_keywords_map[dynamic_theme_name] = set(top_words)
            except Exception as e:
                _log.debug("Dynamic clustering note for %s: %s", sym, e)

        # Ensure all profile themes exist with at least relevant evidence attached
        for idx, theme_title in enumerate(profile_themes):
            if theme_title not in theme_matches or not theme_matches[theme_title]:
                # Attach representative evidence
                theme_matches[theme_title] = evidence_items[idx % len(evidence_items) : (idx % len(evidence_items)) + 2] or evidence_items[:2]

        # 3. Build DiscoveredCluster list
        clusters: list[DiscoveredCluster] = []
        for theme_title, ev_list in theme_matches.items():
            kw_list = sorted(list(theme_keywords_map.get(theme_title, set())))
            if not kw_list:
                kw_list = [w.lower() for w in theme_title.split() if len(w) > 3]
            clusters.append(DiscoveredCluster(
                theme_title=theme_title,
                keywords=kw_list,
                matching_evidence=ev_list or evidence_items[:2]
            ))

        return clusters[:target_k]
