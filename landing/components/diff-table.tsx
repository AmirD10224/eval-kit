"use client";

import { Check, X } from "lucide-react";

type Row = { metric: string; before: number; after: number };

const ROWS: Row[] = [
  { metric: "answer_relevancy",  before: 0.812, after: 0.835 },
  { metric: "closed_book",       before: 0.733, after: 0.733 },
  { metric: "faithfulness",      before: 0.847, after: 0.713 },
  { metric: "idk_when_no_ctx",   before: 0.967, after: 0.967 },
  { metric: "context_precision", before: 0.795, after: 0.811 },
];

export function DiffTable() {
  return (
    <div className="card overflow-hidden">
      <div className="flex items-center px-5 h-11 border-b border-[var(--color-line)]">
        <span className="text-[12.5px] font-mono text-[var(--color-fg-sub)]">
          $ evalkit diff
        </span>
        <span className="ml-auto inline-flex items-center gap-2 text-[11.5px]">
          <span className="inline-block h-1.5 w-1.5 rounded-full bg-[var(--color-danger)] pulse-soft" />
          <span className="text-[var(--color-danger)] font-mono uppercase tracking-[0.16em] text-[10.5px]">
            regression
          </span>
        </span>
      </div>

      <div>
        <div className="grid grid-cols-[1fr_72px_72px_72px_64px_24px] gap-2 px-5 py-2.5 text-[10.5px] uppercase tracking-[0.16em] text-[var(--color-fg-sub)] border-b border-[var(--color-line)] font-mono">
          <span>Metric</span>
          <span className="text-right">Baseline</span>
          <span className="text-right">Current</span>
          <span className="text-right">Δ</span>
          <span className="text-right">PP</span>
          <span></span>
        </div>
        {ROWS.map((r, i) => {
          const delta = r.after - r.before;
          const pp = (delta * 100).toFixed(1);
          const regressed = delta < -0.05;
          const isLast = i === ROWS.length - 1;
          const tone = regressed
            ? "var(--color-danger)"
            : delta > 0.005
              ? "var(--color-success)"
              : "var(--color-fg-sub)";
          return (
            <div
              key={i}
              className={`grid grid-cols-[1fr_72px_72px_72px_64px_24px] gap-2 items-center px-5 py-3 text-[12.5px] font-mono ${!isLast ? "border-b border-[var(--color-line)]" : ""} ${regressed ? "bg-[var(--color-danger-soft)]" : ""}`}
            >
              <span className="text-[var(--color-fg)]">{r.metric}</span>
              <span className="text-right tabular text-[var(--color-fg-sub)]">
                {r.before.toFixed(3)}
              </span>
              <span className="text-right tabular text-[var(--color-fg)]">
                {r.after.toFixed(3)}
              </span>
              <span className="text-right tabular" style={{ color: tone }}>
                {delta > 0 ? "+" : ""}
                {delta.toFixed(3)}
              </span>
              <span className="text-right tabular" style={{ color: tone }}>
                {delta > 0 ? "+" : ""}
                {pp}pp
              </span>
              <span className="flex justify-end">
                {regressed ? (
                  <X className="size-3.5 text-[var(--color-danger)]" strokeWidth={2.5} />
                ) : (
                  <Check className="size-3.5 text-[var(--color-success)]" strokeWidth={2.5} />
                )}
              </span>
            </div>
          );
        })}
      </div>

      <div className="px-5 py-3 border-t border-[var(--color-line)] flex items-center justify-between flex-wrap gap-3 text-[12px] font-mono">
        <span className="text-[var(--color-danger)]">
          ✗ regression detected · faithfulness · -13.4pp · threshold 5pp
        </span>
        <span className="text-[var(--color-fg-sub)] tabular">
          process exit 1 · CI failed
        </span>
      </div>
    </div>
  );
}
