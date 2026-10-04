import React from 'react';
import {interpolate, Easing} from 'remotion';
import {C, SANS, MONO, ownerColor, Cat, catColor, catLabel} from './theme';
import {boxes, chips, edges, altEdge, Box, Chip, Edge, pathD, polyLength, P, along} from './layout';

export const clamp01 = (v: number) => Math.max(0, Math.min(1, v));

export const fade = (frame: number, start: number, dur = 10) =>
  interpolate(frame, [start, start + dur], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});

export const ease = Easing.inOut(Easing.cubic);

const tint = (color: string, alpha: string) =>
  `linear-gradient(0deg, ${color}${alpha}, ${color}${alpha}), ${C.panel}`;

// ---------- Map ----------

export type MapState = {
  appear?: (id: string) => number;
  glow?: Record<string, {color: string; k: number}>;
  edgeGlow?: Record<string, {color: string; k: number}>;
  dim?: Record<string, number>;
  alt?: number; // draw progress of the direct browser to Connect wire
  dot?: {x: number; y: number; color: string; opacity: number} | null;
};

const BoxView: React.FC<{b: Box; a: number; glow?: {color: string; k: number}; dim: number}> = ({b, a, glow, dim}) => {
  const color = ownerColor[b.owner];
  const k = glow?.k ?? 0;
  const g = glow?.color ?? color;
  return (
    <div
      style={{
        position: 'absolute',
        left: b.x,
        top: b.y,
        width: b.w,
        height: b.h,
        opacity: a * dim,
        transform: `translateY(${(1 - a) * 14}px)`,
        background: k > 0 ? tint(g, Math.round(k * 40).toString(16).padStart(2, '0')) : C.panel,
        border: `${b.dashed ? 'dashed' : 'solid'} 2px ${k > 0.05 ? g : color + '88'}`,
        borderRadius: 10,
        boxShadow: k > 0 ? `0 0 ${36 * k}px ${g}${Math.round(k * 150).toString(16).padStart(2, '0')}` : 'none',
        boxSizing: 'border-box',
        padding: '16px 16px 12px',
      }}
    >
      <div style={{position: 'absolute', left: 0, top: 0, right: 0, height: 6, background: color, borderRadius: '8px 8px 0 0'}} />
      <div style={{fontFamily: SANS, fontWeight: 600, fontSize: 30, lineHeight: '36px', color: C.text}}>{b.title}</div>
      {b.lines.map((l, i) => (
        <div
          key={i}
          style={{
            fontFamily: l.mono ? MONO : SANS,
            fontSize: 28,
            lineHeight: '36px',
            color: l.color ?? C.muted,
            whiteSpace: 'nowrap',
          }}
        >
          {l.text}
        </div>
      ))}
      {b.tag ? (
        <div
          style={{
            position: 'absolute',
            right: 16,
            top: -24,
            background: C.bg,
            border: `2px solid ${color}`,
            borderRadius: 22,
            padding: '0 14px',
            fontFamily: SANS,
            fontSize: 28,
            lineHeight: '38px',
            color: C.text,
          }}
        >
          {b.tag}
        </div>
      ) : null}
    </div>
  );
};

const ChipView: React.FC<{c: Chip; a: number; glow?: {color: string; k: number}; dim: number}> = ({c, a, glow, dim}) => {
  const k = glow?.k ?? 0;
  const g = glow?.color ?? C.amber;
  return (
    <div
      style={{
        position: 'absolute',
        left: c.x,
        top: c.y,
        width: c.w,
        height: c.h,
        opacity: a * dim,
        boxSizing: 'border-box',
        borderRadius: 6,
        border: `2px solid ${k > 0.05 ? g : C.line}`,
        background: k > 0 ? `${g}${Math.round(k * 70).toString(16).padStart(2, '0')}` : C.bg,
        boxShadow: k > 0 ? `0 0 ${24 * k}px ${g}aa` : 'none',
        fontFamily: c.mono ? MONO : SANS,
        fontSize: 28,
        lineHeight: '38px',
        color: k > 0.3 ? C.text : C.muted,
        paddingLeft: 14,
      }}
    >
      {c.label}
    </div>
  );
};

const EdgeView: React.FC<{e: Edge; a: number; glow?: {color: string; k: number}; dim: number}> = ({e, a, glow, dim}) => {
  const k = glow?.k ?? 0;
  const len = polyLength(e.pts);
  return (
    <g opacity={dim}>
      <path
        d={pathD(e.pts)}
        fill="none"
        stroke={k > 0.05 ? glow!.color : '#4a5a6b'}
        strokeWidth={k > 0.05 ? 6 : 4}
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeDasharray={e.dashed ? '10 9' : `${len} ${len}`}
        strokeDashoffset={e.dashed ? 0 : len * (1 - a)}
        opacity={e.dashed ? a : 1}
      />
    </g>
  );
};

