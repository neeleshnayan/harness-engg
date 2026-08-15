"use client";

import React, { useCallback, useEffect, useState } from "react";
import {
  AlertTriangle,
  ArrowDownRight,
  ArrowUpRight,
  BookOpen,
  Check,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Compass,
  Copy,
  Database,
  ExternalLink,
  FileText,
  Flame,
  Globe,
  Layers,
  Lightbulb,
  Loader2,
  Lock,
  Plus,
  RefreshCw,
  Search,
  Shield,
  ShieldAlert,
  Sparkles,
  TrendingDown,
  TrendingUp,
  Zap,
} from "lucide-react";
import { StudioHeader } from "../components/StudioHeader";
import { KT } from "../theme";
import { ClarkMarkdown } from "../components/ClarkMarkdown";
import { spineError } from "@/lib/spine_error";
import {
  fundApiClient,
  GeneratedThesisResult,
  ThesisDirection,
  DataSourceStatus,
  DiscoveredTheme,
  ThesisView,
  MemoView,
} from "@/lib/fund_api";

const QUICK_TICKERS = [
  { sym: "NVDA", name: "NVIDIA", hint: "Datacenter & Blackwell" },
  { sym: "AAPL", name: "Apple", hint: "Services & Silicon" },
  { sym: "MSFT", name: "Microsoft", hint: "Cloud & Copilot" },
  { sym: "TSLA", name: "Tesla", hint: "Autonomy & Energy" },
  { sym: "AMZN", name: "Amazon", hint: "AWS & Retail Margins" },
  { sym: "GOOGL", name: "Alphabet", hint: "Search & Cloud TPU" },
  { sym: "AMD", name: "AMD", hint: "MI300 & EPYC Share" },
  { sym: "SMCI", name: "Super Micro", hint: "Liquid Cooling Racks" },
  { sym: "PLTR", name: "Palantir", hint: "Enterprise AIP & DoD" },
  { sym: "INTC", name: "Intel", hint: "18A Node & Turnaround" },
];

const SOURCE_ICONS: Record<string, typeof Database> = {
  sec_edgar: FileText,
  google_news: Globe,
  reddit: Flame,
  hacker_news: Zap,
  github: Layers,
  fred_macro: Shield,
};

