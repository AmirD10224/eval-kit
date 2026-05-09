"use client";

import { GitPullRequest, AlertTriangle } from "lucide-react";

export function PrComment() {
  return (
    <div className="card overflow-hidden">
      <div className="flex items-center px-5 h-11 border-b border-[var(--color-line)]">
        <GitPullRequest className="size-3.5 text-[var(--color-fg-sub)] mr-2" />
        <span className="text-[12.5px] font-mono text-[var(--color-fg-sub)]">
          PR #82 · github checks
        </span>
        <span className="ml-auto inline-flex items-center gap-2 text-[11.5px]">
          <span className="inline-block h-1.5 w-1.5 rounded-full bg-[var(--color-danger)] pulse-soft" />
          <span className="text-[var(--color-danger)] font-mono uppercase tracking-[0.16em] text-[10.5px]">
            blocked
          </span>
        </span>
      </div>

      <div className="p-5 space-y-4">
        <div className="flex items-start gap-3">
          <span className="inline-flex h-8 w-8 items-center justify-center rounded-lg bg-[var(--color-danger-soft)] border border-[var(--color-danger)]/40 shrink-0">
            <AlertTriangle className="size-4 text-[var(--color-danger)]" strokeWidth={2.4} />
          </span>
          <div className="flex-1 min-w-0">
            <p className="text-[12.5px] font-mono text-[var(--color-fg-sub)]">
              <span className="text-[var(--color-fg)] font-medium">github-actions[bot]</span>
              {" "}commented now
            </p>
            <div className="mt-3 card-hi p-4 space-y-3">
              <p className="text-[14px] font-semibold text-[var(--color-danger)]">
                ✗ Eval gate · regression detected
              </p>
              <pre className="font-mono text-[12px] leading-[1.65] text-[var(--color-fg-dim)] overflow-x-auto whitespace-pre-wrap">
{`✓ answer_relevancy   0.812 → 0.835  (+2.3pp)
✓ closed_book        0.733 → 0.733  (+0.0pp)
✗ faithfulness       0.847 → 0.713  (-13.4pp)  ← exceeds 5pp threshold
✓ idk_when_no_ctx    0.967 → 0.967  (+0.0pp)
✓ context_precision  0.795 → 0.811  (+1.6pp)

faithfulness regressed by 13.4pp.
3 examples of regression below, full report in the artifact.`}
              </pre>
              <details className="text-[11.5px] font-mono">
                <summary className="cursor-pointer text-[var(--color-accent)] hover:text-[var(--color-accent-bright)] inline-block transition-colors">
                  ▸ Show 3 regression examples
                </summary>
                <div className="mt-2 space-y-1.5 text-[var(--color-fg-sub)] pl-3 border-l border-[var(--color-line-2)]">
                  <p>
                    Q: &quot;What does X return when Y is null?&quot;
                    <br />
                    Baseline: cited docs/api.md L42; Current: hallucinated &quot;returns empty list&quot;
                  </p>
                </div>
              </details>
              <p className="text-[10.5px] font-mono uppercase tracking-[0.14em] text-[var(--color-fg-sub)] pt-2 border-t border-[var(--color-line)]">
                eval-kit v0.1.0 · suite suites/main.yaml · 50 rows · κ=0.81
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2.5 card-hi px-3.5 py-3">
          <span className="inline-block h-2 w-2 rounded-full bg-[var(--color-danger)]" />
          <span className="text-[12.5px] font-medium text-[var(--color-fg)]">
            eval / required
          </span>
          <span className="ml-auto text-[11.5px] font-mono uppercase tracking-[0.14em] text-[var(--color-danger)]">
            FAILED · merge blocked
          </span>
        </div>
      </div>
    </div>
  );
}
