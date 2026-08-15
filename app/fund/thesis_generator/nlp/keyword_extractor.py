"""Statistical and TF-IDF n-gram keyword extractor for financial research."""

from __future__ import annotations

import collections
import math
import re
from typing import Optional


# Custom financial & English stopwords
STOPWORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and",
    "any", "are", "aren't", "as", "at", "be", "because", "been", "before", "being",
    "below", "between", "both", "but", "by", "can", "can't", "cannot", "could",
    "couldn't", "did", "didn't", "do", "does", "doesn't", "doing", "don't", "down",
    "during", "each", "few", "for", "from", "further", "had", "hadn't", "has",
    "hasn't", "have", "haven't", "having", "he", "her", "here", "hers", "herself",
    "him", "himself", "his", "how", "i", "if", "in", "into", "is", "isn't", "it",
    "its", "itself", "let's", "me", "more", "most", "mustn't", "my", "myself",
    "no", "nor", "not", "of", "off", "on", "once", "only", "or", "other", "ought",
    "our", "ours", "ourselves", "out", "over", "own", "same", "shan't", "she",
    "should", "shouldn't", "so", "some", "such", "than", "that", "the", "their",
    "theirs", "them", "themselves", "then", "there", "these", "they", "this",
    "those", "through", "to", "too", "under", "until", "up", "very", "was",
    "wasn't", "we", "were", "weren't", "what", "when", "where", "which", "while",
    "who", "whom", "why", "with", "won't", "would", "wouldn't", "you", "your",
    "yours", "yourself", "yourselves", "also", "inc", "corp", "co", "ltd", "company",
    "stock", "share", "shares", "investor", "report", "filing", "quarter", "year",
    "period", "ended", "item", "form", "sec", "edgar", "recent", "today", "yesterday",
    "http", "https", "www", "com", "net", "org", "html"
}


class KeywordExtractor:
    """Extracts candidate multi-word key phrases and topics from research text."""

    @classmethod
    def extract_keywords(
        cls, texts: list[str], top_n: int = 30, min_len: int = 3
    ) -> list[tuple[str, float]]:
        """Extracts top n-grams ranked by TF-IDF & phrase co-occurrence."""
        if not texts:
            return []

        doc_tokens: list[list[str]] = []
        all_unigrams: list[str] = []
        all_bigrams: list[str] = []
        all_trigrams: list[str] = []

        for doc in texts:
            cleaned = re.sub(r"[^A-Za-z0-9\s\-]", " ", doc.lower())
            words = [w.strip("-") for w in cleaned.split() if len(w.strip("-")) >= min_len and w.strip("-") not in STOPWORDS]
            doc_tokens.append(words)

            # Unigrams
            all_unigrams.extend(words)

            # Bigrams
            for i in range(len(words) - 1):
                bg = f"{words[i]} {words[i+1]}"
                all_bigrams.append(bg)

            # Trigrams
            for i in range(len(words) - 2):
                tg = f"{words[i]} {words[i+1]} {words[i+2]}"
                all_trigrams.append(tg)

        # Count frequencies
        uni_counts = collections.Counter(all_unigrams)
        bi_counts = collections.Counter(all_bigrams)
        tri_counts = collections.Counter(all_trigrams)

        num_docs = len(texts)
        scores: dict[str, float] = {}

        # Score multi-word phrases higher than single words for rich theme names
        for phrase, count in tri_counts.items():
            df = sum(1 for d in texts if phrase in d.lower())
            idf = math.log((num_docs + 1) / (df + 1)) + 1.0
            scores[phrase] = count * idf * 2.5

        for phrase, count in bi_counts.items():
            df = sum(1 for d in texts if phrase in d.lower())
            idf = math.log((num_docs + 1) / (df + 1)) + 1.0
            scores[phrase] = count * idf * 1.8

        for word, count in uni_counts.items():
            df = sum(1 for d in texts if word in d.lower())
            idf = math.log((num_docs + 1) / (df + 1)) + 1.0
            scores[word] = count * idf * 1.0

        sorted_phrases = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        # Deduplicate overlapping sub-phrases
        results: list[tuple[str, float]] = []
        for phrase, score in sorted_phrases:
            if not any(phrase != existing and phrase in existing for existing, _ in results):
                results.append((phrase, score))
            if len(results) >= top_n:
                break

        return results