export const MapView: React.FC<{s: MapState}> = ({s}) => {
  const appear = s.appear ?? (() => 1);
  const dim = (id: string) => s.dim?.[id] ?? 1;
  const edgeA = (e: Edge) => Math.min(appear(e.ends[0]), appear(e.ends[1]));
  const edgeDim = (e: Edge) => Math.min(dim(e.ends[0]), dim(e.ends[1]), dim(e.id));
  const altLen = polyLength(altEdge.pts);
  return (
    <>
      <svg width={1920} height={1080} style={{position: 'absolute', left: 0, top: 0}}>
        {edges.map((e) => (
          <EdgeView key={e.id} e={e} a={edgeA(e)} glow={s.edgeGlow?.[e.id]} dim={edgeDim(e)} />
        ))}
        {s.alt ? (
          <path
            d={pathD(altEdge.pts)}
            fill="none"
            stroke={s.edgeGlow?.eAlt && s.edgeGlow.eAlt.k > 0.05 ? s.edgeGlow.eAlt.color : C.amber}
            strokeWidth={6}
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeDasharray={`${altLen} ${altLen}`}
            strokeDashoffset={altLen * (1 - s.alt)}
          />
        ) : null}
      </svg>
      {boxes.map((b) => (
        <BoxView key={b.id} b={b} a={appear(b.id)} glow={s.glow?.[b.id]} dim={dim(b.id)} />
      ))}
      {chips.map((c) => (
        <ChipView key={c.id} c={c} a={appear(c.id)} glow={s.glow?.[c.id]} dim={dim('designer')} />
      ))}
      {s.dot && s.dot.opacity > 0 ? (
        <svg width={1920} height={1080} style={{position: 'absolute', left: 0, top: 0}}>
          <circle cx={s.dot.x} cy={s.dot.y} r={26} fill={s.dot.color} opacity={0.28 * s.dot.opacity} />
          <circle cx={s.dot.x} cy={s.dot.y} r={14} fill={s.dot.color} stroke={C.text} strokeWidth={3} opacity={s.dot.opacity} />
        </svg>
      ) : null}
    </>
  );
};

// ---------- Header and clock ----------

export const Header: React.FC<{title: string; a: number; clock?: number | null; clockLabel?: string}> = ({title, a, clock, clockLabel}) => (
  <>
    <div
      style={{
        position: 'absolute',
        left: 40,
        top: 30,
        width: 1300,
        fontFamily: SANS,
        fontWeight: 600,
        fontSize: 40,
        lineHeight: '52px',
        color: C.text,
        opacity: a,
      }}
    >
      {title}
    </div>
    {clock !== undefined && clock !== null ? (
      <div style={{position: 'absolute', right: 40, top: 22, display: 'flex', alignItems: 'baseline', gap: 18, opacity: a}}>
        <span style={{fontFamily: SANS, fontSize: 28, color: C.muted}}>{clockLabel ?? 'time to first words'}</span>
        <span style={{fontFamily: MONO, fontWeight: 500, fontSize: 60, color: C.text, minWidth: 250, textAlign: 'right'}}>
          {clock.toFixed(2)} s
        </span>
      </div>
    ) : null}
  </>
);

// ---------- Caption panel ----------

export const Panel: React.FC<{x?: number; y?: number; w?: number; h?: number; a?: number; children: React.ReactNode}> = ({
  x = 40,
  y = 530,
  w = 820,
  h = 342,
  a = 1,
  children,
}) => (
  <div
    style={{
      position: 'absolute',
      left: x,
      top: y,
      width: w,
      height: h,
      boxSizing: 'border-box',
      background: C.panel,
      border: `2px solid ${C.line}`,
      borderRadius: 12,
      padding: '22px 26px',
      opacity: a,
      overflow: 'hidden',
    }}
  >
    {children}
  </div>
);

export type Caption = {kicker?: string; owner?: string; ownerColor?: string; title: string; time?: string; note?: string};

export const CaptionView: React.FC<{c: Caption; a: number}> = ({c, a}) => (
  <div style={{opacity: a, transform: `translateY(${(1 - a) * 8}px)`}}>
    <div style={{display: 'flex', justifyContent: 'space-between', fontSize: 28, lineHeight: '36px', fontFamily: SANS}}>
      <span style={{color: C.muted}}>{c.kicker ?? ''}</span>
      <span style={{color: c.ownerColor ?? C.muted}}>{c.owner ?? ''}</span>
    </div>
    <div style={{fontFamily: SANS, fontWeight: 600, fontSize: 38, lineHeight: '48px', color: C.text, marginTop: 6}}>{c.title}</div>
    {c.time ? (
      <div style={{fontFamily: MONO, fontWeight: 500, fontSize: 60, lineHeight: '74px', color: c.ownerColor ?? C.text, marginTop: 4}}>{c.time}</div>
    ) : null}
    {c.note ? (
      <div style={{fontFamily: SANS, fontSize: 28, lineHeight: '38px', color: C.muted, marginTop: 4}}>{c.note}</div>
    ) : null}
  </div>
);

// ---------- Stacked bar ----------

export const BAR_ORDER: Cat[] = ['connect', 'agentcore', 'net', 'ours', 'bedrock'];

