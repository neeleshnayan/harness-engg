from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.fund import router as fund_router
from app.fund.events import EventStore
from app.fund.thesis_generator.models import Direction, GeneratedThesisResult
from app.fund.thesis_generator.nlp.fact_extractor import FactExtractor
from app.fund.thesis_generator.nlp.keyword_extractor import KeywordExtractor
from app.fund.thesis_generator.nlp.theme_discovery import ThemeDiscoveryEngine
from app.fund.thesis_generator.nlp.theme_ranker import ThemeRanker
from app.fund.thesis_generator.nlp.evidence_mapper import EvidenceMapper
from app.fund.thesis_generator.query_parser import QueryParser
from app.fund.thesis_generator.service import ThesisGeneratorService

test_app = FastAPI()
test_app.include_router(fund_router, prefix="/api/v1")


def test_query_parser():
    # Long query
    p1 = QueryParser.parse("Create thesis Long NVDA")
    assert p1.ticker == "NVDA"
    assert p1.direction == Direction.LONG

    # Short query
    p2 = QueryParser.parse("Create thesis Short TSLA")
    assert p2.ticker == "TSLA"
    assert p2.direction == Direction.SHORT

    # With theme hint
    p3 = QueryParser.parse("Create thesis Long MSFT on cloud capex")
    assert p3.ticker == "MSFT"
    assert p3.direction == Direction.LONG
    assert p3.theme_hint == "cloud capex"

    # Bare ticker or company name
    p4 = QueryParser.parse("NVIDIA")
    assert p4.ticker == "NVDA"
    assert p4.direction == Direction.LONG

    p5 = QueryParser.parse("Short AAPL")
    assert p5.ticker == "AAPL"
    assert p5.direction == Direction.SHORT


def test_fact_extractor():
    from app.fund.thesis_generator.models import DataSourceType

    sample_text = (
        "NVIDIA datacenter revenue grew 82% YoY to $30.0 billion in Q3. "
        "Capex reached $12.5 billion to support Blackwell platform ramp. "
        "Management gross margin was 75.4% and guidance expects revenue of $37.5 billion next quarter."
    )
    facts = FactExtractor.extract_from_text(sample_text, DataSourceType.SEC_EDGAR)
    assert len(facts) >= 2

    # Check for revenue growth or capex
    types = [f.metric_type for f in facts]
    assert any(t in ("Revenue Growth", "Growth Rate", "Capex", "Margin", "Guidance", "Financial Volume") for t in types)


def test_keyword_extractor():
    corpus = [
        "NVIDIA Blackwell platform architecture accelerates datacenter compute and enterprise AI workloads.",
        "Hyperscaler capex commitments expand for sovereign AI infrastructure and networking clusters.",
        "Datacenter revenue growth driven by Blackwell adoption and high bandwidth memory capacity.",
    ]
    keywords = KeywordExtractor.extract_keywords(corpus, top_n=10)
    assert len(keywords) > 0
    kw_names = [k for k, _ in keywords]
    assert any("blackwell" in k or "datacenter" in k or "capex" in k for k in kw_names)


def test_theme_ranker_and_evidence():
    from app.fund.thesis_generator.models import DataSourceType, EvidenceItem
    from app.fund.thesis_generator.nlp.theme_discovery import DiscoveredCluster

    evidence = [
        EvidenceItem(
            source=DataSourceType.SEC_EDGAR,
            source_label="SEC 10-K",
            title="SEC Filing 10-K",
            snippet="Datacenter revenue +82% YoY with Blackwell architecture volume ramp.",
            recency_days=10,
            weight=10.0,
            sentiment="bullish",
            is_management_mention=True,
        ),
        EvidenceItem(
            source=DataSourceType.GOOGLE_NEWS,
            source_label="Google News",
            title="Hyperscaler Capex Ramp",
            snippet="Major cloud providers increase capex allocations for AI infrastructure.",
            recency_days=2,
            weight=6.0,
            sentiment="bullish",
            is_management_mention=False,
        ),
    ]

    cluster = DiscoveredCluster(
        theme_title="Datacenter Growth & Blackwell Adoption",
        keywords=["datacenter", "blackwell", "capex"],
        matching_evidence=evidence,
    )

    ranked = ThemeRanker.rank_and_build([cluster], [])
    assert len(ranked) == 1
    theme = ranked[0]
    assert theme.score > 50
    assert theme.management_mentions == 1
    assert theme.frequency == 2


