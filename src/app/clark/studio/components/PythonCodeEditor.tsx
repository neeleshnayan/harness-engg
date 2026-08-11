"use client";

import React, { useRef, useEffect } from "react";

interface PythonCodeEditorProps {
  value: string;
  onChange: (val: string) => void;
  height?: string;
  readOnly?: boolean;
  theme?: "dark" | "light";
}

// Tokenize Python code into syntax-colored spans
function highlightPython(code: string, theme: "dark" | "light" = "dark"): string {
  const escapeHtml = (str: string) =>
    str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

  const isLight = theme === "light";
  const commentColor = isLight ? "#78716C" : "#637777";
  const stringColor = isLight ? "#2B6CB0" : "#C3E88D";
  const kwColor = isLight ? "#9B2C2C" : "#C792EA";
  const typeColor = isLight ? "#276749" : "#4EC9B0";
  const signalColor = isLight ? "#D97757" : "#34D399";
  const funcColor = isLight ? "#D97757" : "#82AAFF";
  const numColor = isLight ? "#C05621" : "#F78C6C";

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

    // 3. Keywords
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
  theme = "dark",
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

  const isLight = theme === "light";

  return (
    <div
      className={`relative flex border transition-colors ${
        isLight
          ? "bg-[#FAF7F2] border-[#EAE5D9] text-[#2D2B2A]"
          : "bg-[#040813] border-teal-900/50 text-zinc-100"
      }`}
      style={{ height }}
    >
      {/* Line Numbers Gutter */}
      <div
        ref={gutterRef}
        className={`w-12 select-none overflow-hidden text-right pr-3 pt-3 font-mono text-xs leading-[1.625] border-r ${
          isLight
            ? "bg-[#F3EFE6] text-[#A8A29E] border-[#EAE5D9]"
            : "bg-[#070D1B] text-zinc-600 border-teal-900/40"
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
          dangerouslySetInnerHTML={{ __html: highlightPython(value, theme) }}
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
          className="absolute inset-0 w-full h-full p-3 font-mono text-xs leading-[1.625] bg-transparent text-transparent caret-emerald-500 focus:outline-none resize-none whitespace-pre tab-4 selection:bg-teal-500/30 overflow-auto"
          style={{
            WebkitTextFillColor: "transparent",
          }}
        />
      </div>
    </div>
  );
}
