/**
 * TRUTHLINE — reusable presentational components
 * ==========================================================================
 * Small, dumb, styled pieces the pages compose. No data fetching here.
 */

import type { ReactNode } from 'react';
import type { FreshnessLabel, SourceType, Verdict } from '../types';
import { freshnessMeta, sourceMeta, verdictMeta } from '../utils';

// ── Verdict badge ──────────────────────────────────────────────────────────
export function VerdictBadge({ verdict, large }: { verdict: string; large?: boolean }) {
  const meta = verdictMeta(verdict);
  return (
    <span
      className="chip"
      style={{
        color: meta.color,
        background: meta.bg,
        borderColor: meta.color,
        fontSize: large ? '0.95rem' : undefined,
        padding: large ? '0.35rem 0.9rem' : undefined,
      }}
    >
      {meta.icon} {meta.label}
    </span>
  );
}

// ── Source-type chip ───────────────────────────────────────────────────────
export function SourceChip({ type }: { type: SourceType | string }) {
  const meta = sourceMeta(type);
  return (
    <span className="chip" style={{ color: meta.color, background: meta.bg }}>
      {meta.label}
    </span>
  );
}

// ── Freshness chip ─────────────────────────────────────────────────────────
export function FreshnessChip({ label, score }: { label: string; score?: number }) {
  const meta = freshnessMeta(label);
  return (
    <span
      className="chip"
      style={{ color: meta.color, background: meta.bg }}
      title={score !== undefined ? `freshness ${score.toFixed(3)}` : undefined}
    >
      {label}
    </span>
  );
}

// ── Metric tile ────────────────────────────────────────────────────────────
export function Metric({
  label,
  value,
  hint,
  accent,
}: {
  label: string;
  value: ReactNode;
  hint?: string;
  accent?: string;
}) {
  return (
    <div className="metric" style={accent ? { borderTopColor: accent } : undefined}>
      <div className="metric__value">{value}</div>
      <div className="metric__label">{label}</div>
      {hint ? <div className="metric__hint">{hint}</div> : null}
    </div>
  );
}

// ── Section wrapper ────────────────────────────────────────────────────────
export function Section({
  title,
  subtitle,
  children,
  actions,
}: {
  title: string;
  subtitle?: string;
  children: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <section className="panel section">
      <div className="section__head">
        <div>
          <h3 className="panel__title">{title}</h3>
          {subtitle ? <p className="section__sub">{subtitle}</p> : null}
        </div>
        {actions}
      </div>
      {children}
    </section>
  );
}

// ── Empty state ────────────────────────────────────────────────────────────
export function Empty({ message, hint }: { message: string; hint?: string }) {
  return (
    <div className="empty">
      <div className="empty__mark">○</div>
      <p>{message}</p>
      {hint ? <p className="faint">{hint}</p> : null}
    </div>
  );
}

// ── Loading state ──────────────────────────────────────────────────────────
export function Loading({ label = 'Loading' }: { label?: string }) {
  return (
    <div className="loading">
      <span className="spinner" />
      {label}…
    </div>
  );
}

// ── Error banner ───────────────────────────────────────────────────────────
export function ErrorBanner({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="banner banner--err">
      <span>{message}</span>
      {onRetry ? (
        <button className="button button--ghost" onClick={onRetry}>
          Retry
        </button>
      ) : null}
    </div>
  );
}

// ── Verdict colour for arbitrary verdict strings (used by CSS-driven cards) ─
export function verdictColor(verdict: string): string {
  return verdictMeta(verdict).color;
}

export function freshnessColor(label: FreshnessLabel | string): string {
  return freshnessMeta(label).color;
}

export type { Verdict, FreshnessLabel, SourceType };