def test_thesis_generator_service(wire):
    svc = ThesisGeneratorService(store=wire.store)

    # 1. Generate thesis for NVDA (LONG)
    nvda_long = svc.generate_thesis("Create thesis Long NVDA")
    assert nvda_long.ticker == "NVDA"
    assert nvda_long.direction == Direction.LONG
    assert any("Datacenter" in t.title or "Blackwell" in t.title for t in nvda_long.top_themes)
    assert len(nvda_long.bull_case) >= 3
    assert "# Investment Thesis" in nvda_long.markdown_output

    # 2. Generate thesis for TSLA (SHORT)
    tsla_short = svc.generate_thesis("Create thesis Short TSLA")
    assert tsla_short.ticker == "TSLA"
    assert tsla_short.direction == Direction.SHORT
    assert any("Margin" in t.title or "Competition" in t.title or "Demand" in t.title for t in tsla_short.top_themes)
    assert tsla_short.title.startswith("SHORT TSLA")
    assert "SHORT conviction" in tsla_short.executive_summary

    # 3. Promote to fund
    promotion = svc.promote_to_fund(nvda_long, actor="test-analyst", target_exposure_pct=4.5)
    assert "thesis" in promotion
    assert "memo" in promotion
    assert promotion["thesis"]["status"] == "draft"
    assert promotion["thesis"]["target_exposure_pct"] == 4.5
    assert len(promotion["thesis"]["assets"]) == 1


def test_ticker_and_direction_differentiation(wire):
    svc = ThesisGeneratorService(store=wire.store)

    # Compare AAPL vs TSLA vs NVDA
    aapl_res = svc.generate_thesis("Create thesis Long AAPL")
    tsla_res = svc.generate_thesis("Create thesis Long TSLA")
    nvda_res = svc.generate_thesis("Create thesis Long NVDA")

    # Titles and themes must be distinct
    assert aapl_res.company_name == "Apple Inc."
    assert tsla_res.company_name == "Tesla, Inc."
    assert nvda_res.company_name == "NVIDIA Corporation"

    aapl_theme_titles = [t.title for t in aapl_res.top_themes]
    tsla_theme_titles = [t.title for t in tsla_res.top_themes]
    nvda_theme_titles = [t.title for t in nvda_res.top_themes]

    assert aapl_theme_titles != tsla_theme_titles
    assert tsla_theme_titles != nvda_theme_titles
    assert any("Services" in t or "Apple" in t or "Silicon" in t for t in aapl_theme_titles)
    assert any("FSD" in t or "Robotaxi" in t or "Energy" in t or "Vehicle" in t for t in tsla_theme_titles)

    # Compare Long vs Short for same ticker (NVDA)
    nvda_short = svc.generate_thesis("Create thesis Short NVDA")
    assert nvda_short.direction == Direction.SHORT
    assert nvda_res.direction == Direction.LONG
    assert nvda_short.title != nvda_res.title
    assert "SHORT" in nvda_short.title
    assert "LONG" in nvda_res.title


def test_fastapi_thesis_endpoints(wire):
    client = TestClient(test_app)

    # POST /api/v1/fund/theses/generate (LONG NVDA)
    res = client.post("/api/v1/fund/theses/generate", json={"query": "Create thesis Long NVDA"})
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["ticker"] == "NVDA"
    assert data["direction"] == "LONG"
    assert len(data["top_themes"]) > 0

    # POST /api/v1/fund/theses/generate (SHORT TSLA)
    res_short = client.post("/api/v1/fund/theses/generate", json={"query": "Create thesis Short TSLA"})
    assert res_short.status_code == 200, res_short.text
    data_short = res_short.json()
    assert data_short["ticker"] == "TSLA"
    assert data_short["direction"] == "SHORT"
    assert "SHORT TSLA" in data_short["title"]

    # POST /api/v1/fund/theses/from-generation
    promote_res = client.post(
        "/api/v1/fund/theses/from-generation",
        json={
            "generated_thesis": data,
            "target_exposure_pct": 5.0,
            "horizon": "3-6 months",
            "actor": "operator",
        },
    )
    assert promote_res.status_code == 200, promote_res.text
    promote_data = promote_res.json()
    assert "thesis" in promote_data
    assert "memo" in promote_data
    thesis_id = promote_data["thesis"]["thesis_id"]

    # Verify thesis exists in fund list
    get_res = client.get(f"/api/v1/fund/theses/{thesis_id}")
    assert get_res.status_code == 200
    assert get_res.json()["thesis_id"] == thesis_id

    # GET /api/v1/fund/theses/sources/status
    status_res = client.get("/api/v1/fund/theses/sources/status")
    assert status_res.status_code == 200
    sources_data = status_res.json()
    assert "sources" in sources_data
    assert len(sources_data["sources"]) >= 4
