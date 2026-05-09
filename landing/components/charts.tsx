"use client";

import { useMemo } from "react";

/* Restrained sparkline, single-color, subtle fill, no glow */
export function Sparkline({
  data,
  color = "var(--color-fg)",
  height = 60,
}: {
  data: number[];
  color?: string;
  height?: number;
}) {
  const id = useMemo(() => `sl-${Math.random().toString(36).slice(2, 9)}`, []);
  if (data.length === 0) return null;
  const w = 240;
  const h = height;
  const padX = 2;
  const padY = 6;
  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  const step = (w - padX * 2) / (data.length - 1 || 1);
  const pts = data.map((v, i) => ({
    x: padX + i * step,
    y: padY + (h - padY * 2) * (1 - (v - min) / range),
  }));
  const d = pts.reduce((acc, p, i) => {
    if (i === 0) return `M ${p.x.toFixed(2)} ${p.y.toFixed(2)}`;
    const prev = pts[i - 1]!;
    const cp1x = prev.x + (p.x - prev.x) * 0.5;
    const cp2x = prev.x + (p.x - prev.x) * 0.5;
    return `${acc} C ${cp1x.toFixed(2)} ${prev.y.toFixed(2)}, ${cp2x.toFixed(2)} ${p.y.toFixed(2)}, ${p.x.toFixed(2)} ${p.y.toFixed(2)}`;
  }, "");
  const fillPath = `${d} L ${pts[pts.length - 1]!.x} ${h} L ${pts[0]!.x} ${h} Z`;
  const last = pts[pts.length - 1]!;
  return (
    <svg viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none" className="w-full block">
      <defs>
        <linearGradient id={`${id}-fill`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.16" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={fillPath} fill={`url(#${id}-fill)`} />
      <path
        d={d}
        fill="none"
        stroke={color}
        strokeWidth={1.4}
        strokeLinecap="round"
        vectorEffect="non-scaling-stroke"
      />
      <circle cx={last.x} cy={last.y} r={2.4} fill={color} />
    </svg>
  );
}

/* Calibration plot, minimal, no glow */
export function CalibrationPlot() {
  const w = 200;
  const h = 130;
  const padL = 24;
  const padB = 22;
  const padT = 6;
  const padR = 6;
  const bins = [
    { conf: 0.55, acc: 0.54 },
    { conf: 0.65, acc: 0.63 },
    { conf: 0.75, acc: 0.74 },
    { conf: 0.85, acc: 0.84 },
    { conf: 0.95, acc: 0.92 },
  ];
  const xS = (c: number) => padL + (c - 0.5) * 2 * (w - padL - padR);
  const yS = (a: number) => h - padB - a * (h - padT - padB);
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="w-full block">
      {[0.5, 0.6, 0.7, 0.8, 0.9, 1.0].map((g) => (
        <line
          key={g}
          x1={padL}
          y1={yS(g)}
          x2={w - padR}
          y2={yS(g)}
          stroke="var(--color-line-2)"
          strokeWidth="0.5"
        />
      ))}
      <line
        x1={xS(0.5)}
        y1={yS(0.5)}
        x2={xS(1)}
        y2={yS(1)}
        stroke="var(--color-line-hi)"
        strokeWidth="0.6"
        strokeDasharray="2 3"
      />
      {bins.map((b, i) => {
        const x = xS(b.conf);
        const y = yS(b.acc);
        const bw = (w - padL - padR) / bins.length / 2;
        return (
          <g key={i}>
            <rect
              x={x - bw / 2}
              y={y}
              width={bw}
              height={h - padB - y}
              fill="var(--color-accent)"
              opacity={0.18}
            />
            <rect
              x={x - bw / 2}
              y={y - 1.5}
              width={bw}
              height={1.5}
              fill="var(--color-accent)"
            />
          </g>
        );
      })}
      <text x={3} y={yS(0.5) + 3} fill="var(--color-fg-sub)" fontSize="8" fontFamily="var(--font-mono)">
        .50
      </text>
      <text x={3} y={yS(1) + 3} fill="var(--color-fg-sub)" fontSize="8" fontFamily="var(--font-mono)">
        1.0
      </text>
      <text x={padL} y={h - 4} fill="var(--color-fg-sub)" fontSize="8" fontFamily="var(--font-mono)">
        0.5
      </text>
      <text x={w - padR - 12} y={h - 4} fill="var(--color-fg-sub)" fontSize="8" fontFamily="var(--font-mono)">
        1.0
      </text>
    </svg>
  );
}

/* Histogram, solid bars, monochrome with single highlight */
export function TaxBars({
  bins,
  height = 80,
  labels,
  highlight,
}: {
  bins: number[];
  height?: number;
  labels?: string[];
  highlight?: number;
}) {
  const max = Math.max(...bins) || 1;
  return (
    <div className="space-y-2">
      <div className="flex items-end gap-[6px]" style={{ height }}>
        {bins.map((v, i) => {
          const pct = (v / max) * 100;
          const isHi = highlight === i;
          return (
            <div
              key={i}
              className="flex-1 relative rounded-t-sm"
              style={{
                height: `${pct}%`,
                background: isHi ? "var(--color-accent)" : "var(--color-line-hi)",
              }}
            />
          );
        })}
      </div>
      {labels && (
        <div className="flex gap-[6px] text-[9.5px] font-mono tabular text-[var(--color-fg-sub)] uppercase tracking-tight">
          {labels.map((l, i) => (
            <span key={i} className="flex-1 text-center">
              {l}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
