/**
 * TRUTHLINE — Analysis
 * ==========================================================================
 * The full pipeline readout over the operator's OWN reports: verdict, signals,
 * the six agents, decay maths, claims, relations, gaps and the evidence trail.
 *
 * Nothing here is fixture data. If the board is empty, it says so.
 */

import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { errorMessage, investigateArea } from '../api';
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

export default function Analysis() {
  const [result, setResult] = useState<Investigation | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchParams] = useSearchParams();
  const zone = searchParams.get('zone');

  const load = useCallback(
    async (zoneToLoad?: string) => {
      setLoading(true);
      setError(null);
      try {
        const r = await investigateArea(undefined, zoneToLoad);
        setResult(r);
      } catch (e) {
        setError(errorMessage(e));
      } finally {
        setLoading(false);
      }
    },
    [],
  );

  const handleLoad = useCallback(() => {
    load(zone ?? undefined);
  }, [load, zone]);

  useEffect(() => {
    load(zone ?? undefined);
  }, [load, zone]);

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
  const hasData = (result?.claims.length ?? 0) > 0;

  return (
    <div className="page">
      <header className="page__header">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '1rem', flexWrap: 'wrap' }}>
          <div>
            <h1 className="page__title">Analysis</h1>
            <p className="page__subtitle">
              Full pipeline readout over the reports on the board.
            </p>
          </div>
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <Link className="button button--sm" to="/">
              ← Console
            </Link>
            <button className="button button--sm" onClick={handleLoad} disabled={loading}>
              Re-run
            </button>
          </div>
        </div>
      </header>

      {error ? <ErrorBanner message={error} onRetry={load} /> : null}
      {loading && !result ? <Loading label="Running pipeline… may take up to 2 min with LLM classification" /> : null}

      {result && !hasData ? (
        <section className="panel">
          <Empty
            message="No evidence on the board"
            hint="Go to the Console, log a few field reports, then come back."
          />
          <div style={{ textAlign: 'center' }}>
            <Link className="button button--solid" to="/">
              Open console
            </Link>
          </div>
        </section>
      ) : null}

      {result && hasData ? (
        <>
          {/* ── Verdict ─────────────────────────────────────────────────── */}
          <section
            className="verdict-hero"
            style={{ borderLeftColor: meta?.color, marginBottom: '0.85rem' }}
          >
            <div className="verdict-hero__label">Verdict</div>
            <div className="verdict-hero__value" style={{ color: meta?.color }}>
              {meta?.label}
            </div>
            <p className="verdict-hero__rationale">{result.rationale}</p>
            <div className="stat-strip" style={{ marginTop: '0.7rem' }}>
              <span>clock <b>{result.summary.scenario_time}</b></span>
              <span>claims <b>{result.summary.total_claims}</b></span>
              <span>locations <b>{result.summary.locations_checked}</b></span>
              <span>avg freshness <b>{pct(result.summary.avg_freshness, 1)}</b></span>
            </div>
          </section>

          {/* ── Signals ─────────────────────────────────────────────────── */}
          <div className="grid grid--metrics" style={{ marginBottom: '0.85rem' }}>
            <Metric label="Claims" value={result.summary.total_claims} />
            <Metric
              label="Contradictions"
              value={result.summary.total_contradictions}
              accent="var(--v-conflicting)"
            />
            <Metric label="Supports" value={result.summary.total_supports} accent="var(--v-supported)" />
            <Metric label="Stale" value={result.summary.stale_count} accent="var(--v-stale)" />
            <Metric label="Gaps" value={result.summary.total_gaps} accent="var(--v-uncertain)" />
            <Metric
              label="Citation violations"
              value={result.citation_violations.length}
              accent={result.citation_violations.length ? 'var(--v-conflicting)' : 'var(--v-supported)'}
            />
          </div>

          {/* ── Pipeline ────────────────────────────────────────────────── */}
          <Section title="Pipeline run" subtitle="The six agents, in execution order.">
            <PipelineStrip
              claims={result.claims.length}
              relations={result.summary.total_relations}
              stale={result.summary.stale_count}
              gaps={result.summary.total_gaps}
              verdict={result.verdict}
            />
          </Section>

          {/* ── Radar + decay ───────────────────────────────────────────── */}
          <div className="grid grid--2" style={{ marginBottom: '0.85rem' }}>
            <Section title="Source scope" subtitle="One blip per claim · radius = freshness">
              <Radar blips={blips} size={290} />
            </Section>

            <Section
              title="Freshness decay"
              subtitle="exp(-age/τ) computed in code, never by the model."
            >
              <div className="log scroll-y" style={{ maxHeight: 330 }}>
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
              <p className="section__sub" style={{ marginTop: '0.6rem' }}>
                τ · drone 5m · ground 15m · satellite 30m · intel 1440m · stale below 0.10
              </p>
            </Section>
          </div>

          {/* ── Claims ──────────────────────────────────────────────────── */}
          <Section title="Extracted claims" subtitle="Structured records, never paragraphs.">
            <div style={{ overflowX: 'auto' }}>
              <table className="tbl">
                <thead>
                  <tr>
                    <th>ID</th>
                    <th>Source</th>
                    <th>Zone</th>
                    <th>Observation</th>
                    <th>Time</th>
                    <th>Age</th>
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
                      <td className="nowrap">{ageHuman(c.age_minutes)}</td>
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

          {/* ── Relations ───────────────────────────────────────────────── */}
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
                            <span className="chip" style={{ color: m.color }}>
                              {m.label}
                            </span>
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
              <Empty message="No relations detected" hint="Every claim stands alone." />
            )}
          </Section>

          {/* ── Gaps ────────────────────────────────────────────────────── */}
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
              <Empty message="No evidence gaps" hint="Every claim has the corroboration it needs." />
            )}
          </Section>

          {/* ── Evidence trail ──────────────────────────────────────────── */}
          <Section title="Evidence trail" subtitle="Sources the judge was permitted to cite.">
            {result.evidence_ids.length ? (
              <div className="card__foot" style={{ marginTop: 0 }}>
                {result.evidence_ids.map((eid) => (
                  <span
                    className="chip"
                    key={eid}
                    style={{ color: 'var(--neon)' }}
                  >
                    {eid}
                  </span>
                ))}
              </div>
            ) : (
              <Empty message="No evidence cited" />
            )}

            {result.citation_violations.length ? (
              <div className="banner banner--warn" style={{ marginTop: '0.75rem', marginBottom: 0 }}>
                <span>
                  {result.citation_violations.length} citation violation(s) stripped — the judge
                  cited sources that were not retrieved.
                </span>
              </div>
            ) : (
              <p className="section__sub" style={{ marginTop: '0.75rem', marginBottom: 0 }}>
                ✓ No citation violations — every cited source was in the retrieved set.
              </p>
            )}
          </Section>
        </>
      ) : null}
    </div>
  );
}
