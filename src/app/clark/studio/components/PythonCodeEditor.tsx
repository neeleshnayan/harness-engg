"use client";

import React, { useRef, useEffect } from "react";

interface PythonCodeEditorProps {
  value: string;
  onChange: (val: string) => void;
  height?: string;
  readOnly?: boolean;
}

// Tokenize Python code into syntax-colored spans
function highlightPython(code: string): string {
  const escapeHtml = (str: string) =>
    str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

  const lines = code.split("\n");
  const highlightedLines = lines.map((line) => {
    // 1. Full line docstrings or comments
    if (line.trim().startsWith("#")) {
      return `<span style="color: #637777; font-style: italic;">${escapeHtml(line)}</span>`;
    }
    if (line.trim().startsWith('"""') || line.trim().startsWith("'''")) {
      return `<span style="color: #637777; font-style: italic;">${escapeHtml(line)}</span>`;
    }

    let tokens = escapeHtml(line);

    // 2. Strings ("..." or '...')
    tokens = tokens.replace(
      /(&quot;.*?&quot;|'.*?'|"[^"]*")/g,
      '<span style="color: #C3E88D;">$1</span>'
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
      '<span style="color: #C792EA; font-weight: bold;">$1</span>'
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
      '<span style="color: #4EC9B0; font-weight: bold;">$1</span>'
    );

    // 5. Signals & Methods
    tokens = tokens.replace(
      /\b(BUY|SELL|HOLD|PASSING)\b/g,
      '<span style="color: #34D399; font-weight: bold;">$1</span>'
    );

    // 6. Functions & Methods
    tokens = tokens.replace(
      /\b([a-zA-Z_][a-zA-Z0-9_]*)(?=\()/g,
      '<span style="color: #82AAFF;">$1</span>'
    );

    // 7. Numbers
    tokens = tokens.replace(
      /\b(\d+\.?\d*)\b/g,
      '<span style="color: #F78C6C;">$1</span>'
    );

    // 8. Inline comments (# ...)
    if (tokens.includes("#")) {
      const idx = tokens.indexOf("#");
      const codePart = tokens.slice(0, idx);
      const commentPart = tokens.slice(idx);
      tokens = `${codePart}<span style="color: #637777; font-style: italic;">${commentPart}</span>`;
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

  const lineCount = value.split("\n").length;
  const lineNumbers = Array.from({ length: Math.max(lineCount, 25) }, (_, i) => i + 1);

  // Synchronize scrolling between textarea, pre syntax layer, and line number gutter
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
    <div className="relative flex bg-[#03060E] border border-teal-900/50 rounded-xl overflow-hidden font-mono text-xs shadow-2xl">
      {/* Line Number Gutter */}
      <div
        ref={gutterRef}
        className="w-11 bg-[#060B18] py-4 select-none font-mono text-[11px] text-zinc-600 text-right pr-2 space-y-0.5 border-r border-teal-900/30 overflow-hidden shrink-0"
        style={{ height }}
      >
        {lineNumbers.map((n) => (
          <div key={n} className="leading-relaxed">
            {n}
          </div>
        ))}
      </div>

      {/* Editor Container with Syntax Overlay */}
      <div className="relative flex-1 overflow-hidden" style={{ height }}>
        {/* Background Syntax Highlighted Code Overlay */}
        <pre
          ref={preRef}
          aria-hidden="true"
          className="absolute inset-0 p-4 margin-0 pointer-events-none font-mono text-xs leading-relaxed overflow-auto whitespace-pre tab-4"
          style={{
            fontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
            lineHeight: "1.625",
          }}
          dangerouslySetInnerHTML={{ __html: highlightPython(value) + "\n" }}
        />

        {/* Foreground Transparent Interactive Textarea */}
        <textarea
          ref={textareaRef}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onScroll={handleScroll}
          readOnly={readOnly}
          spellCheck={false}
          className="absolute inset-0 p-4 margin-0 w-full h-full bg-transparent text-transparent caret-teal-400 font-mono text-xs leading-relaxed outline-none resize-none selection:bg-teal-500/30 whitespace-pre overflow-auto tab-4"
          style={{
            fontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
            lineHeight: "1.625",
          }}
        />
      </div>
    </div>
  );
}
