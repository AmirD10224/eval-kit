"use client";

import { useEffect, useState } from "react";
import { Check, Copy } from "lucide-react";

export function CodeBlock({
  code,
  language = "python",
  filename = "demo.py",
  highlightLines = [],
}: {
  code: string;
  language?: string;
  filename?: string;
  highlightLines?: number[];
}) {
  const [copied, setCopied] = useState(false);
  useEffect(() => {
    if (!copied) return;
    const id = setTimeout(() => setCopied(false), 1400);
    return () => clearTimeout(id);
  }, [copied]);

  return (
    <div className="card overflow-hidden">
      <div className="flex items-center px-4 h-10 border-b border-[var(--color-line)]">
        <span className="text-[12px] font-mono text-[var(--color-fg-sub)]">
          {filename}
        </span>
        <span className="ml-2 text-[10.5px] font-mono uppercase tracking-[0.14em] text-[var(--color-fg-faint)]">
          {language}
        </span>
        <button
          onClick={() => {
            navigator.clipboard.writeText(code);
            setCopied(true);
          }}
          className="ml-auto inline-flex items-center gap-1.5 text-[11.5px] text-[var(--color-fg-mute)] hover:text-[var(--color-fg)] transition-colors"
        >
          {copied ? (
            <>
              <Check className="size-3" /> Copied
            </>
          ) : (
            <>
              <Copy className="size-3" /> Copy
            </>
          )}
        </button>
      </div>
      <pre className="px-5 py-5 overflow-x-auto font-mono text-[13px] leading-[1.7]">
        {code.split("\n").map((line, i) => {
          const lineNum = i + 1;
          const isHi = highlightLines.includes(lineNum);
          return (
            <div
              key={i}
              className={
                isHi
                  ? "border-l-2 border-[var(--color-accent)] -mx-5 px-5 bg-[var(--color-accent-soft)]"
                  : ""
              }
            >
              <span className="inline-block w-7 text-right pr-3 text-[var(--color-fg-faint)] tabular select-none">
                {lineNum}
              </span>
              <span dangerouslySetInnerHTML={{ __html: highlight(line) }} />
            </div>
          );
        })}
      </pre>
    </div>
  );
}

function highlight(line: string): string {
  return line
    .replace(
      /(&quot;[^&]*&quot;|"[^"]*"|'[^']*')/g,
      '<span style="color: #84cc16">$1</span>',
    )
    .replace(
      /(#.*)$/g,
      '<span style="color: #6b7280; font-style: italic">$1</span>',
    )
    .replace(
      /\b(from|import|assert|def|class|return|if|else|elif|for|in|is|not|and|or|True|False|None|as|with|try|except|raise|yield|lambda|global|nonlocal|pass|break|continue)\b/g,
      '<span style="color: #fb923c">$1</span>',
    )
    .replace(
      /\b(\d+\.?\d*)\b/g,
      '<span style="color: #fbbf24">$1</span>',
    )
    .replace(
      /\.([a-z_][a-z0-9_]*)/gi,
      '.<span style="color: #93c5fd">$1</span>',
    );
}
