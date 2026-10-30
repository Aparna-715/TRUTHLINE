/**
 * TRUTHLINE — presentation helpers
 * ==========================================================================
 * Maps backend enums to theme tokens and formats numbers. Components never
 * hard-code a hex or a verdict-to-colour lookup; they call these.
 *
 * Colours here are tuned for the dark cyber theme: bright foreground strokes
 * with low-alpha fills, so a badge reads as a lit indicator rather than a
 * pastel pill.
 */

import type { FreshnessLabel, Verdict } from './types';

// ── Verdict ────────────────────────────────────────────────────────────────
export const VERDICT_META: Record<
  Verdict,
  { label: string; color: string; bg: string; icon: string }
> = {
  SUPPORTED:   { label: 'Supported',   color: 'var(--v-supported)',   bg: 'rgba(0, 255, 156, 0.10)',  icon: '✓' },
  CONFLICTING: { label: 'Conflicting', color: 'var(--v-conflicting)', bg: 'rgba(255, 59, 92, 0.12)',  icon: '✕' },
  STALE:       { label: 'Stale',       color: 'var(--v-stale)',       bg: 'rgba(255, 176, 32, 0.12)', icon: '!' },
  UNCERTAIN:   { label: 'Uncertain',   color: 'var(--v-uncertain)',   bg: 'rgba(122, 143, 166, 0.14)',icon: '?' },
  UPDATED:     { label: 'Updated',     color: 'var(--v-updated)',     bg: 'rgba(77, 163, 255, 0.12)', icon: '↻' },
};

export function verdictMeta(verdict: string) {
  return VERDICT_META[(verdict?.toUpperCase() as Verdict)] ?? VERDICT_META.UNCERTAIN;
}

// ── Freshness bands ────────────────────────────────────────────────────────
export const FRESHNESS_META: Record<FreshnessLabel, { color: string; bg: string }> = {
  FRESH:   { color: 'var(--f-fresh)',   bg: 'rgba(0, 255, 156, 0.10)' },
  AGING:   { color: 'var(--f-aging)',   bg: 'rgba(255, 176, 32, 0.12)' },
  STALE:   { color: 'var(--f-stale)',   bg: 'rgba(255, 122, 24, 0.12)' },
  EXPIRED: { color: 'var(--f-expired)', bg: 'rgba(74, 90, 82, 0.22)' },
};

export function freshnessMeta(label: string) {
  return FRESHNESS_META[(label?.toUpperCase() as FreshnessLabel)] ?? FRESHNESS_META.EXPIRED;
}

/** Colour for a raw freshness score, derived from the same bands the backend uses. */
export function scoreColor(score: number): string {
  if (score > 0.7) return 'var(--f-fresh)';
  if (score > 0.3) return 'var(--f-aging)';
  if (score > 0.1) return 'var(--f-stale)';
  return 'var(--f-expired)';
}

// ── Source types ───────────────────────────────────────────────────────────
export const SOURCE_META: Record<string, { color: string; bg: string; label: string }> = {
  drone:     { color: 'var(--s-drone)',     bg: 'rgba(34, 211, 238, 0.10)',  label: 'Drone' },
  ground:    { color: 'var(--s-ground)',    bg: 'rgba(132, 204, 22, 0.10)',  label: 'Ground' },
  satellite: { color: 'var(--s-satellite)', bg: 'rgba(192, 132, 252, 0.10)', label: 'Satellite' },
  intel:     { color: 'var(--s-intel)',     bg: 'rgba(251, 191, 36, 0.10)',  label: 'Intel' },
};

export function sourceMeta(type: string) {
  return (
    SOURCE_META[type?.toLowerCase()] ?? {
      color: 'var(--text-muted)',
      bg: 'rgba(122, 143, 166, 0.12)',
      label: type || 'Unknown',
    }
  );
}

/** Short glyph used on the equipment roster. */
export function sourceGlyph(type: string): string {
  switch ((type || '').toLowerCase()) {
    case 'drone': return '◈';
    case 'ground': return '▲';
    case 'satellite': return '◎';
    case 'intel': return '✦';
    default: return '◇';
  }
}

// ── Relations ──────────────────────────────────────────────────────────────
export const RELATION_META: Record<string, { color: string; bg: string; label: string }> = {
  contradicts: { color: 'var(--v-conflicting)', bg: 'rgba(255, 59, 92, 0.12)',  label: 'Contradicts' },
  supports:    { color: 'var(--v-supported)',   bg: 'rgba(0, 255, 156, 0.10)',  label: 'Supports' },
  unrelated:   { color: 'var(--text-muted)',    bg: 'rgba(122, 143, 166, 0.12)',label: 'Unrelated' },
};

export function relationMeta(type: string) {
  return RELATION_META[type] ?? RELATION_META.unrelated;
}

// ── Threat levels (zones) ──────────────────────────────────────────────────
export const THREAT_META: Record<string, { color: string; label: string }> = {
  low:      { color: 'var(--v-supported)',   label: 'Low' },
  elevated: { color: 'var(--v-stale)',       label: 'Elevated' },
  high:     { color: 'var(--v-conflicting)', label: 'High' },
};

export function threatMeta(level: string) {
  return THREAT_META[(level || 'low').toLowerCase()] ?? THREAT_META.low;
}

// ── Number formatting ──────────────────────────────────────────────────────
export function pct(value: number, digits = 0): string {
  return `${(value * 100).toFixed(digits)}%`;
}

export function score(value: number): string {
  return value.toFixed(3);
}

/** "14:55" from an ISO timestamp, or "—" when unparseable. */
export function clockTime(iso: string | null | undefined): string {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false });
}

export function clockDateTime(iso: string | null | undefined): string {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString([], {
    day: '2-digit',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  });
}

/** Human age: "5 min", "2.5 h", "3 d". */
export function ageHuman(minutes: number): string {
  if (minutes < 0) return '0 min';
  if (minutes < 60) return `${Math.round(minutes)} min`;
  if (minutes < 1440) return `${(minutes / 60).toFixed(1)} h`;
  return `${(minutes / 1440).toFixed(1)} d`;
}

/** Verdict from a case fixture is lowercase ("supported"); normalise it. */
export function normaliseVerdict(v: string | undefined | null): string {
  return (v ?? '').toUpperCase();
}

/** True when the investigation verdict matches the case's expected verdict. */
export function verdictMatches(investigation: { verdict: string }, expected: string): boolean {
  return normaliseVerdict(investigation.verdict) === normaliseVerdict(expected);
}

/**
 * Local datetime string for <input type="datetime-local">.
 * The backend and the decay engine both work in naive ISO (no timezone), and
 * the fixtures use "2026-09-18T14:55:00" — so we format the same way.
 */
export function toLocalInput(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, '0');
  return (
    `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}` +
    `T${pad(date.getHours())}:${pad(date.getMinutes())}`
  );
}

/** Ensure an ISO timestamp has seconds, since the backend compares strings. */
export function withSeconds(iso: string): string {
  if (!iso) return iso;
  return iso.length === 16 ? `${iso}:00` : iso;
}
