/**
 * TRUTHLINE — Validation
 * ==========================================================================
 * The five labelled fixtures (A–E) used to prove the pipeline is correct:
 * SUPPORTED, CONFLICTING, STALE, UNCERTAIN, UPDATED.
 *
 * This is deliberately NOT the main workflow any more. The Console runs on
 * real operator-entered reports; this page exists so you can show the engine
 * is deterministic and reproducible.
 */

import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { errorMessage, fetchCases, investigate } from '../api';
import type { CaseSummary, Investigation } from '../types';
import { ErrorBanner, Loading, VerdictBadge } from '../components/ui';
import { pct, verdictMeta } from '../utils';
import '../components/components.css';

export default function Validation() {
  const [cases, setCases] = useState<CaseSummary[] | null>(null);
  const [results, setResults] = useState<Record<string, Investigation>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const { cases: c } = await fetchCases();
      setCases(c);
      const entries = await Promise.all(
        c.map(async (cs) => {
          const r = await investigate({ case_id: cs.case_id });
          return [cs.case_id, r] as const;
        }),
      );
      setResults(Object.fromEntries(entries));
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const rows = useMemo(
    () =>
      cases?.map((c) => {
        const r = results[c.case_id];
        const expected = (c.expected_verdict ?? '').toUpperCase();
        const actual = r?.verdict ?? '';
        return {
          ...c,
          result: r,
          expected,
          actual,
          match: r ? actual.toUpperCase() === expected : null,
        };
      }) ?? [],
    [cases, results],
  );

  const passCount = rows.filter((r) => r.match === true).length;

  return (
    <div className="page">
      <header className="page__header">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '1rem', flexWrap: 'wrap' }}>
          <div>
            <h1 className="page__title">Validation</h1>
            <p className="page__subtitle">
              Labelled fixtures proving the pipeline is deterministic. Not the operational
              workflow — that lives in the Console.
            </p>
          </div>
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <Link className="button button--sm" to="/">
              ← Console
            </Link>
            <button className="button button--sm" onClick={load} disabled={loading}>
              Re-run suite
            </button>
          </div>
        </div>
      </header>

      {error ? <ErrorBanner message={error} onRetry={load} /> : null}

      <div className="grid grid--metrics" style={{ marginBottom: '0.85rem' }}>
        <div className="metric">
          <div className="metric__value">{rows.length}</div>
          <div className="metric__label">Fixtures</div>
        </div>
        <div className="metric" style={{ borderLeftColor: 'var(--v-supported)' }}>
          <div className="metric__value">{passCount}</div>
          <div className="metric__label">Correct</div>
        </div>
        <div className="metric" style={{ borderLeftColor: 'var(--v-conflicting)' }}>
          <div className="metric__value">{rows.length - passCount}</div>
          <div className="metric__label">Mismatches</div>
        </div>
        <div className="metric" style={{ borderLeftColor: 'var(--neon)' }}>
          <div className="metric__value">
            {rows.length ? `${passCount}/${rows.length}` : '—'}
          </div>
          <div className="metric__label">Gate</div>
          <div className="metric__hint">
            {passCount === rows.length && rows.length > 0 ? 'PASS' : 'PENDING'}
          </div>
        </div>
      </div>

      {loading && !cases ? (
        <Loading label="Loading fixtures" />
      ) : (
        <section className="panel">
          <h3 className="panel__title">Operation NORTHSTAR — labelled fixtures</h3>
          <div style={{ overflowX: 'auto' }}>
            <table className="tbl">
              <thead>
                <tr>
                  <th>Case</th>
                  <th>Name</th>
                  <th>Reports</th>
                  <th>Claims</th>
                  <th>Conflicts</th>
                  <th>Gaps</th>
                  <th>Avg fresh</th>
                  <th>Expected</th>
                  <th>Actual</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.case_id}>
                    <td className="mono" style={{ color: 'var(--neon)' }}>{r.case_id}</td>
                    <td>{r.name}</td>
                    <td>{r.report_count}</td>
                    <td>{r.result?.claims.length ?? '—'}</td>
                    <td>{r.result?.summary.total_contradictions ?? '—'}</td>
                    <td>{r.result?.summary.total_gaps ?? '—'}</td>
                    <td>{r.result ? pct(r.result.summary.avg_freshness, 1) : '—'}</td>
                    <td>
                      <span
                        className="chip"
                        style={{ color: verdictMeta(r.expected).color }}
                      >
                        {r.expected}
                      </span>
                    </td>
                    <td>
                      {r.result ? (
                        <VerdictBadge verdict={r.result.verdict} />
                      ) : (
                        <span className="faint">…</span>
                      )}
                    </td>
                    <td>
                      <Link className="button button--sm" to={`/case/${r.case_id}`}>
                        Inspect
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  );
}
