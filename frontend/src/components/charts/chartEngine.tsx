import { useMemo, useState } from 'react';
import type { ChartData } from '@/lib/types';
import { formatCompact, formatNumber, cellToString } from '@/lib/format';

export const PALETTE = [
  '#0A84FF', '#5E5CE6', '#BF5AF2', '#FF2D92', '#FF9500',
  '#30D158', '#64D2FF', '#FFCC00', '#FF3B30', '#32ADE6',
];

export const PALETTE_HEX = PALETTE;

type Pt = { x: number; y: number; v: number; label?: string };

export function niceTicks(min: number, max: number, count = 5): number[] {
  if (max === min) return [min];
  const span = max - min;
  const step0 = span / count;
  const mag = Math.pow(10, Math.floor(Math.log10(step0)));
  const norm = step0 / mag;
  const step = (norm >= 5 ? 5 : norm >= 2 ? 2 : norm >= 1 ? 1 : 0.5) * mag;
  const out: number[] = [];
  for (let v = Math.floor(min / step) * step; v <= max + step * 0.5; v += step) {
    out.push(Number(v.toFixed(8)));
  }
  if (out.length > 12) {
    return niceTicks(min, max, 3);
  }
  return out;
}

function axisTick(v: number, step: number): string {
  if (step >= 1) return formatCompact(v);
  return String(Number(v.toFixed(2)));
}

interface CartesianProps {
  labels: string[];
  values: number[][]; // series
  seriesNames: string[];
  stacked?: boolean;
  hundred?: boolean;
  grouped?: boolean;
  type: 'bar' | 'line' | 'area' | 'column';
  height?: number;
}

