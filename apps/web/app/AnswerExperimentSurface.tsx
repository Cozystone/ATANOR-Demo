"use client";

/**
 * Experimental answer-interface surface.
 *
 * The engine attaches an `answer_visual` to math / geometry answers, and this
 * component renders the matching interface — a formula card, or a GeoGebra-like
 * labeled figure. The mapping (registry_hint → renderer) is intentionally
 * data-driven so ATANOR can later add its own kinds: a new `kind` here + a new
 * `answer_visual` from the engine is all it takes to teach the agent a new way
 * to answer a class of question.
 */

export type AnswerVisual = {
  kind: "formula" | "geometry_figure" | string;
  title?: string;
  formula?: string;
  registry_hint?: string;
  // geometry_figure only:
  shape?: "square" | "rectangle" | "circle" | "triangle" | string;
  params?: Record<string, number>;
  metric?: "perimeter" | "area" | string;
  result?: number;
};

const ACCENT = "#7db4ff";
const INK = "#dbe6ff";
const DIM = "#8aa0c8";
const FILL = "rgba(125, 180, 255, 0.12)";

function fmt(n: number | undefined): string {
  if (n === undefined || Number.isNaN(n)) return "";
  return Math.abs(n - Math.round(n)) < 1e-9 ? String(Math.round(n)) : String(Math.round(n * 100) / 100);
}

function GeometryFigure({ v }: { v: AnswerVisual }) {
  const p = v.params ?? {};
  const W = 260;
  const H = 180;
  let svg: React.ReactNode = null;

  if (v.shape === "square" || v.shape === "rectangle") {
    const w = p.side ?? p.width ?? 1;
    const h = p.side ?? p.height ?? w;
    const scale = Math.min(150 / Math.max(w, h), 60);
    const bw = Math.max(40, w * scale);
    const bh = Math.max(30, h * scale);
    const x = (W - bw) / 2;
    const y = (H - bh) / 2;
    svg = (
      <>
        <rect x={x} y={y} width={bw} height={bh} fill={FILL} stroke={ACCENT} strokeWidth={2} rx={3} />
        <text x={x + bw / 2} y={y - 8} fill={INK} fontSize={13} textAnchor="middle">{fmt(w)}</text>
        <text x={x - 10} y={y + bh / 2} fill={INK} fontSize={13} textAnchor="end" dominantBaseline="middle">{fmt(h)}</text>
      </>
    );
  } else if (v.shape === "circle") {
    const r = p.radius ?? 1;
    const rr = Math.min(70, Math.max(34, r * 12));
    const cx = W / 2;
    const cy = H / 2;
    svg = (
      <>
        <circle cx={cx} cy={cy} r={rr} fill={FILL} stroke={ACCENT} strokeWidth={2} />
        <line x1={cx} y1={cy} x2={cx + rr} y2={cy} stroke={ACCENT} strokeWidth={1.5} strokeDasharray="3 3" />
        <circle cx={cx} cy={cy} r={2.5} fill={ACCENT} />
        <text x={cx + rr / 2} y={cy - 6} fill={INK} fontSize={12} textAnchor="middle">r = {fmt(r)}</text>
      </>
    );
  } else if (v.shape === "triangle") {
    const b = p.base ?? 1;
    const h = p.height ?? 1;
    const scale = Math.min(150 / Math.max(b, h), 50);
    const bw = Math.max(50, b * scale);
    const bh = Math.max(40, h * scale);
    const x0 = (W - bw) / 2;
    const yb = (H + bh) / 2;
    const apex = x0 + bw / 2;
    svg = (
      <>
        <polygon points={`${x0},${yb} ${x0 + bw},${yb} ${apex},${yb - bh}`} fill={FILL} stroke={ACCENT} strokeWidth={2} />
        <line x1={apex} y1={yb} x2={apex} y2={yb - bh} stroke={ACCENT} strokeWidth={1} strokeDasharray="3 3" />
        <text x={x0 + bw / 2} y={yb + 16} fill={INK} fontSize={12} textAnchor="middle">밑변 {fmt(b)}</text>
        <text x={apex + 8} y={yb - bh / 2} fill={DIM} fontSize={12}>높이 {fmt(h)}</text>
      </>
    );
  }

  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" style={{ maxWidth: 300, display: "block", margin: "0 auto" }}>
      {svg}
    </svg>
  );
}

export default function AnswerExperimentSurface({ visual }: { visual: AnswerVisual }) {
  const isGeo = visual.kind === "geometry_figure";
  return (
    <div className="atanor-answer-experiment" data-kind={visual.kind}>
      <div className="atanor-answer-experiment-head">
        <span className="atanor-answer-experiment-dot" />
        <span>{visual.title || (isGeo ? "도형" : "수식")}</span>
        {visual.registry_hint ? <code className="atanor-answer-experiment-hint">{visual.registry_hint}</code> : null}
      </div>
      {isGeo ? <GeometryFigure v={visual} /> : null}
      {visual.formula ? <div className="atanor-answer-experiment-formula">{visual.formula}</div> : null}
    </div>
  );
}
