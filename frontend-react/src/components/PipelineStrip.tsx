/**
 * TRUTHLINE — the 6-agent pipeline strip
 * ==========================================================================
 * Shows INGEST -> EXTRACT -> CONTRADICT -> DECAY -> GAPS -> JUDGE with live
 * counts from the investigation result. This is the "what just ran" readout.
 */

import './components.css';

const STEPS = [
  { key: 'ingest', name: 'INGEST', label: 'Sources' },
  { key: 'extract', name: 'EXTRACT', label: 'Claims' },
  { key: 'contradict', name: 'CONTRADICT', label: 'Pairs' },
  { key: 'decay', name: 'DECAY', label: 'Scored' },
  { key: 'gaps', name: 'GAPS', label: 'Flagged' },
  { key: 'judge', name: 'JUDGE', label: 'Verdict' },
] as const;

interface PipelineStripProps {
  claims: number;
  relations: number;
  stale: number;
  gaps: number;
  verdict?: string;
}

export default function PipelineStrip({
  claims,
  relations,
  stale,
  gaps,
  verdict,
}: PipelineStripProps) {
  const meta: Record<string, string> = {
    ingest: '—',
    extract: String(claims),
    contradict: String(relations),
    decay: `${stale} stale`,
    gaps: String(gaps),
    judge: verdict ?? '—',
  };

  return (
    <div className="pipeline" role="list" aria-label="Pipeline stages">
      {STEPS.map((s, i) => (
        <div className="pipeline__step" role="listitem" key={s.key}>
          <div className="pipeline__num">{i + 1}</div>
          <div className="pipeline__name">{s.name}</div>
          <div className="pipeline__meta">
            {s.label}: <strong>{meta[s.key]}</strong>
          </div>
        </div>
      ))}
    </div>
  );
}
