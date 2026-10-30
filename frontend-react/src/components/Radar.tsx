/**
 * TRUTHLINE — green radar sweep
 * ==========================================================================
 * The command-centre centrepiece. Concentric rings, a rotating sweep, and one
 * blip per source coloured by its freshness band:
 *
 *   green = FRESH · amber = AGING · orange = STALE · grey = EXPIRED
 *
 * Blips are placed by angle (evenly spaced) and radius (freshness — the fresher
 * the evidence, the further from the centre it sits, i.e. the more "on scope").
 */

import { useEffect, useRef, useState } from 'react';
import type { RadarBlip } from '../types';
import { freshnessMeta } from '../utils';
import './Radar.css';

interface RadarProps {
  blips: RadarBlip[];
  size?: number;
}

export default function Radar({ blips, size = 340 }: RadarProps) {
  const [angle, setAngle] = useState(0);
  const frame = useRef<number | null>(null);
  const last = useRef<number>(0);

  // requestAnimationFrame sweep — cheap, and it stops when the tab is hidden.
  useEffect(() => {
    const tick = (t: number) => {
      if (t - last.current > 40) {
        setAngle((a) => (a + 3) % 360);
        last.current = t;
      }
      frame.current = requestAnimationFrame(tick);
    };
    frame.current = requestAnimationFrame(tick);
    return () => {
      if (frame.current) cancelAnimationFrame(frame.current);
    };
  }, []);

  const R = 100; // viewBox radius
  const cx = 0;
  const cy = 0;

  return (
    <div className="radar" style={{ width: size, height: size }}>
      <svg viewBox="-115 -115 230 230" className="radar__svg" role="img" aria-label="Source radar">
        <defs>
          <radialGradient id="radarGlow" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="#84cc16" stopOpacity="0.22" />
            <stop offset="70%" stopColor="#84cc16" stopOpacity="0.05" />
            <stop offset="100%" stopColor="#84cc16" stopOpacity="0" />
          </radialGradient>
        </defs>

        {/* glow + rings */}
        <circle cx={cx} cy={cy} r={R} fill="url(#radarGlow)" />
        {[R, R * 0.75, R * 0.5, R * 0.25].map((r) => (
          <circle
            key={r}
            cx={cx}
            cy={cy}
            r={r}
            fill="none"
            stroke="#84cc16"
            strokeOpacity={r === R ? 0.45 : 0.22}
            strokeWidth={r === R ? 1.4 : 0.8}
          />
        ))}

        {/* cross hairs */}
        <line x1={-R} y1={0} x2={R} y2={0} stroke="#84cc16" strokeOpacity="0.14" strokeWidth="0.8" />
        <line x1={0} y1={-R} x2={0} y2={R} stroke="#84cc16" strokeOpacity="0.14" strokeWidth="0.8" />

        {/* sweep wedge */}
        <g transform={`rotate(${angle})`}>
          <path
            d={`M 0 0 L ${R} 0 A ${R} ${R} 0 0 0 ${R * 0.707} ${-R * 0.707} Z`}
            fill="#84cc16"
            fillOpacity="0.16"
          />
          <line x1={0} y1={0} x2={R} y2={0} stroke="#84cc16" strokeWidth="2" strokeOpacity="0.9" />
        </g>

        {/* blips */}
        {blips.map((b, i) => {
          const a = (i / Math.max(blips.length, 1)) * Math.PI * 2 - Math.PI / 2;
          const r = 8 + Math.max(0, Math.min(1, b.severity)) * (R - 18);
          const x = Math.cos(a) * r;
          const y = Math.sin(a) * r;
          const meta = freshnessMeta(b.band);
          return (
            <g key={b.id}>
              <circle cx={x} cy={y} r="5.5" fill={meta.color} stroke="#fff" strokeWidth="1.4" />
              <circle cx={x} cy={y} r="5.5" fill="none" stroke={meta.color} strokeOpacity="0.35" strokeWidth="3">
                <animate attributeName="r" from="5.5" to="11" dur="2.2s" repeatCount="indefinite" />
                <animate attributeName="stroke-opacity" from="0.4" to="0" dur="2.2s" repeatCount="indefinite" />
              </circle>
              <title>{`${b.label} — ${b.band}`}</title>
            </g>
          );
        })}
      </svg>

      <div className="radar__legend">
        {(['FRESH', 'AGING', 'STALE', 'EXPIRED'] as const).map((band) => (
          <span className="radar__legend-item" key={band}>
            <i style={{ background: freshnessMeta(band).color }} />
            {band}
          </span>
        ))}
      </div>
    </div>
  );
}