function CartesianChart({ labels, values, seriesNames, stacked, hundred, grouped, type, height = 300 }: CartesianProps) {
  const W = 640;
  const H = height;
  const padL = 38;
  const padR = 12;
  const padT = 10;
  const padB = 34;
  const iw = W - padL - padR;
  const ih = H - padT - padB;

  const flat = values.flat().filter((v) => typeof v === 'number' && Number.isFinite(v));
  const rawMin = Math.min(0, ...(flat.length ? flat : [0]));
  const rawMax = Math.max(0, ...(flat.length ? flat : [1]));
  const ticks = niceTicks(rawMin, rawMax * 1.04, 4);
  const yMin = ticks[0];
  const yMax = ticks[ticks.length - 1];

  const n = labels.length;
  const band = iw / Math.max(n, 1);

  const y = (v: number) => padT + ih - ((v - yMin) / (yMax - yMin || 1)) * ih;
  const x = (i: number) => padL + (n > 1 ? (i * iw) / (n - 1) : iw / 2);

  const labelIdxStep = n > 14 ? Math.ceil(n / 14) : 1;

  const seriesPaths = useMemo(() => {
    return values.map((ser) => {
      const pts: Pt[] = ser.map((v, i) => ({ x: x(i), y: y(Number(v) || 0), v: Number(v) || 0 }));
      return pts;
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [values, labels, yMin, yMax]);

  const tipFor = (si: number, vi: number, value: number) =>
    `${seriesNames[si] ? seriesNames[si] + ' · ' : ''}${labels[vi] ?? ''}\n${formatNumber(value)}`;

  return (
    <div className="relative select-none" style={{ height: H }}>
      <svg viewBox={`0 0 ${W} ${H}`} className="h-full w-full overflow-visible">
        <defs>
          <linearGradient id="chartLineGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={PALETTE[0]} stopOpacity="0.28" />
            <stop offset="100%" stopColor={PALETTE[0]} stopOpacity="0.02" />
          </linearGradient>
        </defs>
        {ticks.map((t) => (
          <g key={t}>
            <line x1={padL} x2={W - padR} y1={y(t)} y2={y(t)} stroke="currentColor" strokeOpacity="0.08" strokeWidth="1" />
            <text x={padL - 6} y={y(t) + 3} textAnchor="end" className="fill-muted-foreground" fontSize="9">
              {axisTick(t, ticks[1] - ticks[0] || 1)}
            </text>
          </g>
        ))}
        {labels.map((l, i) =>
          i % labelIdxStep === 0 ? (
            <text key={l} x={x(i)} y={H - padB + 14} textAnchor="middle" className="fill-muted-foreground" fontSize="9">
              {cellToString(l).length > 12 ? cellToString(l).slice(0, 11) + '…' : cellToString(l)}
            </text>
          ) : null,
        )}
        {labels.length > 30 && (
          <text x={W - padR} y={H - 2} textAnchor="end" className="fill-muted-foreground" fontSize="8">
            {labels.length} values
          </text>
        )}

        {(type === 'line' || type === 'area') && (
          <g>
            {type === 'area' && seriesPaths[0] && seriesPaths[0].length > 1 && (
              <path
                d={`M ${seriesPaths[0][0].x} ${y(0)} L ${seriesPaths[0].map((p) => `${p.x} ${p.y}`).join(' L ')} L ${seriesPaths[0][seriesPaths[0].length - 1].x} ${y(0)} Z`}
                fill="url(#chartLineGrad)"
              />
            )}
            {seriesPaths.map((pts, si) => {
              if (pts.length < 2) return null;
              const d = pts.map((p, i) => (i === 0 ? `M ${p.x} ${p.y}` : ` L ${p.x} ${p.y}`)).join(' ');
              return (
                <path
                  key={si}
                  d={d}
                  fill="none"
                  stroke={PALETTE[si % PALETTE.length]}
                  strokeWidth="2"
                  strokeLinejoin="round"
                  strokeLinecap="round"
                />
              );
            })}
          </g>
        )}

        {(type === 'bar' || type === 'column') && (
          <g>
            {stacked
              ? labels.map((l, i) => {
                  let acc = 0;
                  return values.map((ser, si) => {
                    const raw = Number(ser[i]) || 0;
                    const v = raw;
                    const isHundred = hundred;
                    const yy = isHundred ? padT + ih - (raw / 100) * ih : y(acc + v);
                    acc += v;
                    const bw = band * 0.7;
                    return (
                      <rect
                        key={`${l}-${si}`}
                        x={padL + i * band + bw / 4}
                        y={Math.min(yy, y(acc))}
                        width={bw}
                        height={Math.abs(y(acc) - yy)}
                        rx="2.5"
                        fill={PALETTE[si % PALETTE.length]}
                        opacity="0.9"
                      >
                        <title>{tipFor(si, i, v)}</title>
                      </rect>
                    );
                  });
                })
              : labels.map((l, i) => {
                  const gw = grouped ? 0.72 : 0.6;
                  const groupW = band * gw;
                  const per = values.length;
                  const sw = groupW / per;
                  return values.map((ser, si) => {
                    const v = Number(ser[i]) || 0;
                    const bh = Math.abs((v / (yMax - yMin || 1)) * ih);
                    const yTop = y(v);
                    const bx = padL + i * band + band * ((1 - gw) / 2) + si * sw + 1;
                    return (
                      <rect
                        key={`${l}-${si}`}
                        x={bx}
                        y={yTop}
                        width={Math.max(2, sw - 2)}
                        height={Math.max(1, bh)}
                        rx="2"
                        fill={PALETTE[si % PALETTE.length]}
                        opacity={grouped ? 0.92 : 0.9}
                      >
                        <title>{tipFor(si, i, v)}</title>
                      </rect>
                    );
                  });
                })}
          </g>
        )}

        {(type === 'line' || type === 'area') &&
          seriesPaths.map((pts, si) =>
            pts.map((p, vi) => (
              <circle
                key={`${si}-${vi}`}
                cx={p.x}
                cy={p.y}
                r={3.2}
                fill={PALETTE[si % PALETTE.length]}
                stroke="var(--card)"
                strokeWidth="1.5"
              >
                <title>{tipFor(si, vi, p.v)}</title>
              </circle>
            )),
          )}
      </svg>
    </div>
  );
}

function PieDoughnut({ labels, values, doughnut, height = 280 }: { labels: string[]; values: number[]; doughnut: boolean; height?: number }) {
  const W = 460;
  const H = height;
  const cx = W / 2;
  const cy = H / 2;
  const r = Math.min(W, H) / 2 - 20;
  const total = values.reduce((a, b) => a + b, 0) || 1;
  const rOuter = r;
  const rInner = doughnut ? r * 0.58 : 0;

  let acc = -Math.PI / 2;
  const arcs = values.map((v, i) => {
    const a0 = acc;
    const a1 = acc + (v / total) * Math.PI * 2;
    acc = a1;
    const large = a1 - a0 > Math.PI ? 1 : 0;
    const label = labels[i] ?? '';
    const mid = (a0 + a1) / 2;
    const lx = cx + Math.cos(mid) * r * 0.62;
    const ly = cy + Math.sin(mid) * r * 0.62;
    const pct = (v / total) * 100;
    return { a0, a1, large, label, mid, lx, ly, pct, color: PALETTE[i % PALETTE.length], value: v };
  });

  return (
    <div className="relative select-none" style={{ height: H }}>
      <svg viewBox={`0 0 ${W} ${H}`} className="h-full w-full">
        {arcs.map((a, i) => {
          const x0 = cx + rOuter * Math.cos(a.a0);
          const y0 = cy + rOuter * Math.sin(a.a0);
          const x1 = cx + rOuter * Math.cos(a.a1);
          const y1 = cy + rOuter * Math.sin(a.a1);
          if (rInner === 0) {
            return (
              <path key={i} d={`M ${cx} ${cy} L ${x0} ${y0} A ${rOuter} ${rOuter} 0 ${a.large} 1 ${x1} ${y1} Z`} fill={a.color}>
                <title>{`${a.label}\n${formatNumber(a.value)} (${a.pct.toFixed(1)}%)`}</title>
              </path>
            );
          }
          const ix0 = cx + rInner * Math.cos(a.a0);
          const iy0 = cy + rInner * Math.sin(a.a0);
          const ix1 = cx + rInner * Math.cos(a.a1);
          const iy1 = cy + rInner * Math.sin(a.a1);
          return (
            <path
              key={i}
              d={`M ${x0} ${y0} A ${rOuter} ${rOuter} 0 ${a.large} 1 ${x1} ${y1} L ${ix1} ${iy1} A ${rInner} ${rInner} 0 ${a.large} 0 ${ix0} ${iy0} Z`}
              fill={a.color}
              stroke="var(--card)"
              strokeWidth="1.5"
            >
              <title>{`${a.label}\n${formatNumber(a.value)} (${a.pct.toFixed(1)}%)`}</title>
            </path>
          );
        })}
        {labels.length <= 8 &&
          arcs
            .filter((a) => a.pct > 3)
            .map((a, i) => (
              <text key={i} x={a.lx} y={a.ly} textAnchor="middle" className={doughnut ? 'fill-card' : 'fill-white'} fontSize="10" fontWeight="600">
                {a.pct.toFixed(0)}%
              </text>
            ))}
      </svg>
      {doughnut && (
        <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
          <div className="text-xl font-semibold tabular-nums">{formatCompact(total)}</div>
          <div className="text-[10px] uppercase tracking-wide text-muted-foreground">Total</div>
        </div>
      )}
    </div>
  );
}

function ScatterBubble({ data, height = 300 }: { data: ChartData; height?: number }) {
  const W = 640;
  const H = height;
  const padL = 42;
  const padR = 14;
  const padT = 12;
  const padB = 34;
  const iw = W - padL - padR;
  const ih = H - padT - padB;
  const points = (data.points ?? []).filter((p) => Number.isFinite(p.x) && Number.isFinite(p.y));
  const sizes = (data.points ?? []).map((p) => p.size ?? 10);

  const xs = points.map((p) => p.x);
  const ys = points.map((p) => p.y);
  let xMin = Math.min(...xs, 0);
  let xMax = Math.max(...xs, 1);
  let yMin = Math.min(...ys, 0);
  let yMax = Math.max(...ys, 1);
  const sMin = Math.min(...sizes, 1);
  const sMax = Math.max(...sizes, sMin + 1);
  if (xMin === xMax) xMax = xMin + 1;
  if (yMin === yMax) yMax = yMin + 1;

  const scaleX = (v: number) => padL + ((v - xMin) / (xMax - xMin)) * iw;
  const scaleY = (v: number) => padT + ih - ((v - yMin) / (yMax - yMin)) * ih;
  const scaleR = (s: number) => 2 + ((s - sMin) / (sMax - sMin)) * 16;

  const xTicks = niceTicks(xMin, xMax, 5);
  const yTicks = niceTicks(yMin, yMax, 4);

  const colorMap = new Map<string, string>();
  let ci = 0;
  for (const p of points) {
    const key = typeof p.color === 'number' ? `num:${p.color}` : String(p.color ?? '');
    if (!colorMap.has(key)) colorMap.set(key, PALETTE[ci++ % PALETTE.length]);
  }

  const [hover, setHover] = useState<number | null>(null);

  return (
    <div className="relative select-none" style={{ height: H }}>
      <svg viewBox={`0 0 ${W} ${H}`} className="h-full w-full">
        <defs>
          <radialGradient id="scatterGlow">
            <stop offset="0%" stopColor="white" stopOpacity="0.35" />
            <stop offset="100%" stopColor="white" stopOpacity="0" />
          </radialGradient>
        </defs>
        {xTicks.map((t) => (
          <g key={t}>
            <line x1={scaleX(t)} x2={scaleX(t)} y1={padT} y2={H - padB} stroke="currentColor" strokeOpacity="0.06" strokeWidth="1" />
            <text x={scaleX(t)} y={H - padB + 14} textAnchor="middle" className="fill-muted-foreground" fontSize="9">
              {axisTick(t, xTicks[1] - xTicks[0] || 1)}
            </text>
          </g>
        ))}
        {yTicks.map((t) => (
          <g key={t}>
            <line x1={padL} x2={W - padR} y1={scaleY(t)} y2={scaleY(t)} stroke="currentColor" strokeOpacity="0.06" strokeWidth="1" />
            <text x={padL - 6} y={scaleY(t) + 3} textAnchor="end" className="fill-muted-foreground" fontSize="9">
              {axisTick(t, yTicks[1] - yTicks[0] || 1)}
            </text>
          </g>
        ))}
        {points.map((p, i) => {
          const key = typeof p.color === 'number' ? `num:${p.color}` : String(p.color ?? '');
          const color = typeof p.color === 'number' ? PALETTE[Math.min(p.color, PALETTE.length - 1) % PALETTE.length] : colorMap.get(key) ?? PALETTE[0];
          const r = scaleR(p.size ?? 10);
          return (
            <g key={i} opacity={hover === null || hover === i ? 1 : 0.25}>
              <circle cx={scaleX(p.x)} cy={scaleY(p.y)} r={r + 3} fill={color} opacity="0.12" />
              <circle cx={scaleX(p.x)} cy={scaleY(p.y)} r={r} fill={color} opacity="0.85">
                <title>{cellToString(p.label ?? '')}</title>
              </circle>
              <circle
                cx={scaleX(p.x)}
                cy={scaleY(p.y)}
                r={r + 6}
                fill="transparent"
                onMouseEnter={() => setHover(i)}
                onMouseLeave={() => setHover(null)}
              />
            </g>
          );
        })}
      </svg>
    </div>
  );
}

function HeatmapChart({ data, height = 300 }: { data: ChartData; height?: number }) {
  const xLabels = (data.x_labels as string[]) ?? [];
  const yLabels = (data.y_labels as string[]) ?? [];
  const matrix = (data.matrix as { x: string; y: string; value: number | null }[]) ?? [];
  const cells = matrix.filter((c) => c.value !== null).map((c) => c.value as number);
  const min = cells.length ? Math.min(...cells) : 0;
  const max = cells.length ? Math.max(...cells) : 1;

  const cellW = 26;
  const cellH = 22;
  const padL = 64;
  const padT = 16;

  const interp = (v: number) => {
    const t = max === min ? 0.5 : (v - min) / (max - min);
    const r = Math.round(234 - 190 * t);
    const g = Math.round(70 + 24 * t);
    const b = Math.round(254 - 60 * t);
    return `rgba(${r},${g},${b},${0.35 + 0.6 * (1 - t)})`;
  };

  const [hover, setHover] = useState<number | null>(null);

  return (
    <div className="relative select-none overflow-auto scrollbar-thin" style={{ height }}>
      <svg
        viewBox={`0 0 ${padL + xLabels.length * cellW + 10} ${padT + yLabels.length * cellH + 24}`}
        className="h-full w-full"
      >
        {yLabels.map((y, yi) => (
          <text key={y} x={padL - 6} y={padT + yi * cellH + cellH / 2 + 3} textAnchor="end" className="fill-muted-foreground" fontSize="9">
            {cellToString(y)}
          </text>
        ))}
        {xLabels.map((x, xi) => (
          <text key={x} x={padL + xi * cellW + cellW / 2} y={padT - 6} textAnchor="middle" className="fill-muted-foreground" fontSize="9">
            {cellToString(x)}
          </text>
        ))}
        {matrix.map((c, i) => {
          const xi = xLabels.indexOf(c.x);
          const yi = yLabels.indexOf(c.y);
          if (xi < 0 || yi < 0) return null;
          return (
            <rect
              key={i}
              x={padL + xi * cellW}
              y={padT + yi * cellH}
              width={cellW - 2}
              height={cellH - 2}
              rx="3"
              fill={c.value === null ? 'transparent' : interp(c.value)}
              stroke={hover === i ? 'var(--foreground)' : 'var(--card)'}
              strokeWidth={hover === i ? 1.4 : 1}
              onMouseEnter={() => setHover(i)}
              onMouseLeave={() => setHover(null)}
            >
              <title>
                {c.x} × {c.y} · {formatNumber(c.value)}
              </title>
            </rect>
          );
        })}
        <g transform={`translate(${padL}, ${padT + yLabels.length * cellH + 8})`}>
          {[0, 0.25, 0.5, 0.75, 1].map((t) => (
            <rect key={t} x={t * 100} y={0} width={25} height={8} rx="2" fill={interp(min + (max - min) * t)} />
          ))}
        </g>
      </svg>
    </div>
  );
}

function RadarChart({ data, height = 300 }: { data: ChartData; height?: number }) {
  const cats = (data.categories ?? data.labels ?? []) as string[];
  const values = (data.values ?? []) as number[];
  const W = 480;
  const H = height;
  const cx = W / 2;
  const cy = H / 2 - 6;
  const r = Math.min(W, H) / 2 - 46;
  const max = Math.max(...values, 1);

  const angle = (i: number) => -Math.PI / 2 + (i * 2 * Math.PI) / Math.max(cats.length, 1);
  const px = (i: number, v: number) => cx + Math.cos(angle(i)) * r * (v / max);
  const py = (i: number, v: number) => cy + Math.sin(angle(i)) * r * (v / max);

  return (
    <div className="relative select-none" style={{ height: H }}>
      <svg viewBox={`0 0 ${W} ${H}`} className="h-full w-full">
        {[0.25, 0.5, 0.75, 1].map((f) => (
          <polygon
            key={f}
            points={cats.map((_, i) => `${px(i, max * f)},${py(i, max * f)}`).join(' ')}
            fill="none"
            stroke="currentColor"
            strokeOpacity="0.1"
            strokeWidth="1"
          />
        ))}
        {cats.map((_, i) => (
          <line key={i} x1={cx} y1={cy} x2={px(i, max)} y2={py(i, max)} stroke="currentColor" strokeOpacity="0.1" strokeWidth="1" />
        ))}
        {cats.map((c, i) => (
          <text key={c} x={px(i, max * 1.14)} y={py(i, max * 1.14)} textAnchor="middle" className="fill-muted-foreground" fontSize="9">
            {cellToString(c)}
          </text>
        ))}
        <polygon
          points={cats.map((_, i) => `${px(i, values[i] ?? 0)},${py(i, values[i] ?? 0)}`).join(' ')}
          fill={PALETTE[0]}
          fillOpacity="0.22"
          stroke={PALETTE[0]}
          strokeWidth="2"
          strokeLinejoin="round"
        />
        {cats.map((c, i) => (
          <circle key={c} cx={px(i, values[i] ?? 0)} cy={py(i, values[i] ?? 0)} r="2.5" fill={PALETTE[0]}>
            <title>{`${cellToString(c)}: ${formatNumber(values[i])}`}</title>
          </circle>
        ))}
      </svg>
    </div>
  );
}

function TreemapChart({ data, height = 300 }: { data: ChartData; height?: number }) {
  const labels = (data.labels ?? []) as string[];
  const values = (data.values ?? []) as number[];
  const W = 640;
  const H = height;
  const total = values.reduce((a, b) => a + b, 0) || 1;

  let x = 2;
  let y = 2;
  const w = W - 4;
  const h = H - 4;

  const rects: { x: number; y: number; w: number; h: number; label: string; value: number; i: number }[] = [];

  // simple slice-and-dice treemap
  const draw = (items: { label: string; value: number; i: number }[], rx: number, ry: number, rw: number, rh: number, hFirst: boolean) => {
    if (items.length === 0) return;
    if (items.length === 1) {
      rects.push({ x: rx, y: ry, w: rw, h: rh, label: items[0].label, value: items[0].value, i: items[0].i });
      return;
    }
    const split = items.length / 2 + (items.length % 2);
    const part1 = items.slice(0, Math.round(split)).reduce((a, b) => a + b.value, 0);
    const part1f = part1 / (items.reduce((a, b) => a + b.value, 0) || 1);
    if (hFirst) {
      const w1 = rw * part1f;
      draw(items.slice(0, Math.round(split)), rx, ry, w1, rh, false);
      draw(items.slice(Math.round(split)), rx + w1, ry, rw - w1, rh, false);
    } else {
      const h1 = rh * part1f;
      draw(items.slice(0, Math.round(split)), rx, ry, rw, h1, true);
      draw(items.slice(Math.round(split)), rx, ry + h1, rw, rh - h1, true);
    }
  };

  const items = values.map((v, i) => ({ label: labels[i] ?? '', value: v || 0.0001, i })).sort((a, b) => b.value - a.value);
  draw(items, x, y, w, h, true);

  return (
    <div className="relative select-none" style={{ height: H }}>
      <svg viewBox={`0 0 ${W} ${H}`} className="h-full w-full">
        {rects.map((r) => (
          <g key={r.i}>
            <rect x={r.x} y={r.y} width={r.w} height={r.h} rx="3" fill={PALETTE[r.i % PALETTE.length]} opacity="0.9">
              <title>{`${r.label}: ${formatNumber(r.value)}`}</title>
            </rect>
            {r.w > 40 && r.h > 22 && (
              <>
                <text x={r.x + 6} y={r.y + 14} fontSize="9.5" fontWeight="600" fill="#fff">
                  {cellToString(r.label).slice(0, 24)}
                </text>
                <text x={r.x + 6} y={r.y + 25} fontSize="8.5" fill="#fff" opacity="0.85">
                  {formatNumber(r.value)} · {((r.value / total) * 100).toFixed(1)}%
                </text>
              </>
            )}
          </g>
        ))}
      </svg>
    </div>
  );
}

function FunnelChart({ data, height = 300 }: { data: ChartData; height?: number }) {
  const labels = (data.labels ?? []) as string[];
  const values = (data.values ?? []) as number[];
  const W = 560;
  const H = Math.max(height, values.length * 44 + 24);
  const max = Math.max(...values, 1);
  const wMax = W - 100;

  return (
    <div className="relative select-none" style={{ height: H }}>
      <svg viewBox={`0 0 ${W} ${H}`} className="h-full w-full">
        {values.map((v, i) => {
          const frac = v / max;
          const bw = wMax * frac;
          const x0 = (W - bw) / 2;
          const y0 = i * 44 + 6;
          return (
            <g key={i}>
              <path
                d={`M ${x0} ${y0} L ${x0 + bw} ${y0} L ${x0 + bw - Math.min(14, bw * 0.15)} ${y0 + 34} L ${x0 + Math.min(14, bw * 0.15)} ${y0 + 34} Z`}
                fill={PALETTE[i % PALETTE.length]}
                opacity="0.92"
              >
                <title>{`${cellToString(labels[i])}: ${formatNumber(v)}`}</title>
              </path>
              <text x={x0 + bw + 8} y={y0 + 22} fontSize="10" className="fill-muted-foreground" fontWeight="500">
                {formatCompact(v)} ({((v / max) * 100).toFixed(0)}%)
              </text>
              <text x={W / 2} y={y0 + 12} textAnchor="middle" fontSize="10" fill="#fff" fontWeight="600">
                {cellToString(labels[i])}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

function WaterfallChart({ data, height = 300 }: { data: ChartData; height?: number }) {
  const labels = (data.labels ?? []) as string[];
  const values = (data.values ?? []) as number[];
  const running = (data.running as number[]) ?? values.reduce<number[]>((a, v) => [...a, (a[a.length - 1] ?? 0) + v], []);
  const W = 640;
  const H = height;
  const padL = 42;
  const padR = 14;
  const padT = 12;
  const padB = 34;
  const iw = W - padL - padR;
  const ih = H - padT - padB;

  let min = 0;
  let max = 0;
  running.forEach((r) => {
    min = Math.min(min, r);
    max = Math.max(max, r);
  });
  values.forEach((v) => {
    if (v >= 0) max = Math.max(max, v);
    else min = Math.min(min, v);
  });
  const ticks = niceTicks(min * 1.05, max * 1.05, 4);
  const yMin = ticks[0];
  const yMax = ticks[ticks.length - 1];
  const y = (v: number) => padT + ih - ((v - yMin) / (yMax - yMin || 1)) * ih;

  const n = labels.length;
  const band = iw / Math.max(n, 1);
  const bw = band * 0.62;

  return (
    <div className="relative select-none" style={{ height: H }}>
      <svg viewBox={`0 0 ${W} ${H}`} className="h-full w-full">
        {ticks.map((t) => (
          <g key={t}>
            <line x1={padL} x2={W - padR} y1={y(t)} y2={y(t)} stroke="currentColor" strokeOpacity="0.08" strokeWidth="1" />
            <text x={padL - 6} y={y(t) + 3} textAnchor="end" className="fill-muted-foreground" fontSize="9">
              {axisTick(t, ticks[1] - ticks[0] || 1)}
            </text>
          </g>
        ))}
        {running.map((r, i) => {
          const prev = i === 0 ? 0 : running[i - 1];
          const delta = values[i];
          const yTop = y(r);
          const yBot = y(prev);
          const col = delta >= 0 ? PALETTE[0] : PALETTE[4];
          return (
            <g key={i}>
              <line x1={padL + i * band + band / 2} x2={padL + (i + 1) * band + band / 2} y1={yBot} y2={yBot} stroke="currentColor" strokeOpacity="0.25" strokeDasharray="3 3" strokeWidth="1" />
              <rect x={padL + i * band + (band - bw) / 2} y={Math.min(yTop, yBot)} width={bw} height={Math.max(1, Math.abs(yTop - yBot))} rx="2.5" fill={col} opacity="0.9">
                <title>{`${cellToString(labels[i])}: ${formatNumber(delta)} → ${formatNumber(r)}`}</title>
              </rect>
              <text x={padL + i * band + band / 2} y={H - padB + 14} textAnchor="middle" className="fill-muted-foreground" fontSize="8.5">
                {cellToString(labels[i]).slice(0, 8)}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

function BoxPlotChart({ data, height = 300 }: { data: ChartData; height?: number }) {
  const boxes = (data.boxes ?? []) as { name: string; min: number; q1: number; median: number; q3: number; max: number; outliers: number[]; count: number }[];
  const W = Math.max(560, boxes.length * 90);
  const H = height;
  const padL = 42;
  const padR = 14;
  const padT = 12;
  const padB = 34;
  const vals = boxes.flatMap((b) => [b.min, b.max, ...(b.outliers ?? [])]);
  const ticks = niceTicks(Math.min(...vals, 0), Math.max(...vals, 1), 4);
  const yMin = ticks[0];
  const yMax = ticks[ticks.length - 1];
  const y = (v: number) => padT + (H - padT - padB) - ((v - yMin) / (yMax - yMin || 1)) * (H - padT - padB);

  return (
    <div className="relative select-none overflow-auto scrollbar-thin">
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" style={{ height: H }}>
        {ticks.map((t) => (
          <g key={t}>
            <line x1={padL} x2={W - padR} y1={y(t)} y2={y(t)} stroke="currentColor" strokeOpacity="0.08" strokeWidth="1" />
            <text x={padL - 6} y={y(t) + 3} textAnchor="end" className="fill-muted-foreground" fontSize="9">
              {axisTick(t, ticks[1] - ticks[0] || 1)}
            </text>
          </g>
        ))}
        {boxes.map((b, i) => {
          const cx = padL + (i + 0.5) * ((W - padL - padR) / Math.max(boxes.length, 1));
          const bw = Math.min(46, (W - padL - padR) / boxes.length * 0.5);
          return (
            <g key={i}>
              <line x1={cx} x2={cx} y1={y(b.min)} y2={y(b.max)} stroke="currentColor" strokeOpacity="0.5" strokeWidth="1.2" />
              <line x1={cx - bw / 2} x2={cx + bw / 2} y1={y(b.min)} y2={y(b.min)} stroke="currentColor" strokeOpacity="0.6" strokeWidth="1.2" />
              <line x1={cx - bw / 2} x2={cx + bw / 2} y1={y(b.max)} y2={y(b.max)} stroke="currentColor" strokeOpacity="0.6" strokeWidth="1.2" />
              <rect x={cx - bw / 2} y={y(b.q3)} width={bw} height={Math.max(2, y(b.q1) - y(b.q3))} rx="2" fill={PALETTE[0]} opacity="0.35" stroke={PALETTE[0]} strokeWidth="1.2" />
              <line x1={cx - bw / 2} x2={cx + bw / 2} y1={y(b.median)} y2={y(b.median)} stroke="var(--foreground)" strokeWidth="1.6" />
              {(b.outliers ?? []).map((o, oi) => (
                <circle key={oi} cx={cx} cy={y(o)} r="2.5" fill="currentColor" opacity="0.5">
                  <title>{formatNumber(o)}</title>
                </circle>
              ))}
              <text x={cx} y={H - padB + 14} textAnchor="middle" className="fill-muted-foreground" fontSize="9">
                {cellToString(b.name).slice(0, 12)}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

function GaugeChart({ data, height = 240 }: { data: ChartData; height?: number }) {
  const g = data.gauge ?? { value: 0, min: 0, max: 100, label: '' };
  const frac = Math.min(1, Math.max(0, (g.value - g.min) / ((g.max - g.min) || 1)));
  const cx = 200;
  const cy = 180;
  const r = 140;
  const a0 = Math.PI;
  const a1 = 2 * Math.PI;
  const f = (t: number) => `${cx + r * Math.cos(a0 + (a1 - a0) * t)},${cy + r * Math.sin(a0 + (a1 - a0) * t)}`;

  const arcPath = (from: number, to: number) => {
    const large = to - from > 0.5 ? 1 : 0;
    return `M ${f(from)} A ${r} ${r} 0 ${large} 1 ${f(to)}`;
  };

  return (
    <div className="relative select-none" style={{ height }}>
      <svg viewBox="0 0 400 215" className="h-full w-full">
        <defs>
          <linearGradient id="gaugeGrad" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor={PALETTE[0]} />
            <stop offset="100%" stopColor={PALETTE[3]} />
          </linearGradient>
        </defs>
        <path d={arcPath(0, 1)} fill="none" stroke="currentColor" strokeOpacity="0.12" strokeWidth="14" strokeLinecap="round" />
        <path d={arcPath(0, frac)} fill="none" stroke="url(#gaugeGrad)" strokeWidth="14" strokeLinecap="round" />
        <text x={cx} y={cy - 14} textAnchor="middle" fontSize="11" className="fill-muted-foreground">
          {g.label || ''}
        </text>
        <text x={cx} y={cy + 20} textAnchor="middle" fontSize="34" fontWeight="700" className="tabular-nums">
          {formatNumber(g.value)}
        </text>
        <text x={cx - r - 4} y={cy + 76} fontSize="9" className="fill-muted-foreground">
          {formatCompact(g.min)}
        </text>
        <text x={cx + r + 4} y={cy + 76} fontSize="9" textAnchor="end" className="fill-muted-foreground">
          {formatCompact(g.max)}
        </text>
      </svg>
    </div>
  );
}

function KPICard({ data }: { data: ChartData }) {
  const k = data.kpi;
  if (!k) return null;
  return (
    <div className="flex h-full min-h-[120px] flex-col items-start justify-center gap-1 p-5">
      <div className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">{k.label}</div>
      <div className="text-4xl font-bold tabular-nums tracking-tight">{formatNumber(k.value)}</div>
      <div className="mt-1 flex items-center gap-2 text-[11px] text-muted-foreground">
        <span className="rounded bg-muted px-1.5 py-0.5 font-mono text-[10px] uppercase">{k.aggregation}</span>
        <span>{k.column}</span>
        <span>· {formatCompact(k.row_count)} rows</span>
      </div>
    </div>
  );
}

function TableChart({ data, height }: { data: ChartData; height?: number }) {
  const columns = (data.columns ?? []) as string[];
  const rows = (data.rows ?? []) as unknown[][];
  return (
    <div className="scrollbar-thin overflow-auto rounded-lg border border-border" style={{ height: height ? `${height}px` : '100%' }}>
      <table className="w-full text-left text-xs">
        <thead className="sticky top-0 bg-muted/80 backdrop-blur">
          <tr>
            {columns.map((c) => (
              <th key={c} className="whitespace-nowrap border-b border-border px-3 py-2 font-semibold text-muted-foreground">
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, ri) => (
            <tr key={ri} className={ri % 2 === 1 ? 'bg-muted/40' : ''}>
              {r.map((v, ci) => (
                <td key={ci} className="whitespace-nowrap border-b border-border/60 px-3 py-1.5 tabular-nums">
                  {cellToString(v)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function HistogramChart({ data, height = 300 }: { data: ChartData; height?: number }) {
  const values = (data.values ?? []) as number[];
  const labels = (data.labels ?? []) as string[];
  return <CartesianChart labels={labels} values={[values]} seriesNames={['count']} type="column" height={height} />;
}

export function ChartView({ data, chartType, height }: { data: ChartData; chartType: string; height?: number }) {
  const values = (data.values ?? []) as number[];
  const labels = (data.labels ?? []) as string[];
  const series = data.series as { name: string; values: number[] }[] | undefined;
  const seriesValues = series ? series.map((s) => s.values) : [values];
  const seriesNames = series ? series.map((s) => s.name) : [];

  switch (chartType) {
    case 'line':
    case 'area':
      return <CartesianChart labels={labels} values={seriesValues.length ? seriesValues : [values]} seriesNames={series?.length ? seriesNames : []} type={chartType} height={height} />;
    case 'bar':
      return <CartesianChart labels={labels} values={[values]} seriesNames={[]} type="bar" height={height} />;
    case 'column':
    case 'grouped_bar':
    case 'grouped_column':
      return <CartesianChart labels={labels} values={seriesValues.length ? seriesValues : [values]} seriesNames={seriesNames} grouped type="column" height={height} />;
    case 'stacked_bar':
    case 'stacked_column':
      return <CartesianChart labels={labels} values={seriesValues} seriesNames={seriesNames} stacked type="column" height={height} />;
    case 'hundred_bar':
    case 'hundred_column':
    case 'hundred_stacked_bar':
    case 'hundred_stacked_column':
      return <CartesianChart labels={labels} values={seriesValues} seriesNames={seriesNames} stacked hundred type="column" height={height} />;
    case 'pie':
    case 'donut':
      return <PieDoughnut labels={labels} values={values} doughnut={chartType === 'donut'} height={height} />;
    case 'scatter':
    case 'bubble':
      return <ScatterBubble data={data} height={height} />;
    case 'histogram':
      return <HistogramChart data={data} height={height} />;
    case 'heatmap':
      return <HeatmapChart data={data} height={height} />;
    case 'radar':
      return <RadarChart data={data} height={height} />;
    case 'treemap':
      return <TreemapChart data={data} height={height} />;
    case 'sunburst':
      return <TreemapChart data={data} height={height} />;
    case 'funnel':
      return <FunnelChart data={data} height={height} />;
    case 'waterfall':
      return <WaterfallChart data={data} height={height} />;
    case 'box':
      return <BoxPlotChart data={data} height={height} />;
    case 'gauge':
      return <GaugeChart data={data} height={height} />;
    case 'kpi':
      return <KPICard data={data} />;
    case 'table':
      return <TableChart data={data} height={height} />;
    default:
      return (
        <div className="flex h-full items-center justify-center text-xs text-muted-foreground">
          Unsupported chart: {chartType}
        </div>
      );
  }
}

export function Legend({ series }: { series: { name: string }[] }) {
  if (!series.length) return null;
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 px-1 pb-1">
      {series.map((s, i) => (
        <div key={s.name} className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
          <span className="h-2.5 w-2.5 rounded-full" style={{ background: PALETTE[i % PALETTE.length] }} />
          {s.name}
        </div>
      ))}
    </div>
  );
}

export function MiniSparkline({ values, width = 100, height = 28, color = PALETTE[0] }: { values: number[]; width?: number; height?: number; color?: string }) {
  if (!values.length) return null;
  const max = Math.max(...values, 1);
  const min = Math.min(...values, 0);
  const pts = values.map((v, i) => `${(i / Math.max(values.length - 1, 1)) * width},${height - ((v - min) / (max - min || 1)) * (height - 4) - 2}`);
  return (
    <svg width={width} height={height} className="overflow-visible">
      <path d={`M ${pts.join(' L ')}`} fill="none" stroke={color} strokeWidth="1.6" strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  );
}