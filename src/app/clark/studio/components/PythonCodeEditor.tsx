"use client";

import React, { useRef, useEffect } from "react";

interface PythonCodeEditorProps {
  value: string;
  onChange: (val: string) => void;
  height?: string;
  readOnly?: boolean;
}

// Tokenize Python code into syntax-colored spans (dark-only, see theme.ts)
function highlightPython(code: string): string {
  const escapeHtml = (str: string) =>
    str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");


  // Anthropic Color Tokens
  const commentColor = "#64748B";
  const stringColor = "#34D399";
  const kwColor = "#34D399"; // Anthropic Terracotta / Emerald Green
  const typeColor = "#38BDF8";
  const signalColor = "#6EE7B7";
  const funcColor = "#F8FAFC";
  const numColor = "#38BDF8";

  const lines = code.split("\n");
  const highlightedLines = lines.map((line) => {
    // 1. Full line docstrings or comments
    if (line.trim().startsWith("#") || line.trim().startsWith('"""') || line.trim().startsWith("'''")) {
      return `<span style="color: ${commentColor}; font-style: italic;">${escapeHtml(line)}</span>`;
    }

    let tokens = escapeHtml(line);

    // 2. Strings ("..." or '...')
    tokens = tokens.replace(
      /(&quot;.*?&quot;|'.*?'|"[^"]*")/g,
      `<span style="color: ${stringColor}; font-weight: 500;">$1</span>`
    );

    // 3. Keywords (Anthropic Emerald Green)
    const keywords = [
      "import", "from", "class", "def", "return", "if", "elif", "else",
      "self", "in", "and", "or", "not", "is", "None", "True", "False",
      "as", "pass", "raise", "try", "except", "finally", "with", "yield",
    ];
    const kwRegex = new RegExp(`\\b(${keywords.join("|")})\\b`, "g");
    tokens = tokens.replace(
      kwRegex,
      `<span style="color: ${kwColor}; font-weight: bold;">$1</span>`
    );

    // 4. Classes & Types
    const types = [
      "Strategy", "Signal", "MarketData", "RiskGate",
      "SmaCrossoverStrategy", "RsiMeanReversionStrategy",
      "MacdMomentumStrategy", "BollingerDipBuyer", "MultiFactorAlphaStrategy",
    ];
    const typeRegex = new RegExp(`\\b(${types.join("|")})\\b`, "g");
    tokens = tokens.replace(
      typeRegex,
      `<span style="color: ${typeColor}; font-weight: bold;">$1</span>`
    );

    // 5. Signals & Methods
    tokens = tokens.replace(
      /\b(BUY|SELL|HOLD|PASSING)\b/g,
      `<span style="color: ${signalColor}; font-weight: bold;">$1</span>`
    );

    // 6. Functions & Methods
    tokens = tokens.replace(
      /\b([a-zA-Z_][a-zA-Z0-9_]*)(?=\()/g,
      `<span style="color: ${funcColor}; font-weight: 600;">$1</span>`
    );

    // 7. Numbers
    tokens = tokens.replace(
      /\b(\d+\.?\d*)\b/g,
      `<span style="color: ${numColor};">$1</span>`
    );

    // 8. Inline comments (# ...)
    if (tokens.includes("#")) {
      const idx = tokens.indexOf("#");
      const codePart = tokens.slice(0, idx);
      const commentPart = tokens.slice(idx);
      tokens = `${codePart}<span style="color: ${commentColor}; font-style: italic;">${commentPart}</span>`;
    }

    return tokens;
  });

  return highlightedLines.join("\n");
}

export function PythonCodeEditor({
  value,
  onChange,
  height = "380px",
  readOnly = false,
}: PythonCodeEditorProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const preRef = useRef<HTMLPreElement>(null);
  const gutterRef = useRef<HTMLDivElement>(null);

  const lines = value.split("\n");
  const lineCount = lines.length;

  const handleScroll = () => {
    if (textareaRef.current) {
      const top = textareaRef.current.scrollTop;
      const left = textareaRef.current.scrollLeft;
      if (preRef.current) {
        preRef.current.scrollTop = top;
        preRef.current.scrollLeft = left;
      }
      if (gutterRef.current) {
        gutterRef.current.scrollTop = top;
      }
    }
  };

  useEffect(() => {
    handleScroll();
  }, [value]);


  return (
    <div
      className={`relative flex border font-mono text-xs transition-all rounded-b-xl shadow-2xl ${
        "bg-[var(--kt-surface)] border-emerald-500/20 text-[var(--kt-text)] backdrop-blur-xl"
      }`}
      style={{ height }}
    >
      {/* Line Numbers Gutter */}
      <div
        ref={gutterRef}
        className={`w-12 select-none overflow-hidden text-right pr-3 pt-3 font-mono text-xs leading-[1.625] border-r ${
          "bg-[#0D1322] text-[var(--kt-text-muted)] border-emerald-950/40"
        }`}
      >
        {Array.from({ length: lineCount }, (_, i) => (
          <div key={i + 1}>{i + 1}</div>
        ))}
      </div>

      {/* Editor Content Area */}
      <div className="relative flex-1 h-full overflow-hidden">
        {/* Tokenized Syntax Highlighting Layer */}
        <pre
          ref={preRef}
          className="absolute inset-0 pointer-events-none overflow-hidden p-3 font-mono text-xs leading-[1.625] whitespace-pre tab-4 m-0 font-medium"
          dangerouslySetInnerHTML={{ __html: highlightPython(value) }}
        />

        {/* Foreground Transparent Editable Textarea */}
        <textarea
          ref={textareaRef}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onScroll={handleScroll}
          readOnly={readOnly}
          spellCheck={false}
          autoCapitalize="off"
          autoComplete="off"
          autoCorrect="off"
          className="absolute inset-0 w-full h-full p-3 font-mono text-xs leading-[1.625] bg-transparent text-transparent caret-emerald-400 focus:outline-none resize-none whitespace-pre tab-4 selection:bg-emerald-500/30 overflow-auto"
          style={{
            WebkitTextFillColor: "transparent",
          }}
        />
      </div>
    </div>
  );
}
