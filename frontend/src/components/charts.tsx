import { cls } from "./ui";

/** Health score over time (0-100). Gaps where a day has no data. */
export function ScoreLineChart({ points, height = 180 }: { points: { label: string; value: number | null }[]; height?: number }) {
  const W = 640, H = height, padL = 34, padR = 12, padT = 12, padB = 26;
  const iw = W - padL - padR, ih = H - padT - padB;
  const x = (i: number) => padL + (points.length <= 1 ? iw / 2 : (i / (points.length - 1)) * iw);
  const y = (v: number) => padT + ih - (v / 100) * ih;
  const segs: string[] = [];
  let cur = "";
  points.forEach((p, i) => {
    if (p.value == null) { if (cur) segs.push(cur); cur = ""; return; }
    cur += `${cur ? "L" : "M"}${x(i).toFixed(1)},${y(p.value).toFixed(1)}`;
  });
  if (cur) segs.push(cur);
  const valid = points.filter((p) => p.value != null);
  const last = valid[valid.length - 1];
  const desc = valid.length ? `Average health score from ${valid[0].value} to ${last.value} over ${points.length} days` : "No scan data yet";
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="h-auto w-full" role="img" aria-label={desc}>
      {[0, 50, 100].map((g) => (
        <g key={g}>
          <line x1={padL} x2={W - padR} y1={y(g)} y2={y(g)} className="stroke-line" strokeDasharray={g === 0 ? "" : "3 4"} />
          <text x={padL - 8} y={y(g) + 4} textAnchor="end" className="fill-muted text-[11px]">{g}</text>
        </g>
      ))}
      {segs.map((d, i) => <path key={i} d={d} fill="none" className="stroke-navy-700 [[data-theme=dark]_&]:stroke-[#7fb2ec]" strokeWidth="2.5" strokeLinejoin="round" strokeLinecap="round" />)}
      {points.map((p, i) => p.value != null && (
        <circle key={i} cx={x(i)} cy={y(p.value)} r={i === points.length - 1 ? 4.5 : 3}
          className={cls("fill-surface stroke-navy-700 [[data-theme=dark]_&]:stroke-[#7fb2ec]")} strokeWidth="2">
          <title>{`${p.label}: ${p.value}`}</title>
        </circle>
      ))}
      {points.map((p, i) => ((points.length - 1 - i) % 3 === 0 && (i > 0 || (points.length - 1) % 3 === 0)) && (
        <text key={`l${i}`} x={x(i)} y={H - 6} textAnchor={i === points.length - 1 ? "end" : i <= 1 ? "start" : "middle"} className="fill-muted text-[11px]">{p.label}</text>
      ))}
    </svg>
  );
}

export type Segment = { label: string; value: number; tone: "pass" | "warn" | "fail" | "muted" | "brand" };
const TONE_BG = { pass: "bg-pass", warn: "bg-warn", fail: "bg-fail", muted: "bg-muted/40", brand: "bg-navy-700" };

export function StackedBar({ segments, label }: { segments: Segment[]; label: string }) {
  const total = segments.reduce((a, s) => a + s.value, 0);
  return (
    <div>
      <div className="flex h-2.5 overflow-hidden rounded-full bg-subtle" role="img"
        aria-label={`${label}: ${segments.map((s) => `${s.value} ${s.label}`).join(", ")}`}>
        {total > 0 && segments.map((s) => s.value > 0 && (
          <span key={s.label} className={TONE_BG[s.tone]} style={{ width: `${(s.value / total) * 100}%` }} />
        ))}
      </div>
    </div>
  );
}

export function Legend({ segments }: { segments: Segment[] }) {
  return (
    <ul className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted">
      {segments.map((s) => (
        <li key={s.label} className="flex items-center gap-1.5">
          <span className={cls("h-2 w-2 rounded-full", TONE_BG[s.tone])} aria-hidden="true" />{s.label} <span className="font-semibold text-heading">{s.value}</span>
        </li>
      ))}
    </ul>
  );
}
