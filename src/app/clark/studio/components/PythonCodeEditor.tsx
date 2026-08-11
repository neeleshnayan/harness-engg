"use client";

import React, { useRef, useEffect } from "react";

interface PythonCodeEditorProps {
  value: string;
  onChange: (val: string) => void;
  height?: string;
  readOnly?: boolean;
}

// Tokenize Python code into syntax-colored spans using a restrained, smart dark palette
function highlightPython(code: string): string {
  const escapeHtml = (str: string) =>
    str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

  const lines = code.split("\n");
  const highlightedLines = lines.map((line) => {
    // 1. Full line docstrings or comments (Muted Slate)
    if (line.trim().startsWith("#") || line.trim().startsWith('"""') || line.trim().startsWith("'''")) {
      return `<span style="color: #64748B; font-style: italic;">${escapeHtml(line)}</span>`;
    }

    let tokens = escapeHtml(line);

    // 2. Strings (Soft Emerald)
    tokens = tokens.replace(
      /(&quot;.*?&quot;|'.*?'|"[^"]*")/g,
      `<span style="color: #34D399; font-weight: 500;">$1</span>`
    );

    // 3. Keywords (Crisp Teal)
    const keywords = [
      "import", "from", "class", "def", "return", "if", "elif", "else",
      "self", "in", "and", "or", "not", "is", "None", "True", "False",
      "as", "pass", "raise", "try", "except", "finally", "with", "yield",
    ];
    const kwRegex = new RegExp(`\\b(${keywords.join("|")})\\b`, "g");
    tokens = tokens.replace(
      kwRegex,
      `<span style="color: #2DD4BF; font-weight: bold;">$1</span>`
    );

    // 4. Classes & Types (Electric Sky Blue)
    const types = [
      "Strategy", "Signal", "MarketData", "RiskGate",
      "SmaCrossoverStrategy", "RsiMeanReversionStrategy",
      "MacdMomentumStrategy", "BollingerDipBuyer", "MultiFactorAlphaStrategy",
    ];
    const typeRegex = new RegExp(`\\b(${types.join("|")})\\b`, "g");
    tokens = tokens.replace(
      typeRegex,
      `<span style="color: #38BDF8; font-weight: bold;">$1</span>`
    );

    // 5. Signals & Methods (Emerald / Cyan)
    tokens = tokens.replace(
      /\b(BUY|SELL|HOLD|PASSING)\b/g,
      `<span style="color: #10B981; font-weight: bold;">$1</span>`
    );

    // 6. Functions & Methods (Ice Blue)
    tokens = tokens.replace(
      /\b([a-zA-Z_][a-zA-Z0-9_]*)(?=\()/g,
      `<span style="color: #7DD3FC; font-weight: 600;">$1</span>`
    );

    // 7. Numbers (Cool Steel)
    tokens = tokens.replace(
      /\b(\d+\.?\d*)\b/g,
      `<span style="color: #F8FAFC;">$1</span>`
    );

    // 8. Inline comments (# ...)
    if (tokens.includes("#")) {
      const idx = tokens.indexOf("#");
      const codePart = tokens.slice(0, idx);
      const commentPart = tokens.slice(idx);
      tokens = `${codePart}<span style="color: #64748B; font-style: italic;">${commentPart}</span>`;
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
      className="relative flex border border-teal-500/20 bg-[#040812]/90 backdrop-blur-xl text-zinc-100 transition-all rounded-b-xl shadow-2xl"
      style={{ height }}
    >
      {/* Line Numbers Gutter */}
      <div
        ref={gutterRef}
        className="w-12 select-none overflow-hidden text-right pr-3 pt-3 font-mono text-xs leading-[1.625] bg-[#070D1B]/80 text-zinc-600 border-r border-teal-900/30"
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
          className="absolute inset-0 w-full h-full p-3 font-mono text-xs leading-[1.625] bg-transparent text-transparent caret-teal-400 focus:outline-none resize-none whitespace-pre tab-4 selection:bg-teal-500/30 overflow-auto"
          style={{
            WebkitTextFillColor: "transparent",
          }}
        />
      </div>
    </div>
  );
}