export const Bar: React.FC<{
  values: Record<Cat, number>;
  scale: number; // seconds that fill the full width
  a: number;
  show?: Cat[];
  ghost?: {secs: number; label: string};
}> = ({values, scale, a, show = ['connect', 'agentcore', 'net', 'ours'], ghost}) => {
  const X = 40;
  const WIDTH = 1840;
  const Y = 900;
  const px = (s: number) => (s / scale) * WIDTH;
  let x = X;
  const segs = BAR_ORDER.filter((c) => values[c] > 0).map((c) => {
    const w = px(values[c]);
    const seg = {c, x, w};
    x += w;
    return seg;
  });
  const rows: Cat[][] = [show.slice(0, 3), show.slice(3)];
  return (
    <div style={{position: 'absolute', left: 0, top: 0, opacity: a}}>
      <div style={{position: 'absolute', left: X, top: Y, width: WIDTH, height: 44, background: C.panel, borderRadius: 6, border: `1px solid ${C.line}`}} />
      {ghost ? (
        <div
          style={{
            position: 'absolute',
            left: X,
            top: Y,
            width: px(ghost.secs),
            height: 44,
            boxSizing: 'border-box',
            border: `2px dashed ${C.muted}`,
            borderRadius: 6,
            fontFamily: SANS,
            fontSize: 28,
            lineHeight: '40px',
            color: C.muted,
            textAlign: 'right',
            paddingRight: 14,
          }}
        >
          {ghost.label}
        </div>
      ) : null}
      {segs.map((s) => (
        <div
          key={s.c}
          style={{position: 'absolute', left: s.x, top: Y, width: Math.max(0, s.w - 2), height: 44, background: catColor[s.c], borderRadius: 4}}
        />
      ))}
      {rows.map((row, ri) => (
        <div key={ri} style={{position: 'absolute', left: X, top: Y + 58 + ri * 44, display: 'flex'}}>
          {row.map((c) => (
            <div key={c} style={{width: 613, display: 'flex', alignItems: 'center', gap: 14}}>
              <div style={{width: 24, height: 24, borderRadius: 4, background: catColor[c]}} />
              <span style={{fontFamily: SANS, fontSize: 28, color: C.text}}>{catLabel[c]}</span>
              <span style={{fontFamily: MONO, fontSize: 28, color: C.muted}}>{values[c].toFixed(values[c] < 0.1 && values[c] > 0 ? 3 : 2)} s</span>
            </div>
          ))}
        </div>
      ))}
    </div>
  );
};

export const OwnerLegend: React.FC<{a: number}> = ({a}) => {
  const items: [string, string][] = [
    [C.grey, 'Internet and CloudFront'],
    [C.blue, 'AgentCore'],
    [C.amber, 'Amazon Connect and designer'],
    [C.green, 'Our code'],
    [C.violet, 'Bedrock models'],
  ];
  return (
    <div style={{position: 'absolute', left: 40, top: 930, display: 'flex', gap: 54, opacity: a}}>
      {items.map(([c, l]) => (
        <div key={l} style={{display: 'flex', alignItems: 'center', gap: 14}}>
          <div style={{width: 28, height: 28, borderRadius: 5, background: c}} />
          <span style={{fontFamily: SANS, fontSize: 30, color: C.text}}>{l}</span>
        </div>
      ))}
    </div>
  );
};

// ---------- Step engine ----------

export type Step = {
  start: number; // frame, local to the scene
  travel: number; // frames of motion and clock counting
  path?: P[];
  color: string;
  add: Partial<Record<Cat, number>>;
  k?: number; // clock scale for this step's seconds
  glow: string[];
  edges?: string[];
  caption?: Caption;
};

export const zeroCats = (): Record<Cat, number> => ({connect: 0, agentcore: 0, net: 0, ours: 0, bedrock: 0});

export const runSteps = (frame: number, steps: Step[], base?: Record<Cat, number>) => {
  const cats = base ? {...base} : zeroCats();
  let clock = 0;
  let current = -1;
  steps.forEach((s, i) => {
    if (frame < s.start) return;
    current = i;
    const p = clamp01((frame - s.start) / s.travel);
    (Object.keys(s.add) as Cat[]).forEach((c) => {
      cats[c] += (s.add[c] ?? 0) * p;
      clock += (s.add[c] ?? 0) * p * (s.k ?? 1);
    });
  });
  const glow: Record<string, {color: string; k: number}> = {};
  const edgeGlow: Record<string, {color: string; k: number}> = {};
  let dot: MapState['dot'] = null;
  let caption: Caption | undefined;
  let captionA = 0;
  if (current >= 0) {
    const s = steps[current];
    const local = frame - s.start;
    const k = fade(local, 0, 6);
    s.glow.forEach((id) => (glow[id] = {color: s.color, k}));
    (s.edges ?? []).forEach((id) => (edgeGlow[id] = {color: s.color, k}));
    if (s.path) {
      const p = ease(clamp01(local / s.travel));
      const [x, y] = along(s.path, p);
      const op = Math.min(fade(local, 0, 4), 1 - fade(local, s.travel, 8));
      dot = {x, y, color: s.color, opacity: op};
    }
    caption = s.caption;
    captionA = fade(local, 0, 8);
  }
  return {cats, clock, glow, edgeGlow, dot, caption, captionA, current};
};
