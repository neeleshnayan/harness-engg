"use client";

import React, { useState, useRef } from "react";
import { FileText, Download, Check, ShieldCheck, TrendingUp, BarChart3 } from "lucide-react";
import { BacktestResult, ChatMessage } from "../types";

interface PDFReportExporterProps {
  title?: string;
  symbol?: string;
  backtestResult?: BacktestResult;
  messageContent?: string;
  username?: string;
  className?: string;
}

export default function PDFReportExporter({
  title = "Krypton Fund Strategy Backtest & Investment Report",
  symbol,
  backtestResult,
  messageContent,
  username = "Institutional Operator",
  className = "",
}: PDFReportExporterProps) {
  const [isExporting, setIsExporting] = useState(false);
  const [exported, setExported] = useState(false);
  const printRef = useRef<HTMLDivElement>(null);

  const metrics = backtestResult?.metrics || backtestResult?.data?.metrics || {};
  const allocations = backtestResult?.allocations || backtestResult?.data?.allocations || [];

  const handlePrint = () => {
    setIsExporting(true);
    setTimeout(() => {
      window.print();
      setIsExporting(false);
      setExported(true);
      setTimeout(() => setExported(false), 3000);
    }, 300);
  };

  return (
    <>
      <button
        onClick={handlePrint}
        disabled={isExporting}
        className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-teal-950/80 border border-teal-500/30 text-teal-300 hover:bg-teal-900/60 hover:border-teal-400/60 text-xs font-medium transition-all shadow-sm group ${className}`}
      >
        {exported ? (
          <Check size={14} className="text-emerald-400" />
        ) : (
          <FileText size={14} className="text-teal-400 group-hover:scale-110 transition-transform" />
        )}
        <span>{isExporting ? "Generating PDF..." : exported ? "Report Exported!" : "Export Institutional PDF"}</span>
      </button>

      {/* Hidden printable report layout optimized for CSS @media print */}
      <div className="hidden print:block print:fixed print:inset-0 print:bg-white print:text-slate-900 print:p-8 print:z-[99999]" ref={printRef}>
        <div className="max-w-4xl mx-auto space-y-6">
          {/* Header Bar */}
          <div className="flex items-center justify-between border-b-2 border-slate-900 pb-4">
            <div>
              <h1 className="text-2xl font-bold tracking-tight text-slate-900">KRYPTON FUND MANAGEMENT</h1>
              <p className="text-xs text-slate-500 uppercase tracking-widest mt-1">Quantitative Strategy & Investment Memo</p>
            </div>
            <div className="text-right text-xs text-slate-600">
              <p className="font-semibold text-slate-800">{new Date().toLocaleDateString("en-US", { month: "long", day: "numeric", year: "numeric" })}</p>
              <p>Prepared for: {username}</p>
            </div>
          </div>

          {/* Title Card */}
          <div className="bg-slate-50 p-4 rounded-lg border border-slate-200">
            <h2 className="text-lg font-semibold text-slate-900">{title}</h2>
            {symbol && <p className="text-xs text-slate-600 mt-0.5">Asset Symbol: <strong>{symbol.toUpperCase()}</strong></p>}
          </div>

          {/* Key Metrics Grid */}
          {metrics && (
            <div>
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-700 mb-2">Performance & Risk Metrics</h3>
              <div className="grid grid-cols-4 gap-3">
                <div className="p-3 bg-slate-100 rounded border border-slate-200">
                  <span className="text-[10px] text-slate-500 uppercase font-semibold">Total Return</span>
                  <p className="text-base font-bold text-emerald-700 mt-0.5">
                    {metrics.total_return !== undefined ? `${(metrics.total_return * 100).toFixed(2)}%` : "N/A"}
                  </p>
                </div>
                <div className="p-3 bg-slate-100 rounded border border-slate-200">
                  <span className="text-[10px] text-slate-500 uppercase font-semibold">Sharpe Ratio</span>
                  <p className="text-base font-bold text-slate-900 mt-0.5">
                    {metrics.sharpe_ratio !== undefined ? metrics.sharpe_ratio.toFixed(2) : "N/A"}
                  </p>
                </div>
                <div className="p-3 bg-slate-100 rounded border border-slate-200">
                  <span className="text-[10px] text-slate-500 uppercase font-semibold">Max Drawdown</span>
                  <p className="text-base font-bold text-rose-700 mt-0.5">
                    {metrics.max_drawdown !== undefined ? `${(metrics.max_drawdown * 100).toFixed(2)}%` : "N/A"}
                  </p>
                </div>
                <div className="p-3 bg-slate-100 rounded border border-slate-200">
                  <span className="text-[10px] text-slate-500 uppercase font-semibold">Win Rate</span>
                  <p className="text-base font-bold text-slate-900 mt-0.5">
                    {metrics.win_rate !== undefined ? `${(metrics.win_rate * 100).toFixed(1)}%` : "N/A"}
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* Allocations Table */}
          {allocations.length > 0 && (
            <div>
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-700 mb-2">Target Asset Allocations</h3>
              <table className="w-full text-xs text-left border border-slate-200 rounded">
                <thead className="bg-slate-100 text-slate-700 uppercase">
                  <tr>
                    <th className="p-2 border-b">Asset Symbol</th>
                    <th className="p-2 border-b">Allocation %</th>
                    <th className="p-2 border-b">Final Value ($)</th>
                  </tr>
                </thead>
                <tbody>
                  {allocations.map((alloc: any, idx: number) => (
                    <tr key={idx} className="border-b">
                      <td className="p-2 font-semibold">{alloc.symbol || alloc.asset || "N/A"}</td>
                      <td className="p-2">{(alloc.allocation_percentage || alloc.target_pct || 0).toFixed(1)}%</td>
                      <td className="p-2">${(alloc.final_value || 0).toLocaleString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Memo Reasoning Content */}
          {messageContent && (
            <div>
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-700 mb-2">Executive Investment Thesis</h3>
              <div className="p-4 bg-slate-50 rounded border border-slate-200 text-xs text-slate-800 leading-relaxed whitespace-pre-line">
                {messageContent}
              </div>
            </div>
          )}

          {/* Disclosures & Regulatory Footer */}
          <div className="border-t border-slate-200 pt-4 text-[10px] text-slate-500 leading-normal space-y-1">
            <p><strong>Institutional Disclosure:</strong> This investment report was generated by Clark Agentic Intelligence for Krypton Fund. Past performance is no guarantee of future returns.</p>
            <p>Confidential & Proprietary • Confidential Document for Krypton Fund LP Operators.</p>
          </div>
        </div>
      </div>
    </>
  );
}
