/**
 * TRUTHLINE — Fixture detail
 * ==========================================================================
 * Drill-down for one labelled fixture (A–E). Shows the same pipeline readout as
 * the Analysis page, but over the deterministic fixture rather than live data.
 */

import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { errorMessage, investigate } from '../api';
import type { Investigation } from '../types';
import Radar from '../components/Radar';
import PipelineStrip from '../components/PipelineStrip';
import {
  Empty,
  ErrorBanner,
  FreshnessChip,
  Loading,
  Metric,
  Section,
  SourceChip,
} from '../components/ui';
import {
  ageHuman,
  clockTime,
  pct,
  relationMeta,
  scoreColor,
  verdictMeta,
} from '../utils';
import '../components/components.css';

export default function CaseDetail() {
  const { id = '' } = useParams();
  const [result, setResult] = useState<Investigation | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setResult(await investigate({ case_id: id }));
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  const blips = useMemo(
    () =>
      result?.claims.map((c) => ({
        id: c.id,
        label: `${c.source} · ${c.location}`,
        severity: c.freshness_score,
        band: c.freshness_label,
      })) ?? [],
    [result],
  );

  const meta = result ? verdictMeta(result.verdict) : null;

  return (
    <div className="page">
      <header className="page__header">
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
          <Link to="/validation" className="button button--sm">
            ← Validation
          </Link>
          <h1 className="page__title">Fixture {id}</h1>
        </div>
        <p className="page__subtitle">
          {result
            ? `${result.case_name} · ${result.summary.total_claims} claims · ${result.summary.total_contradictions} contradictions`
            : 'Loading…'}
        </p>
      </header>

      {error ? <ErrorBanner message={error} onRetry={load} /> : null}
      {loading && !result ? <Loading label="Running pipeline" /> : null}

      {result ? (
        <>
          <section
            className="verdict-hero"
            style={{ borderLeftColor: meta?.color, marginBottom: '0.85rem' }}
          >
            <div className="verdict-hero__label">
              Verdict
              {result.summary.expected_verdict ? (
                <span className="faint" style={{ marginLeft: '0.6rem', textTransform: 'none', letterSpacing: 0 }}>
                  expected {String(result.summary.expected_verdict).toUpperCase()}
                </span>
              ) : null}
            </div>
            <div className="verdict-hero__value" style={{ color: meta?.color }}>
              {meta?.label}
            </div>
            <p className="verdict-hero__rationale">{result.rationale}</p>
            <div className="stat-strip" style={{ marginTop: '0.7rem' }}>
              <span>clock <b>{result.summary.scenario_time}</b></span>
              <span>avg freshness <b>{pct(result.summary.avg_freshness, 1)}</b></span>
              <span>locations <b>{result.summary.locations_checked}</b></span>
            </div>
          </section>

          <div className="grid grid--metrics" style={{ marginBottom: '0.85rem' }}>
            <Metric label="Claims" value={result.summary.total_claims} />
            <Metric
              label="Contradictions"
              value={result.summary.total_contradictions}
              accent="var(--v-conflicting)"
            />
            <Metric label="Stale" value={result.summary.stale_count} accent="var(--v-stale)" />
            <Metric label="Gaps" value={result.summary.total_gaps} accent="var(--v-uncertain)" />
          </div>

          <Section title="Pipeline run" subtitle="The six agents, in execution order.">
            <PipelineStrip
              claims={result.claims.length}
              relations={result.summary.total_relations}
              stale={result.summary.stale_count}
              gaps={result.summary.total_gaps}
              verdict={result.verdict}
            />
          </Section>

          <div className="grid grid--2" style={{ marginBottom: '0.85rem' }}>
            <Section title="Source scope" subtitle="One blip per claim · radius = freshness">
              <Radar blips={blips} size={280} />
            </Section>

            <Section title="Freshness decay" subtitle="exp(-age/τ) computed in code.">
              <div className="log scroll-y" style={{ maxHeight: 320 }}>
                {result.claims.map((c) => (
                  <div className="log__row" key={c.id}>
                    <span className="log__time">{c.id}</span>
                    <span className="log__msg">
                      {c.source} · {c.location}
                      <span className="faint"> · age {ageHuman(c.age_minutes)}</span>
                    </span>
                    <span className="nowrap" style={{ color: scoreColor(c.freshness_score) }}>
                      {c.freshness_score.toFixed(3)}
                    </span>
                    <FreshnessChip label={c.freshness_label} />
                  </div>
                ))}
              </div>
            </Section>
          </div>

          <Section title="Claims" subtitle="Structured records, never paragraphs.">
            <div style={{ overflowX: 'auto' }}>
              <table className="tbl">
                <thead>
                  <tr>
                    <th>ID</th>
                    <th>Source</th>
                    <th>Zone</th>
                    <th>Observation</th>
                    <th>Time</th>
                    <th>Freshness</th>
                  </tr>
                </thead>
                <tbody>
                  {result.claims.map((c) => (
                    <tr key={c.id}>
                      <td className="mono" style={{ color: 'var(--neon)' }}>{c.id}</td>
                      <td>
                        <SourceChip type={c.source_type} />
                        <div className="faint" style={{ fontSize: '0.64rem', marginTop: '0.15rem' }}>
                          {c.source}
                        </div>
                      </td>
                      <td className="nowrap">{c.location}</td>
                      <td>{c.event}</td>
                      <td className="nowrap">{clockTime(c.timestamp)}</td>
                      <td>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem' }}>
                          <div className="fbar" style={{ width: 50 }}>
                            <div
                              className="fbar__fill"
                              style={{
                                width: `${c.freshness_score * 100}%`,
                                background: scoreColor(c.freshness_score),
                              }}
                            />
                          </div>
                          <FreshnessChip label={c.freshness_label} />
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Section>

          <Section
            title="Relations"
            subtitle={`${result.summary.total_contradictions} contradictions · ${result.summary.total_supports} supports`}
          >
            {result.relations.length ? (
              <div style={{ overflowX: 'auto' }}>
                <table className="tbl">
                  <thead>
                    <tr>
                      <th>A</th>
                      <th>B</th>
                      <th>Relation</th>
                      <th>Conf</th>
                      <th>Reason</th>
                      <th>By</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.relations.map((r, i) => {
                      const m = relationMeta(r.relation_type);
                      return (
                        <tr key={`${r.claim_a}-${r.claim_b}-${i}`}>
                          <td className="mono" style={{ color: 'var(--neon)' }}>{r.claim_a}</td>
                          <td className="mono" style={{ color: 'var(--neon)' }}>{r.claim_b}</td>
                          <td>
                            <span className="chip" style={{ color: m.color }}>{m.label}</span>
                          </td>
                          <td>
                            {r.confidence == null ? (
                              <span
                                className="faint"
                                title="Rule-matched on differing wording; no LLM classifier configured to score it."
                              >
                                unverified
                              </span>
                            ) : (
                              r.confidence.toFixed(2)
                            )}
                          </td>
                          <td>{r.reason}</td>
                          <td>
                            <span
                              className="chip"
                              style={{
                                color:
                                  r.classified_by === 'llm'
                                    ? 'var(--v-updated)'
                                    : 'var(--text-muted)',
                              }}
                            >
                              {r.classified_by}
                            </span>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            ) : (
              <Empty message="No relations detected" />
            )}
          </Section>

          <Section title="Evidence gaps" subtitle="What the evidence is missing.">
            {result.gaps.length ? (
              <div className="log">
                {result.gaps.map((g, i) => (
                  <div className="log__row" key={`${g.claim_id}-${g.missing_attribute}-${i}`}>
                    <span
                      className="log__time"
                      style={{
                        color:
                          g.severity === 'high'
                            ? 'var(--v-conflicting)'
                            : g.severity === 'medium'
                              ? 'var(--v-stale)'
                              : 'var(--text-muted)',
                      }}
                    >
                      {g.severity.toUpperCase()}
                    </span>
                    <span className="log__msg">
                      <b style={{ color: 'var(--text-strong)' }}>{g.location}</b> ·{' '}
                      {g.missing_attribute} — {g.suggested_verification}
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <Empty message="No evidence gaps" />
            )}
          </Section>
        </>
      ) : null}
    </div>
  );
}
