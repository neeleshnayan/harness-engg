"""Pydantic models and dataclasses for the Investment Thesis Generator."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Literal, Optional
from pydantic import BaseModel, Field


class Direction(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"


class DataSourceType(str, Enum):
    SEC_EDGAR = "sec_edgar"
    INVESTOR_RELATIONS = "investor_relations"
    GOOGLE_NEWS = "google_news"
    REDDIT = "reddit"
    HACKER_NEWS = "hacker_news"
    GITHUB = "github"
    GOOGLE_TRENDS = "google_trends"
    FRED_MACRO = "fred_macro"


class FactMetric(BaseModel):
    """An extracted quantitative fact or metric from evidence."""
    metric_type: str = Field(..., description="e.g. Revenue Growth, Capex, Guidance, Margin")
    segment: Optional[str] = Field(None, description="e.g. Datacenter, Services, Automotive")
    value: Optional[float] = Field(None, description="Numerical value if parsed")
    unit: Optional[str] = Field(None, description="e.g. %, $B, $M, units")
    raw_text: str = Field(..., description="Original snippet containing the fact")
    source: DataSourceType = Field(..., description="Source of the metric")
    source_url: Optional[str] = None
    recency_days: Optional[int] = None


class EvidenceItem(BaseModel):
    """A discrete unit of collected research evidence."""
    source: DataSourceType
    source_label: str
    title: str
    snippet: str
    url: Optional[str] = None
    published_at: Optional[str] = None
    recency_days: int = 30
    weight: float = 1.0  # e.g. 10-K: 10, Earnings: 9, IR: 8, News: 5, Reddit: 2
    sentiment: Literal["bullish", "bearish", "neutral"] = "neutral"
    is_management_mention: bool = False
    metrics: list[FactMetric] = Field(default_factory=list)


class DiscoveredTheme(BaseModel):
    """A discovered investment narrative/theme ranked by evidence."""
    theme_id: str
    title: str
    keywords: list[str] = Field(default_factory=list)
    score: int = Field(..., ge=0, le=100, description="Composite score (0..100)")
    frequency: int = Field(0, description="Evidence frequency count")
    recency_score: float = Field(0.0, description="Recency weighting score")
    management_mentions: int = Field(0, description="Direct management / filing quotes count")
    summary: str = Field(..., description="Deterministic theme narrative")
    evidence: list[EvidenceItem] = Field(default_factory=list)
    metrics: list[FactMetric] = Field(default_factory=list)


class BullDriver(BaseModel):
    driver_number: int
    theme_title: str
    driver_statement: str
    evidence_snippets: list[str] = Field(default_factory=list)
    key_metrics: list[str] = Field(default_factory=list)


class BearRisk(BaseModel):
    risk_number: int
    risk_title: str
    risk_statement: str
    counter_argument: Optional[str] = None
    evidence_snippets: list[str] = Field(default_factory=list)


class Catalyst(BaseModel):
    event_name: str
    timeframe: str
    expected_impact: str
    source_ref: Optional[str] = None


class InvalidationCondition(BaseModel):
    condition: str
    trigger_metric: Optional[str] = None
    threshold: Optional[str] = None


class DataSourceStatus(BaseModel):
    source: DataSourceType
    name: str
    status: Literal["healthy", "degraded", "offline"]
    item_count: int = 0
    latency_ms: int = 0
    message: Optional[str] = None


class GeneratedThesisResult(BaseModel):
    """Complete generated investment thesis (MVP #2) output."""
    thesis_id: Optional[str] = None
    ticker: str
    company_name: str
    direction: Direction
    title: str
    executive_summary: str
    top_themes: list[DiscoveredTheme]
    bull_case: list[BullDriver]
    bear_case: list[BearRisk]
    catalysts: list[Catalyst]
    invalidation_conditions: list[InvalidationCondition]
    sources_summary: dict[str, int] = Field(default_factory=dict)
    data_sources_status: list[DataSourceStatus] = Field(default_factory=list)
    raw_evidence_count: int = 0
    generated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    markdown_output: str