export default function ThesisStudioPage() {
  const [query, setQuery] = useState("Create thesis Long NVDA");
  const [direction, setDirection] = useState<ThesisDirection>("LONG");
  const [busy, setBusy] = useState(false);
  const [progressStage, setProgressStage] = useState<string>("");
  const [thesisResult, setThesisResult] = useState<GeneratedThesisResult | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  // Selected tab in evidence explorer
  const [evidenceFilter, setEvidenceFilter] = useState<string>("all");
  const [expandedThemeId, setExpandedThemeId] = useState<string | null>(null);

  // Promote modal state
  const [promoteOpen, setPromoteOpen] = useState(false);
  const [targetExposure, setTargetExposure] = useState<number>(5.0);
  const [horizon, setHorizon] = useState<string>("3-6 months");
  const [promoting, setPromoting] = useState(false);
  const [promoteSuccess, setPromoteSuccess] = useState<string | null>(null);

  // Existing fund theses
  const [fundTheses, setFundTheses] = useState<ThesisView[]>([]);
  const [selectedFundThesis, setSelectedFundThesis] = useState<ThesisView | null>(null);
  const [fundThesesOpen, setFundThesesOpen] = useState(false);

  const fetchFundTheses = useCallback(async () => {
    try {
      const res = await fundApiClient.getTheses();
      setFundTheses(res.theses || []);
    } catch (e) {
      console.debug("Failed to load fund theses:", e);
    }
  }, []);

  useEffect(() => {
    fetchFundTheses();
  }, [fetchFundTheses]);

  // Run initial generation or parameter-driven generation
  const runGeneration = useCallback(
    async (overrideQuery?: string, overrideDir?: ThesisDirection) => {
      const activeQuery = overrideQuery || query;
      const activeDir = overrideDir || direction;
      setBusy(true);
      setErr(null);
      setPromoteSuccess(null);

      const stages = [
        `Parsing query for ${activeDir} position...`,
        "Querying SEC EDGAR 10-K / 10-Q disclosures...",
        "Scraping real-time Google News RSS...",
        "Ingesting Reddit r/stocks & r/investing discussions...",
        "Scanning Hacker News & GitHub repositories...",
        "Aggregating FRED macro rate backdrop...",
        "Vectorizing n-grams & clustering emerging narratives...",
        "Ranking themes (0.5 freq + 0.3 recency + 0.2 mgmt)...",
        `Synthesizing ${activeDir} thesis & primary driver cases...`,
      ];

      let stageIdx = 0;
      setProgressStage(stages[0]);
      const stageInterval = setInterval(() => {
        stageIdx = (stageIdx + 1) % stages.length;
        setProgressStage(stages[stageIdx]);
      }, 650);

      try {
        const res = await fundApiClient.generateThesis(activeQuery, activeDir);
        setThesisResult(res);
        if (res.top_themes.length > 0) {
          setExpandedThemeId(res.top_themes[0].theme_id);
        }
      } catch (e: any) {
        setErr(spineError(e));
      } finally {
        clearInterval(stageInterval);
        setBusy(false);
      }
    },
    [query, direction]
  );

  useEffect(() => {
    runGeneration("Create thesis Long NVDA", "LONG");
  }, []);

  const handleDirectionChange = (newDir: ThesisDirection) => {
    setDirection(newDir);
    let updatedQ = query;
    if (/\b(long|short)\b/i.test(updatedQ)) {
      updatedQ = updatedQ.replace(/\b(long|short)\b/gi, newDir);
    } else {
      updatedQ = `Create thesis ${newDir} ${query.replace(/^create\s+thesis\s+/i, "").trim()}`;
    }
    setQuery(updatedQ);
    runGeneration(updatedQ, newDir);
  };

  const handlePromoteToFund = async () => {
    if (!thesisResult) return;
    setPromoting(true);
    setErr(null);
    try {
      const res = await fundApiClient.createThesisFromGeneration(
        thesisResult,
        targetExposure,
        horizon,
        "operator"
      );
      setPromoteSuccess(res.message);
      setPromoteOpen(false);
      fetchFundTheses();
    } catch (e: any) {
      setErr(spineError(e));
    } finally {
      setPromoting(false);
    }
  };

  const handleCopyMarkdown = () => {
    if (!thesisResult) return;
    navigator.clipboard.writeText(thesisResult.markdown_output);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // Filtered evidence items
  const allEvidence = thesisResult
    ? thesisResult.top_themes.flatMap((t) => t.evidence)
    : [];
  const uniqueEvidence = Array.from(
    new Map(allEvidence.map((item) => [item.title + item.snippet, item])).values()
  );
  const filteredEvidence =
    evidenceFilter === "all"
      ? uniqueEvidence
      : uniqueEvidence.filter((e) => e.source === evidenceFilter);

  return (
    <div className={KT.page}>
      <StudioHeader
        subtitle="Automatic theme discovery, multi-source research intelligence & deterministic thesis generation"
        actions={
          <div className="flex items-center gap-2">
            <button
              onClick={() => setFundThesesOpen(!fundThesesOpen)}
              className={KT.btnGhost}
              title="View live registered fund theses in the spine"
            >
              <BookOpen size={13} className="inline mr-1.5" />
              Fund Theses ({fundTheses.length})
            </button>
          </div>
        }
      />

      <main className="mx-auto max-w-[1600px] px-6 py-6 space-y-6">
        {/* Top Query & Generator Control Bar */}
        <section className={KT.panel}>
          <div className="p-5 border-b border-[var(--kt-border)]">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div>
                <span className={KT.label}>INVESTMENT THESIS GENERATOR</span>
                <h1 className="text-lg font-semibold text-[var(--kt-text-strong)] mt-0.5 flex items-center gap-2">
                  <Compass size={18} className={KT.accent} />
                  Autonomous Theme Discovery & Thesis Synthesis
                </h1>
              </div>

              {/* Direction Toggle */}
              <div className="flex items-center rounded-lg border border-[var(--kt-border)] bg-[var(--kt-inset)] p-0.5 text-xs">
                <button
                  type="button"
                  onClick={() => handleDirectionChange("LONG")}
                  className={`flex items-center gap-1 rounded-md px-3 py-1 font-medium transition-colors ${direction === "LONG"
                    ? "bg-[var(--kt-accent)] text-black font-semibold"
                    : "text-[var(--kt-text-dim)] hover:text-[var(--kt-text)]"
                    }`}
                >
                  <ArrowUpRight size={13} />
                  LONG
                </button>
                <button
                  type="button"
                  onClick={() => handleDirectionChange("SHORT")}
                  className={`flex items-center gap-1 rounded-md px-3 py-1 font-medium transition-colors ${direction === "SHORT"
                    ? "bg-[var(--kt-down)] text-white font-semibold"
                    : "text-[var(--kt-text-dim)] hover:text-[var(--kt-text)]"
                    }`}
                >
                  <ArrowDownRight size={13} />
                  SHORT
                </button>
              </div>
            </div>

            {/* Natural Language Query Bar */}
            <form
              onSubmit={(e) => {
                e.preventDefault();
                runGeneration();
              }}
              className="mt-4 flex flex-wrap items-center gap-2"
            >
              <div className="relative flex-1 min-w-[280px]">
                <Search
                  size={15}
                  className="absolute left-3.5 top-1/2 -translate-y-1/2 text-[var(--kt-text-muted)]"
                />
                <input
                  type="text"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="e.g. Create thesis Long NVDA, Short TSLA, or Long MSFT on cloud capex"
                  className={`${KT.input} w-full pl-9 font-mono text-sm`}
                />
              </div>

              <button
                type="submit"
                disabled={busy}
                className={`flex items-center gap-2 rounded-lg ${direction === "LONG" ? "bg-[var(--kt-accent)] text-black" : "bg-[var(--kt-down)] text-white"
                  } px-4 py-2 text-sm font-semibold transition-opacity hover:opacity-90 disabled:opacity-50`}
              >
                {busy ? (
                  <>
                    <Loader2 size={15} className="animate-spin" />
                    Discovering Themes...
                  </>
                ) : (
                  <>
                    <Sparkles size={15} />
                    Generate {direction} Thesis
                  </>
                )}
              </button>
            </form>

            {/* Quick Pick Chips */}
            <div className="mt-3 flex flex-wrap items-center gap-1.5">
              <span className={`text-[11px] ${KT.muted} mr-1`}>Quick Discovery:</span>
              {QUICK_TICKERS.map((t) => (
                <button
                  key={t.sym}
                  type="button"
                  onClick={() => {
                    const newQ = `Create thesis ${direction} ${t.sym}`;
                    setQuery(newQ);
                    runGeneration(newQ, direction);
                  }}
                  className="flex items-center gap-1 rounded-md border border-[var(--kt-border)] bg-[var(--kt-inset)] px-2.5 py-1 text-[11px] font-mono text-[var(--kt-text-dim)] transition-colors hover:border-[var(--kt-accent-border)] hover:text-[var(--kt-accent)]"
                >
                  <span className="font-semibold">{t.sym}</span>
                  <span className="text-[10px] text-[var(--kt-text-muted)] hidden sm:inline">
                    · {t.name}
                  </span>
                </button>
              ))}
            </div>
          </div>

          {/* Active Generation Progress or Live Data Sources Status Bar */}
          {busy ? (
            <div className="px-5 py-3.5 bg-[var(--kt-accent-bg)]/40 border-t border-[var(--kt-accent-border)] flex items-center justify-between gap-3 text-xs">
              <div className="flex items-center gap-2.5 text-[var(--kt-accent)]">
                <Loader2 size={14} className="animate-spin" />
                <span className="font-medium font-mono">{progressStage}</span>
              </div>
              <span className="text-[11px] text-[var(--kt-text-muted)] hidden sm:inline">
                Real-Time Synthesis: SEC EDGAR · News RSS · Reddit · HN · GitHub · Macro
              </span>
            </div>
          ) : thesisResult?.data_sources_status ? (
            <div className="px-5 py-3 bg-[var(--kt-surface)] flex flex-wrap items-center justify-between gap-3 border-t border-[var(--kt-border)]">
              <div className="flex flex-wrap items-center gap-3 text-xs">
                <span className={KT.label}>SOURCES INGESTED:</span>
                {thesisResult.data_sources_status.map((src) => {
                  const Icon = SOURCE_ICONS[src.source] || Database;
                  return (
                    <div
                      key={src.source}
                      className="flex items-center gap-1.5 rounded-full border border-[var(--kt-border)] bg-[var(--kt-inset)] px-2.5 py-0.5 text-[11px] font-mono"
                      title={`${src.name}: ${src.item_count} items in ${src.latency_ms}ms`}
                    >
                      <span
                        className={`h-1.5 w-1.5 rounded-full ${src.status === "healthy"
                          ? "bg-[var(--kt-accent)]"
                          : "bg-[var(--kt-warn)]"
                          }`}
                      />
                      <Icon size={11} className={KT.muted} />
                      <span className="text-[var(--kt-text)]">{src.name.split(" ")[0]}</span>
                      <span className={KT.muted}>({src.item_count})</span>
                    </div>
                  );
                })}
              </div>

              <div className="flex items-center gap-3 text-xs">
                <span className={KT.muted}>
                  Total Evidence:{" "}
                  <strong className="text-[var(--kt-text)] font-mono">
                    {thesisResult.raw_evidence_count} items
                  </strong>
                </span>
                <span className={KT.muted}>·</span>
                <span className={KT.muted}>
                  Latency:{" "}
                  <strong className="text-[var(--kt-text)] font-mono">
                    {Math.max(
                      ...thesisResult.data_sources_status.map((s) => s.latency_ms),
                      120
                    )}
                    ms
                  </strong>
                </span>
              </div>
            </div>
          ) : null}
        </section>

        {/* Error notification */}
        {err && (
          <div className="rounded-xl border border-[var(--kt-down)]/30 bg-[var(--kt-down)]/10 p-4 text-sm text-[var(--kt-down)] flex items-center justify-between gap-4">
            <div className="flex items-center gap-2">
              <AlertTriangle size={16} />
              <span>{err}</span>
            </div>
            <button
              onClick={() => runGeneration()}
              className="text-xs underline font-medium hover:opacity-80"
            >
              Retry
            </button>
          </div>
        )}

        {/* Promote Success Banner */}
        {promoteSuccess && (
          <div className="rounded-xl border border-[var(--kt-accent-border)] bg-[var(--kt-accent-bg)] p-4 text-sm text-[var(--kt-accent)] flex items-center justify-between gap-4">
            <div className="flex items-center gap-2">
              <CheckCircle2 size={16} />
              <span className="font-semibold">{promoteSuccess}</span>
            </div>
            <button
              onClick={() => setFundThesesOpen(true)}
              className="text-xs bg-[var(--kt-accent)] text-black px-3 py-1 rounded font-semibold hover:opacity-90"
            >
              View in Fund Theses
            </button>
          </div>
        )}

        {/* Main Content Area */}
        {thesisResult && (
          <div className="space-y-6">
            {/* Top Scorecard & Executive Summary */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* Left 2 Cols: Title & Exec Summary */}
              <section className={`${KT.panel} lg:col-span-2 p-6 flex flex-col justify-between`}>
                <div>
                  <div className="flex items-center justify-between gap-2 border-b border-[var(--kt-border)] pb-3">
                    <div className="flex items-center gap-2">
                      <span
                        className={`font-mono text-xs font-semibold px-2 py-0.5 rounded ${thesisResult.direction === "LONG"
                          ? "bg-[var(--kt-accent)]/20 text-[var(--kt-accent)] border border-[var(--kt-accent-border)]"
                          : "bg-[var(--kt-down)]/20 text-[var(--kt-down)] border border-[var(--kt-down)]/40"
                          }`}
                      >
                        {thesisResult.direction} {thesisResult.ticker}
                      </span>
                      <span className={`text-xs ${KT.muted}`}>
                        {thesisResult.company_name}
                      </span>
                    </div>

                    <div className="flex items-center gap-2">
                      <button
                        onClick={handleCopyMarkdown}
                        className={KT.btnGhost}
                        title="Copy full thesis as formatted Markdown"
                      >
                        {copied ? (
                          <>
                            <Check size={12} className="inline mr-1 text-[var(--kt-accent)]" />
                            Copied
                          </>
                        ) : (
                          <>
                            <Copy size={12} className="inline mr-1" />
                            Markdown
                          </>
                        )}
                      </button>

                      <button
                        onClick={() => setPromoteOpen(true)}
                        className="flex items-center gap-1.5 rounded-lg bg-[var(--kt-accent)] px-3 py-1.5 text-xs font-semibold text-black transition-opacity hover:opacity-90"
                      >
                        <Plus size={13} />
                        Promote to Fund
                      </button>
                    </div>
                  </div>

                  <h2 className="text-xl font-bold tracking-tight text-[var(--kt-text-strong)] mt-4">
                    {thesisResult.title}
                  </h2>

                  <p className={`mt-3 text-sm leading-relaxed ${KT.body}`}>
                    {thesisResult.executive_summary}
                  </p>
                </div>

                <div className="mt-6 pt-4 border-t border-[var(--kt-border)] flex flex-wrap items-center justify-between gap-4 text-xs">
                  <div className="flex items-center gap-4">
                    <span className={KT.muted}>
                      Primary Driver:{" "}
                      <strong className="text-[var(--kt-text)]">
                        {thesisResult.top_themes[0]?.title || "Core Focus"}
                      </strong>
                    </span>
                    <span className={KT.muted}>·</span>
                    <span className={KT.muted}>
                      Horizon: <strong className="text-[var(--kt-text)]">3-6 Months</strong>
                    </span>
                  </div>
                  <span className={`text-[11px] font-mono ${KT.muted}`}>
                    Generated {new Date(thesisResult.generated_at).toLocaleTimeString()}
                  </span>
                </div>
              </section>

              {/* Right Col: Conviction & Top Theme Rank Radar */}
              <section className={`${KT.panel} p-6 flex flex-col justify-between`}>
                <div>
                  <div className={KT.label}>CONVICTION & DISCOVERY RANK</div>
                  <div className="mt-4 flex items-baseline gap-3">
                    <span className={KT.hero}>
                      {thesisResult.top_themes[0]?.score || 94}
                    </span>
                    <span className={`text-sm ${KT.muted}`}>/ 100 Composite Score</span>
                  </div>

                  <div className="mt-4 space-y-2.5">
                    <div className="text-xs font-medium text-[var(--kt-text-dim)] flex items-center justify-between">
                      <span>Top Theme Ranking</span>
                      <span className={KT.muted}>Score</span>
                    </div>

                    {thesisResult.top_themes.slice(0, 4).map((t, idx) => (
                      <div key={t.theme_id} className="space-y-1">
                        <div className="flex items-center justify-between text-xs font-mono">
                          <span className="truncate pr-2 text-[var(--kt-text)]">
                            {idx + 1}. {t.title}
                          </span>
                          <span className="font-semibold text-[var(--kt-accent)]">
                            {t.score}
                          </span>
                        </div>
                        <div className={KT.barTrack}>
                          <div
                            className={KT.barFill}
                            style={{ width: `${t.score}%` }}
                          />
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="mt-4 pt-3 border-t border-[var(--kt-border)] text-[11px] text-[var(--kt-text-muted)]">
                  Formula: <code>0.5 * frequency + 0.3 * recency + 0.2 * management_mentions</code>
                </div>
              </section>
            </div>

            {/* Top Themes Discovery Cards */}
            <section className={KT.panel}>
              <div className="border-b border-[var(--kt-border)] px-6 py-4 flex items-center justify-between">
                <div>
                  <span className={KT.label}>DISCOVERED INVESTMENT THEMES ({thesisResult.ticker})</span>
                  <h3 className="text-sm font-semibold text-[var(--kt-text-strong)] mt-0.5">
                    Emerging Narratives & Verified Evidence Drivers
                  </h3>
                </div>
                <span className={`text-xs ${KT.muted}`}>
                  {thesisResult.top_themes.length} Themes Ranked
                </span>
              </div>

              <div className="divide-y divide-[var(--kt-border)]">
                {thesisResult.top_themes.map((theme, i) => {
                  const isExpanded = expandedThemeId === theme.theme_id;
                  return (
                    <div key={theme.theme_id} className="p-5 transition-colors hover:bg-[var(--kt-inset)]/30">
                      <div
                        onClick={() =>
                          setExpandedThemeId(isExpanded ? null : theme.theme_id)
                        }
                        className="cursor-pointer flex items-start justify-between gap-4"
                      >
                        <div className="flex items-start gap-3.5">
                          <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg border border-[var(--kt-accent-border)] bg-[var(--kt-accent-bg)] font-mono text-xs font-bold text-[var(--kt-accent)]">
                            {i + 1}
                          </span>
                          <div>
                            <div className="flex flex-wrap items-center gap-2">
                              <h4 className="text-sm font-semibold text-[var(--kt-text-strong)]">
                                {theme.title}
                              </h4>
                              <span className={KT.chip}>Score: {theme.score}/100</span>
                              <span className="text-[11px] font-mono text-[var(--kt-text-muted)]">
                                ({theme.frequency} evidence items · {theme.management_mentions} filing citations)
                              </span>
                            </div>

                            {/* <p className={`mt-1.5 text-xs leading-relaxed ${KT.body}`}>
                              {theme.summary}
                            </p> */}

                            {/* Extracted quantitative fact pills */}
                            {/* {theme.metrics && theme.metrics.length > 0 && (
                              <div className="mt-2.5 flex flex-wrap items-center gap-1.5">
                                {theme.metrics.map((m, idx) => (
                                  <span
                                    key={idx}
                                    className="inline-flex items-center gap-1 rounded-md border border-[var(--kt-border)] bg-[var(--kt-inset)] px-2 py-0.5 text-[10px] font-mono text-[var(--kt-text)]"
                                  >
                                    <span className="font-semibold text-[var(--kt-accent)]">
                                      {m.metric_type}:
                                    </span>
                                    {m.raw_text}
                                  </span>
                                ))}
                              </div>
                            )} */}
                          </div>
                        </div>

                        <button className="text-[var(--kt-text-muted)] hover:text-[var(--kt-text)] pt-1">
                          {isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                        </button>
                      </div>

                      {/* Expanded Evidence Sub-block */}
                      {isExpanded && (
                        <div className="mt-4 pt-3 border-t border-[var(--kt-border)] pl-10 space-y-2.5">
                          <div className={KT.label}>SUPPORTING CITATIONS & QUOTES</div>
                          {theme.evidence.map((ev, evIdx) => (
                            <div
                              key={evIdx}
                              className="rounded-lg border border-[var(--kt-border)] bg-[var(--kt-surface)] p-3 text-xs"
                            >
                              <div className="flex items-center justify-between gap-2">
                                <span className="font-semibold text-[var(--kt-text-strong)]">
                                  [{ev.source_label}] {ev.title}
                                </span>
                                {ev.url && (
                                  <a
                                    href={ev.url}
                                    target="_blank"
                                    rel="noreferrer"
                                    className="text-[var(--kt-accent)] hover:underline flex items-center gap-1"
                                  >
                                    Source <ExternalLink size={10} />
                                  </a>
                                )}
                              </div>
                              <p className={`mt-1.5 ${KT.body} leading-relaxed font-mono text-[11px]`}>
                                {/* "{ev.snippet}" */}
                              </p>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </section>

            {/* Side-by-Side Case Analysis (Long vs Short Aware) */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Primary Drivers (Bull Drivers if LONG, Downside Drivers if SHORT) */}
              <section className={KT.panel}>
                <div
                  className={`border-b border-[var(--kt-border)] px-5 py-3.5 flex items-center justify-between ${thesisResult.direction === "LONG"
                    ? "bg-[var(--kt-accent-bg)]/20 text-[var(--kt-accent)]"
                    : "bg-[var(--kt-down)]/15 text-[var(--kt-down)]"
                    }`}
                >
                  <div className="flex items-center gap-2">
                    {thesisResult.direction === "LONG" ? (
                      <TrendingUp size={16} className={KT.accent} />
                    ) : (
                      <TrendingDown size={16} className={KT.down} />
                    )}
                    <span className="text-xs font-semibold uppercase tracking-wider">
                      {thesisResult.direction === "LONG"
                        ? "Bull Case (Key Growth Drivers)"
                        : "Short Thesis (Primary Downside Drivers)"}
                    </span>
                  </div>
                  <span className={KT.chip}>{thesisResult.bull_case.length} Drivers</span>
                </div>

                <div className="p-5 space-y-4">
                  {thesisResult.bull_case.map((driver) => (
                    <div
                      key={driver.driver_number}
                      className="rounded-xl border border-[var(--kt-border)] bg-[var(--kt-surface)] p-4 space-y-2"
                    >
                      <div className="flex items-center gap-2">
                        <span
                          className={`flex h-5 w-5 items-center justify-center rounded-full font-mono text-[11px] font-bold ${thesisResult.direction === "LONG"
                            ? "bg-[var(--kt-accent)]/20 text-[var(--kt-accent)]"
                            : "bg-[var(--kt-down)]/20 text-[var(--kt-down)]"
                            }`}
                        >
                          {driver.driver_number}
                        </span>
                        <h4 className="text-xs font-semibold text-[var(--kt-text-strong)]">
                          {driver.theme_title}
                        </h4>
                      </div>
                      <p className={`text-xs ${KT.body} leading-relaxed`}>
                        {driver.driver_statement}
                      </p>
                      {driver.evidence_snippets.length > 0 && (
                        <div className="pt-2 border-t border-[var(--kt-border)] space-y-1">
                          {driver.evidence_snippets.map((snip, sIdx) => (
                            <div
                              key={sIdx}
                              className={`text-[11px] font-mono ${KT.muted} leading-relaxed`}
                            >
                              • {snip}
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </section>

              {/* Counter Risks (Bear Risks if LONG, Upside Risks if SHORT) */}
              <section className={KT.panel}>
                <div
                  className={`border-b border-[var(--kt-border)] px-5 py-3.5 flex items-center justify-between ${thesisResult.direction === "LONG"
                    ? "bg-[var(--kt-down)]/10 text-[var(--kt-down)]"
                    : "bg-[var(--kt-accent-bg)]/20 text-[var(--kt-accent)]"
                    }`}
                >
                  <div className="flex items-center gap-2">
                    {thesisResult.direction === "LONG" ? (
                      <TrendingDown size={16} className={KT.down} />
                    ) : (
                      <TrendingUp size={16} className={KT.accent} />
                    )}
                    <span className="text-xs font-semibold uppercase tracking-wider">
                      {thesisResult.direction === "LONG"
                        ? "Bear Case & Critical Risks"
                        : "Upside Risks & Counter-Theses"}
                    </span>
                  </div>
                  <span className={KT.chip}>{thesisResult.bear_case.length} Risk Factors</span>
                </div>

                <div className="p-5 space-y-4">
                  {thesisResult.bear_case.map((risk) => (
                    <div
                      key={risk.risk_number}
                      className="rounded-xl border border-[var(--kt-border)] bg-[var(--kt-surface)] p-4 space-y-2"
                    >
                      <div className="flex items-center gap-2">
                        <span
                          className={`flex h-5 w-5 items-center justify-center rounded-full font-mono text-[11px] font-bold ${thesisResult.direction === "LONG"
                            ? "bg-[var(--kt-down)]/20 text-[var(--kt-down)]"
                            : "bg-[var(--kt-accent)]/20 text-[var(--kt-accent)]"
                            }`}
                        >
                          {risk.risk_number}
                        </span>
                        <h4 className="text-xs font-semibold text-[var(--kt-text-strong)]">
                          {risk.risk_title}
                        </h4>
                      </div>
                      <p className={`text-xs ${KT.body} leading-relaxed`}>
                        <strong
                          className={
                            thesisResult.direction === "LONG"
                              ? "text-[var(--kt-down)]"
                              : "text-[var(--kt-accent)]"
                          }
                        >
                          {thesisResult.direction === "LONG" ? "Risk:" : "Upside Risk:"}
                        </strong>{" "}
                        {risk.risk_statement}
                      </p>
                      {risk.counter_argument && (
                        <p className={`text-[11px] ${KT.muted} pt-1 border-t border-[var(--kt-border)]`}>
                          <strong className="text-[var(--kt-text-strong)]">
                            {thesisResult.direction === "LONG" ? "Counter-Defense:" : "Short Perspective:"}
                          </strong>{" "}
                          {risk.counter_argument}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              </section>
            </div>

            {/* Catalysts & Invalidation Engine */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Catalysts */}
              <section className={KT.panel}>
                <div className="border-b border-[var(--kt-border)] px-5 py-3 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Zap size={15} className={KT.accent} />
                    <span className={KT.label}>FORWARD CATALYSTS & TIMELINE</span>
                  </div>
                </div>
                <div className="p-5 space-y-3">
                  {thesisResult.catalysts.map((cat, idx) => (
                    <div
                      key={idx}
                      className="rounded-xl border border-[var(--kt-border)] bg-[var(--kt-inset)] p-3.5 text-xs space-y-1"
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-semibold text-[var(--kt-text-strong)]">
                          {cat.event_name}
                        </span>
                        <span className={KT.chip}>{cat.timeframe}</span>
                      </div>
                      <p className={KT.body}>{cat.expected_impact}</p>
                      {cat.source_ref && (
                        <div className={`text-[10px] ${KT.muted} pt-1 font-mono`}>
                          Source: {cat.source_ref}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </section>

              {/* Invalidation Conditions */}
              <section className={KT.panel}>
                <div className="border-b border-[var(--kt-border)] px-5 py-3 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <ShieldAlert size={15} className={KT.down} />
                    <span className={KT.label}>
                      {thesisResult.direction === "LONG"
                        ? "FALSIFIABLE LONG EXIT TRIGGERS"
                        : "FALSIFIABLE SHORT STOP-LOSS TRIGGERS"}
                    </span>
                  </div>
                </div>
                <div className="p-5 space-y-3">
                  {thesisResult.invalidation_conditions.map((inv, idx) => (
                    <div
                      key={idx}
                      className="rounded-xl border border-[var(--kt-down)]/30 bg-[var(--kt-down)]/5 p-3.5 text-xs space-y-1"
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-semibold text-[var(--kt-down)]">
                          Exit Trigger #{idx + 1}
                        </span>
                        <span className="font-mono text-[10px] text-[var(--kt-down)] font-bold">
                          {inv.trigger_metric || "Threshold Breach"}
                        </span>
                      </div>
                      <p className={KT.body}>{inv.condition}</p>
                    </div>
                  ))}
                </div>
              </section>
            </div>

            {/* Evidence & Multi-Source Explorer */}
            <section className={KT.panel}>
              <div className="border-b border-[var(--kt-border)] px-6 py-4 flex flex-wrap items-center justify-between gap-4">
                <div>
                  <span className={KT.label}>RESEARCH EVIDENCE CORPUS</span>
                  <h3 className="text-sm font-semibold text-[var(--kt-text-strong)] mt-0.5">
                    Multi-Source Primary Documents & Datasets ({thesisResult.ticker})
                  </h3>
                </div>

                {/* Source Tabs */}
                <div className="flex flex-wrap items-center gap-1.5 text-xs">
                  {[
                    { id: "all", label: `All (${uniqueEvidence.length})` },
                    { id: "sec_edgar", label: "SEC EDGAR" },
                    { id: "google_news", label: "Google News" },
                    { id: "reddit", label: "Reddit" },
                    { id: "hacker_news", label: "Hacker News" },
                    { id: "github", label: "GitHub" },
                    { id: "fred_macro", label: "FRED Macro" },
                  ].map((tab) => (
                    <button
                      key={tab.id}
                      type="button"
                      onClick={() => setEvidenceFilter(tab.id)}
                      className={`rounded-lg px-2.5 py-1 text-xs font-mono transition-colors ${evidenceFilter === tab.id
                        ? "bg-[var(--kt-accent-bg)] text-[var(--kt-accent)] border border-[var(--kt-accent-border)] font-semibold"
                        : "bg-[var(--kt-inset)] text-[var(--kt-text-dim)] border border-[var(--kt-border)] hover:text-[var(--kt-text)]"
                        }`}
                    >
                      {tab.label}
                    </button>
                  ))}
                </div>
              </div>

              <div className="p-6 grid grid-cols-1 md:grid-cols-2 gap-4 max-h-[500px] overflow-y-auto">
                {filteredEvidence.map((item, idx) => {
                  const Icon = SOURCE_ICONS[item.source] || Database;
                  return (
                    <div
                      key={idx}
                      className="rounded-xl border border-[var(--kt-border)] bg-[var(--kt-surface)] p-4 flex flex-col justify-between space-y-3"
                    >
                      <div>
                        <div className="flex items-center justify-between gap-2">
                          <span className="flex items-center gap-1.5 text-[10px] font-mono text-[var(--kt-text-muted)] uppercase">
                            <Icon size={11} className={KT.accent} />
                            {item.source_label}
                          </span>
                          <span
                            className={`text-[10px] font-mono px-1.5 py-0.2 rounded ${item.sentiment === "bullish"
                              ? "text-[var(--kt-accent)] bg-[var(--kt-accent-bg)]"
                              : item.sentiment === "bearish"
                                ? "text-[var(--kt-down)] bg-[var(--kt-down)]/10"
                                : "text-[var(--kt-text-muted)] bg-[var(--kt-inset)]"
                              }`}
                          >
                            {item.sentiment}
                          </span>
                        </div>

                        <h4 className="text-xs font-semibold text-[var(--kt-text-strong)] mt-1.5">
                          {item.title}
                        </h4>

                        <p className={`mt-1.5 text-xs ${KT.body} leading-relaxed line-clamp-3`}>
                          {item.snippet}
                        </p>
                      </div>

                      <div className="pt-2 border-t border-[var(--kt-border)] flex items-center justify-between text-[10px] font-mono text-[var(--kt-text-muted)]">
                        <span>Weight: {item.weight.toFixed(1)}</span>
                        {item.url && (
                          <a
                            href={item.url}
                            target="_blank"
                            rel="noreferrer"
                            className="text-[var(--kt-accent)] hover:underline flex items-center gap-1"
                          >
                            View Record <ExternalLink size={10} />
                          </a>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </section>
          </div>
        )}

        {/* Promote to Fund Modal */}
        {promoteOpen && thesisResult && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
            <div className={`${KT.panel} w-full max-w-lg p-6 space-y-5 border border-[var(--kt-accent-border)]`}>
              <div className="flex items-center justify-between border-b border-[var(--kt-border)] pb-3">
                <div>
                  <div className={KT.label}>FUND LIFECYCLE INTEGRATION</div>
                  <h3 className="text-base font-semibold text-[var(--kt-text-strong)] mt-0.5">
                    Promote to Fund Thesis & Memo
                  </h3>
                </div>
                <button
                  onClick={() => setPromoteOpen(false)}
                  className="text-[var(--kt-text-muted)] hover:text-[var(--kt-text)]"
                >
                  ✕
                </button>
              </div>

              <div className="space-y-4 text-xs">
                <div>
                  <label className="font-semibold text-[var(--kt-text)] block mb-1">
                    Thesis Title & Claim
                  </label>
                  <input
                    type="text"
                    readOnly
                    value={thesisResult.title}
                    className={`${KT.input} w-full opacity-80`}
                  />
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="font-semibold text-[var(--kt-text)] block mb-1">
                      Target Exposure (% NAV)
                    </label>
                    <input
                      type="number"
                      step="0.5"
                      min="1"
                      max="20"
                      value={targetExposure}
                      onChange={(e) => setTargetExposure(Number(e.target.value))}
                      className={`${KT.input} w-full font-mono`}
                    />
                  </div>

                  <div>
                    <label className="font-semibold text-[var(--kt-text)] block mb-1">
                      Holding Horizon
                    </label>
                    <input
                      type="text"
                      value={horizon}
                      onChange={(e) => setHorizon(e.target.value)}
                      className={`${KT.input} w-full`}
                    />
                  </div>
                </div>

                <div className="rounded-lg bg-[var(--kt-inset)] p-3 text-[11px] text-[var(--kt-text-muted)] leading-relaxed">
                  Promoting registers an auditable <code>ThesisCreated</code> event and generates a formal <code>InvestmentMemo</code> in the ClarkHarness spine. This allows the thesis to be attached to proposed orders in the Approval Desk and evaluated in post-mortems.
                </div>
              </div>

              <div className="flex items-center justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setPromoteOpen(false)}
                  className={KT.btnGhost}
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={handlePromoteToFund}
                  disabled={promoting}
                  className="flex items-center gap-2 rounded-lg bg-[var(--kt-accent)] px-4 py-2 text-xs font-semibold text-black hover:opacity-90 disabled:opacity-50"
                >
                  {promoting ? <Loader2 size={13} className="animate-spin" /> : <Check size={13} />}
                  Confirm Promotion
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Fund Theses Drawer / Gallery */}
        {fundThesesOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-end bg-black/60 backdrop-blur-sm">
            <div className="h-full w-full max-w-xl bg-[var(--kt-bg)] border-l border-[var(--kt-border)] p-6 flex flex-col justify-between overflow-y-auto space-y-6">
              <div>
                <div className="flex items-center justify-between border-b border-[var(--kt-border)] pb-3">
                  <div>
                    <div className={KT.label}>KRYPTON FUND LEDGER</div>
                    <h3 className="text-base font-semibold text-[var(--kt-text-strong)] mt-0.5">
                      Live Registered Theses ({fundTheses.length})
                    </h3>
                  </div>
                  <button
                    onClick={() => setFundThesesOpen(false)}
                    className="text-[var(--kt-text-muted)] hover:text-[var(--kt-text)] text-sm font-semibold"
                  >
                    ✕
                  </button>
                </div>

                <div className="mt-5 space-y-3">
                  {fundTheses.length === 0 ? (
                    <div className="text-center py-12 text-xs text-[var(--kt-text-muted)]">
                      No active theses registered in the fund spine yet. Generate and promote one above!
                    </div>
                  ) : (
                    fundTheses.map((t) => (
                      <div
                        key={t.thesis_id}
                        onClick={() => setSelectedFundThesis(t)}
                        className={`rounded-xl border p-4 transition-colors cursor-pointer ${selectedFundThesis?.thesis_id === t.thesis_id
                          ? "border-[var(--kt-accent)] bg-[var(--kt-accent-bg)]/20"
                          : "border-[var(--kt-border)] bg-[var(--kt-surface)] hover:border-[var(--kt-accent-border)]"
                          }`}
                      >
                        <div className="flex items-center justify-between gap-2">
                          <span className="font-semibold text-xs text-[var(--kt-text-strong)]">
                            {t.title}
                          </span>
                          <span
                            className={`text-[10px] font-mono px-2 py-0.5 rounded-full ${t.status === "active"
                              ? "bg-[var(--kt-accent-bg)] text-[var(--kt-accent)] border border-[var(--kt-accent-border)]"
                              : t.status === "reviewed"
                                ? "bg-[var(--kt-inset)] text-[var(--kt-text-muted)]"
                                : "bg-[var(--kt-warn)]/10 text-[var(--kt-warn)] border border-[var(--kt-warn)]/30"
                              }`}
                          >
                            {t.status.toUpperCase()}
                          </span>
                        </div>

                        {t.claim && (
                          <p className={`mt-2 text-xs ${KT.body} line-clamp-2`}>
                            {t.claim}
                          </p>
                        )}

                        <div className="mt-3 pt-2 border-t border-[var(--kt-border)] flex items-center justify-between text-[10px] font-mono text-[var(--kt-text-muted)]">
                          <span>Assets: {t.assets?.join(", ") || "—"}</span>
                          <span>Target: {t.target_exposure_pct ? `${t.target_exposure_pct}% NAV` : "—"}</span>
                          <span>{t.has_postmortem ? "✅ Post-Mortem" : "⏳ Active"}</span>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>

              <div className="pt-4 border-t border-[var(--kt-border)] flex items-center justify-between">
                <button
                  onClick={fetchFundTheses}
                  className={KT.btnGhost}
                >
                  <RefreshCw size={12} className="inline mr-1" />
                  Refresh
                </button>
                <button
                  onClick={() => setFundThesesOpen(false)}
                  className="rounded-lg bg-[var(--kt-accent)] text-black px-4 py-1.5 text-xs font-semibold"
                >
                  Done
                </button>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
