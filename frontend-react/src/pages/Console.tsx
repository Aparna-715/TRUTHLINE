/**
 * TRUTHLINE — Field Console
 * ==========================================================================
 * The primary workspace. Not a demo: the operator provisions an area (zones +
 * equipment), then feeds real reports in and runs the pipeline over them.
 *
 * Layout (three columns, all embedded — no tabs):
 *
 *   ROSTER            AREA / ZONES / SCOPE        ENTRY + FEED
 *   equipment list    zone grid + radar           report form + live feed
 *
 * The scenario clock is an offset from *now*, so advancing it decays the
 * operator's own evidence rather than a fixture's.
 */

import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  createReport,
  deleteReport,
  errorMessage,
  fetchArea,
  investigateArea,
  seedArea,
  createZone,
  deleteZone,
  createEquipment,
  deleteEquipment,
} from '../api';
import type { AreaResponse, Equipment, Investigation, Report } from '../types';
import Radar from '../components/Radar';
import {
  Empty,
  ErrorBanner,
  FreshnessChip,
  Loading,
  Metric,
  SourceChip,
  VerdictBadge,
} from '../components/ui';
import {
  ageHuman,
  clockTime,
  pct,
  scoreColor,
  sourceGlyph,
  sourceMeta,
  threatMeta,
  toLocalInput,
  withSeconds,
} from '../utils';
import '../components/components.css';

/** Clock offset in minutes from now. Negative = past, positive = future. */
const CLOCK_MIN = -120;
const CLOCK_MAX = 720;
const CLOCK_STEP = 15;

function scenarioFrom(offsetMinutes: number): string {
  const d = new Date(Date.now() + offsetMinutes * 60_000);
  // Naive local ISO, matching the fixtures' format ("2026-09-18T14:55:00").
  return toLocalInput(d) + ':00';
}

export default function Console() {
  const [data, setData] = useState<AreaResponse | null>(null);
  const [result, setResult] = useState<Investigation | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [offset, setOffset] = useState(0);
  const [zoneFilter, setZoneFilter] = useState<string | null>(null);
  const [selectedEquipment, setSelectedEquipment] = useState<string>('');

  // ── Manage area: zone / equipment provisioning ────────────────────────
  const [showManage, setShowManage] = useState(false);
  const [zoneForm, setZoneForm] = useState({ name: '', description: '', threat: 'low' });
  const [equipForm, setEquipForm] = useState({ name: '', source_type: 'drone', zone_id: '', status: 'online' });
  const [manageError, setManageError] = useState<string | null>(null);

  // Report form
  const [formZone, setFormZone] = useState('');
  const [formText, setFormText] = useState('');
  const [formTime, setFormTime] = useState(toLocalInput(new Date()));
  const [formError, setFormError] = useState<string | null>(null);

  const scenarioTime = useMemo(() => scenarioFrom(offset), [offset]);

  // ── Load ────────────────────────────────────────────────────────────────
  const load = useCallback(
    async (clock: string) => {
      setLoading(true);
      setError(null);
      try {
        const d = await fetchArea(clock);
        setData(d);
        if (!formZone && d.zones.length) setFormZone(d.zones[0].name);
        if (!selectedEquipment && d.equipment.length) {
          setSelectedEquipment(d.equipment[0].equipment_id);
        }
        // Populate the verdict straight away so the console never opens on a
        // blank readout when there is already evidence on the board.
        if (d.report_count > 0) {
          try {
            setResult(await investigateArea(clock));
          } catch {
            /* the verdict panel degrades to "not run yet"; the board still shows */
          }
        }
      } catch (e) {
        setError(errorMessage(e));
      } finally {
        setLoading(false);
      }
    },
    // formZone / selectedEquipment intentionally excluded: this is an initial load
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [],
  );

  useEffect(() => {
    load(scenarioTime);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const refresh = useCallback(async () => {
    try {
      const d = await fetchArea(scenarioTime);
      setData(d);
    } catch (e) {
      setError(errorMessage(e));
    }
  }, [scenarioTime]);

  // ── Actions ─────────────────────────────────────────────────────────────
  const provision = async () => {
    setBusy(true);
    setError(null);
    try {
      await seedArea();
      await load(scenarioTime);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  const runAnalysis = async () => {
    setBusy(true);
    setError(null);
    try {
      const r = await investigateArea(scenarioTime, zoneFilter ?? undefined);
      setResult(r);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  const submitReport = async () => {
    setFormError(null);
    if (!formText.trim()) {
      setFormError('Report body cannot be empty.');
      return;
    }
    if (!formZone) {
      setFormError('Pick a zone first.');
      return;
    }
    setBusy(true);
    try {
      await createReport({
        text: formText.trim(),
        zone: formZone,
        equipment_id: selectedEquipment || null,
        timestamp: withSeconds(formTime),
      });
      setFormText('');
      setFormTime(toLocalInput(new Date()));
      // Auto-scope the filter to the zone just logged, so the next analysis
      // run shows only that zone's evidence.
      setZoneFilter(formZone);
      await refresh();
      // Re-run automatically so the verdict tracks the new evidence.
      const r = await investigateArea(scenarioTime, formZone ?? undefined);
      setResult(r);
    } catch (e) {
      setFormError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  const removeReport = async (id: string) => {
    setBusy(true);
    try {
      await deleteReport(id);
      await refresh();
      const r = await investigateArea(scenarioTime, zoneFilter ?? undefined);
      setResult(r);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  // ── Manage area: zone / equipment provisioning ────────────────────────
  const addZone = async () => {
    setManageError(null);
    if (!zoneForm.name.trim()) {
      setManageError('Zone name is required.');
      return;
    }
    setBusy(true);
    try {
      await createZone({ name: zoneForm.name.trim(), description: zoneForm.description.trim() || undefined, threat: zoneForm.threat });
      setZoneForm({ name: '', description: '', threat: 'low' });
      await refresh();
      const r = await investigateArea(scenarioTime, zoneFilter ?? undefined);
      setResult(r);
    } catch (e) {
      setManageError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  const deleteZoneById = async (zoneId: string) => {
    setBusy(true);
    try {
      await deleteZone(zoneId);
      await refresh();
      const r = await investigateArea(scenarioTime, zoneFilter ?? undefined);
      setResult(r);
    } catch (e) {
      setManageError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  const addEquipment = async () => {
    setManageError(null);
    if (!equipForm.name.trim()) {
      setManageError('Equipment name is required.');
      return;
    }
    if (!equipForm.source_type) {
      setManageError('Source type is required.');
      return;
    }
    setBusy(true);
    try {
      await createEquipment({
        name: equipForm.name.trim(),
        source_type: equipForm.source_type,
        zone_id: equipForm.zone_id || null,
        status: equipForm.status,
      });
      setEquipForm({ name: '', source_type: 'drone', zone_id: '', status: 'online' });
      await refresh();
      const r = await investigateArea(scenarioTime, zoneFilter ?? undefined);
      setResult(r);
    } catch (e) {
      setManageError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  const deleteEquipmentById = async (equipmentId: string) => {
    setBusy(true);
    try {
      await deleteEquipment(equipmentId);
      await refresh();
      const r = await investigateArea(scenarioTime, zoneFilter ?? undefined);
      setResult(r);
    } catch (e) {
      setManageError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  // ── Derived ─────────────────────────────────────────────────────────────
  const reports = useMemo(() => {
    const all = data?.reports ?? [];
    const filtered = zoneFilter ? all.filter((r) => r.location === zoneFilter) : all;
    return [...filtered].sort((a, b) => (b.timestamp || '').localeCompare(a.timestamp || ''));
  }, [data, zoneFilter]);

  const blips = useMemo(() => {
    if (!result) return [];
    return result.claims.map((c) => ({
      id: c.id,
      label: `${c.source} · ${c.location}`,
      severity: c.freshness_score,
      band: c.freshness_label,
    }));
  }, [result]);

  const equipmentOnline = (data?.equipment ?? []).filter(
    (e) => (e.status || 'online') !== 'offline',
  ).length;

  const zones = data?.zones ?? [];
  const provisioned = zones.length > 0 || (data?.equipment.length ?? 0) > 0;

  const activeEquipment: Equipment | undefined = data?.equipment.find(
    (e) => e.equipment_id === selectedEquipment,
  );

  // ── Render ──────────────────────────────────────────────────────────────
  return (
    <div className="page">
      {/* ── Area header ─────────────────────────────────────────────────── */}
      <header className="hero">
        <div style={{ minWidth: 0 }}>
          <h1 className="hero__title">
            {data?.area?.name ?? 'No area provisioned'}
            <span className="caret" />
          </h1>
          <p className="hero__sub">
            {data?.area?.designation ?? 'Define an operational area, attach equipment, then feed reports in.'}
          </p>
          <div className="hero__badges">
            <span className="chip" style={{ color: 'var(--neon)' }}>
              {data?.report_count ?? 0} reports
            </span>
            <span className="chip" style={{ color: 'var(--s-drone)' }}>
              {zones.length} zones
            </span>
            <span className="chip" style={{ color: 'var(--s-ground)' }}>
              {equipmentOnline}/{data?.equipment.length ?? 0} equipment online
            </span>
            {zoneFilter ? (
              <span
                className="chip"
                style={{ color: 'var(--v-stale)', cursor: 'pointer' }}
                onClick={() => setZoneFilter(null)}
                title="Clear zone filter"
              >
                scope: {zoneFilter} ✕
              </span>
            ) : (
              <span className="chip" style={{ color: 'var(--text-muted)' }}>
                scope: whole area
              </span>
            )}
          </div>
        </div>

        <div className="hero__right">
          <div style={{ textAlign: 'right' }}>
            <div className="field__label">Scenario clock</div>
            <div className="mono" style={{ color: 'var(--neon)', fontWeight: 700 }}>
              {clockTime(scenarioTime)}
              <span className="faint" style={{ marginLeft: 6, fontSize: '0.7rem' }}>
                {offset === 0 ? 'now' : `${offset > 0 ? '+' : ''}${offset}m`}
              </span>
            </div>
          </div>
          <button className="button button--solid" onClick={runAnalysis} disabled={busy}>
            {busy ? 'Working…' : 'Run analysis'}
          </button>
        </div>
      </header>

      {error ? <ErrorBanner message={error} onRetry={() => load(scenarioTime)} /> : null}

      {/* ── Not provisioned yet ─────────────────────────────────────────── */}
      {!loading && !provisioned ? (
        <section className="panel" style={{ textAlign: 'center', padding: '2.5rem 1rem' }}>
          <div style={{ fontSize: '1.6rem', color: 'var(--neon)', marginBottom: '0.5rem' }}>◈</div>
          <h3 style={{ fontSize: '0.95rem', letterSpacing: '0.08em' }}>AREA NOT PROVISIONED</h3>
          <p className="section__sub" style={{ maxWidth: '58ch', margin: '0.5rem auto 1rem' }}>
            Provision the default area to get five zones and a five-piece equipment roster.
            This creates structure only — no sample observations. Every report on the board
            will be one you entered.
          </p>
          <button className="button button--solid" onClick={provision} disabled={busy}>
            Provision area
          </button>
        </section>
      ) : null}

      {provisioned ? (
        <>
          {/* ── Metrics ─────────────────────────────────────────────────── */}
          <div className="grid grid--metrics" style={{ marginBottom: '0.85rem' }}>
            <Metric label="Reports on board" value={data?.report_count ?? 0} />
            <Metric label="Zones" value={zones.length} />
            <Metric
              label="Equipment online"
              value={`${equipmentOnline}/${data?.equipment.length ?? 0}`}
              accent="var(--s-ground)"
            />
            <Metric
              label="Verdict"
              value={result ? <VerdictBadge verdict={result.verdict} /> : '—'}
              hint={result ? `${result.summary.total_claims} claims` : 'not run yet'}
            />
          </div>

          {/* ── Three-column console ────────────────────────────────────── */}
          <div className="grid grid--console" style={{ marginBottom: '0.85rem' }}>
            {/* ROSTER */}
            <section className="panel">
              <div className="section__head">
                <div>
                  <h3 className="panel__title" style={{ marginBottom: 0 }}>Equipment</h3>
                  <p className="section__sub">Pick an item to attribute a report.</p>
                </div>
                <button
                  className="button button--sm"
                  onClick={() => setShowManage((v) => !v)}
                  title={showManage ? 'Hide management' : 'Manage zones & equipment'}
                >
                  {showManage ? 'Hide' : 'Manage area'}
                </button>
              </div>
              {data?.equipment.length ? (
                <div className="roster">
                  {data.equipment.map((e) => {
                    const meta = sourceMeta(e.source_type);
                    const active = e.equipment_id === selectedEquipment;
                    const online = (e.status || 'online') !== 'offline';
                    return (
                      <div
                        key={e.equipment_id}
                        className={`roster__item${active ? ' roster__item--active' : ''}`}
                        onClick={() => setSelectedEquipment(e.equipment_id)}
                      >
                        <span className="roster__glyph" style={{ color: meta.color }}>
                          {sourceGlyph(e.source_type)}
                        </span>
                        <div style={{ minWidth: 0, flex: 1 }}>
                          <div className="roster__name">{e.name}</div>
                          <div className="roster__meta">
                            {e.source_type}
                            {e.zone_id ? ` · ${e.zone_id}` : ''}
                          </div>
                        </div>
                        <span className={`dot ${online ? 'dot--ok' : 'dot--err'}`} />
                      </div>
                    );
                  })}
                </div>
              ) : (
                <Empty message="No equipment" />
              )}

              <hr className="divider" />

              <h3 className="panel__title">Clock offset</h3>
              <div className="slider-row">
                <input
                  className="slider"
                  type="range"
                  min={CLOCK_MIN}
                  max={CLOCK_MAX}
                  step={CLOCK_STEP}
                  value={offset}
                  onChange={(e) => setOffset(Number(e.target.value))}
                  aria-label="Scenario clock offset in minutes"
                />
                <span className="slider__value">
                  {offset > 0 ? '+' : ''}
                  {offset}m
                </span>
              </div>
              <p className="section__sub" style={{ marginTop: '0.5rem' }}>
                Advance to decay your own evidence. Then re-run analysis.
              </p>
            </section>

            {/* ── MANAGE AREA (zones / equipment) ─────────────────────────── */}
            {showManage ? (
              <section className="panel" style={{ marginBottom: '0.85rem' }}>
                <div className="section__head">
                  <div>
                    <h3 className="panel__title" style={{ marginBottom: 0 }}>Manage area</h3>
                    <p className="section__sub">Add or remove zones and equipment.</p>
                  </div>
                  <button className="button button--ghost button--sm" onClick={() => setShowManage(false)}>
                    Close
                  </button>
                </div>
                {manageError ? (
                  <div className="banner banner--err" style={{ marginBottom: '0.6rem' }}>
                    <span>{manageError}</span>
                  </div>
                ) : null}

                {/* Zones */}
                <div className="card" style={{ marginBottom: '0.75rem' }}>
                  <div className="card__head">
                    <div className="card__title">Zones</div>
                    <span className="card__body" style={{ fontSize: '0.62rem' }}>{zones.length} defined</span>
                  </div>
                  <div className="card__body" style={{ display: 'grid', gap: '0.4rem', marginTop: '0.4rem' }}>
                    {zones.map((z) => (
                      <div key={z.zone_id} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '0.5rem', padding: '0.35rem 0.5rem', background: 'var(--inset)', border: '1px solid var(--line)', borderRadius: 'var(--radius)' }}>
                        <div style={{ minWidth: 0, flex: 1 }}>
                          <div style={{ fontWeight: 600, color: 'var(--text)' }}>{z.name}</div>
                          <div className="faint" style={{ fontSize: '0.58rem' }}>{z.description ?? ''}</div>
                        </div>
                        <button
                          className="button button--danger button--sm"
                          onClick={() => deleteZoneById(z.zone_id)}
                          disabled={busy}
                          title="Delete zone"
                        >
                          ✕
                        </button>
                      </div>
                    ))}
                    {!zones.length ? <Empty message="No zones" /> : null}
                  </div>
                </div>

                {/* Add zone form */}
                <div className="card" style={{ marginBottom: '0.75rem' }}>
                  <div className="card__head">
                    <div className="card__title">Add zone</div>
                  </div>
                  <div className="card__body" style={{ display: 'grid', gap: '0.4rem', marginTop: '0.4rem' }}>
                    <div className="field">
                      <label className="field__label">Name</label>
                      <input
                        className="input"
                        value={zoneForm.name}
                        onChange={(e) => setZoneForm((v) => ({ ...v, name: e.target.value }))}
                        placeholder="Grid-4"
                      />
                    </div>
                    <div className="field">
                      <label className="field__label">Description</label>
                      <input
                        className="input"
                        value={zoneForm.description}
                        onChange={(e) => setZoneForm((v) => ({ ...v, description: e.target.value }))}
                        placeholder="Description"
                      />
                    </div>
                    <div className="field">
                      <label className="field__label">Threat</label>
                      <select
                        className="select"
                        value={zoneForm.threat}
                        onChange={(e) => setZoneForm((v) => ({ ...v, threat: e.target.value }))}
                      >
                        <option value="low">Low</option>
                        <option value="elevated">Elevated</option>
                        <option value="high">High</option>
                      </select>
                    </div>
                    <button className="button button--solid" onClick={addZone} disabled={busy}>
                      {busy ? 'Adding…' : 'Add zone'}
                    </button>
                  </div>
                </div>

                {/* Equipment */}
                <div className="card" style={{ marginBottom: '0.75rem' }}>
                  <div className="card__head">
                    <div className="card__title">Equipment</div>
                    <span className="card__body" style={{ fontSize: '0.62rem' }}>{data?.equipment.length ?? 0} units</span>
                  </div>
                  <div className="card__body" style={{ display: 'grid', gap: '0.4rem', marginTop: '0.4rem' }}>
                    {data?.equipment.map((e) => (
                      <div key={e.equipment_id} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '0.5rem', padding: '0.35rem 0.5rem', background: 'var(--inset)', border: '1px solid var(--line)', borderRadius: 'var(--radius)' }}>
                        <div style={{ minWidth: 0, flex: 1 }}>
                          <div style={{ fontWeight: 600, color: 'var(--text)' }}>{e.name}</div>
                          <div className="faint" style={{ fontSize: '0.58rem' }}>{e.source_type} · {e.zone_id ?? 'no zone'}</div>
                        </div>
                        <button
                          className="button button--danger button--sm"
                          onClick={() => deleteEquipmentById(e.equipment_id)}
                          disabled={busy}
                          title="Delete equipment"
                        >
                          ✕
                        </button>
                      </div>
                    ))}
                    {!(data?.equipment.length ?? 0) ? <Empty message="No equipment" /> : null}
                  </div>
                </div>

                {/* Add equipment form */}
                <div className="card">
                  <div className="card__head">
                    <div className="card__title">Add equipment</div>
                  </div>
                  <div className="card__body" style={{ display: 'grid', gap: '0.4rem', marginTop: '0.4rem' }}>
                    <div className="field">
                      <label className="field__label">Name</label>
                      <input
                        className="input"
                        value={equipForm.name}
                        onChange={(e) => setEquipForm((v) => ({ ...v, name: e.target.value }))}
                        placeholder="Drone-Charlie"
                      />
                    </div>
                    <div className="field">
                      <label className="field__label">Source type</label>
                      <select
                        className="select"
                        value={equipForm.source_type}
                        onChange={(e) => setEquipForm((v) => ({ ...v, source_type: e.target.value }))}
                      >
                        <option value="drone">Drone</option>
                        <option value="ground">Ground</option>
                        <option value="satellite">Satellite</option>
                        <option value="intel">Intel</option>
                      </select>
                    </div>
                    <div className="field">
                      <label className="field__label">Zone</label>
                      <select
                        className="select"
                        value={equipForm.zone_id}
                        onChange={(e) => setEquipForm((v) => ({ ...v, zone_id: e.target.value }))}
                      >
                        <option value="">— unattributed —</option>
                        {zones.map((z) => (
                          <option key={z.zone_id} value={z.zone_id}>{z.name}</option>
                        ))}
                      </select>
                    </div>
                    <div className="field">
                      <label className="field__label">Status</label>
                      <select
                        className="select"
                        value={equipForm.status}
                        onChange={(e) => setEquipForm((v) => ({ ...v, status: e.target.value }))}
                      >
                        <option value="online">Online</option>
                        <option value="degraded">Degraded</option>
                        <option value="offline">Offline</option>
                      </select>
                    </div>
                    <button className="button button--solid" onClick={addEquipment} disabled={busy}>
                      {busy ? 'Adding…' : 'Add equipment'}
                    </button>
                  </div>
                </div>
              </section>
            ) : null}
            <div>
              <section className="panel" style={{ marginBottom: '0.85rem' }}>
                <div className="section__head">
                  <div>
                    <h3 className="panel__title" style={{ marginBottom: 0 }}>
                      Zones
                    </h3>
                    <p className="section__sub">Click a zone to scope the analysis to it.</p>
                  </div>
                  <button className="button button--sm" onClick={() => load(scenarioTime)}>
                    Refresh
                  </button>
                </div>

                <div className="zones">
                  {zones.map((z) => {
                    const t = threatMeta(z.threat);
                    const active = zoneFilter === z.name;
                    return (
                      <div
                        key={z.zone_id}
                        className={`zone${active ? ' zone--active' : ''}${z.report_count === 0 ? ' zone--empty' : ''}`}
                        style={{ borderTopColor: t.color }}
                        onClick={() => setZoneFilter(active ? null : z.name)}
                      >
                        <div className="zone__name">
                          <span>{z.name}</span>
                          <span className="chip" style={{ color: t.color, fontSize: '0.5rem' }}>
                            {t.label}
                          </span>
                        </div>
                        <div className="zone__desc" title={z.description ?? ''}>
                          {z.description ?? '—'}
                        </div>
                        <div className="zone__stats">
                          <span>
                            <span className="zone__count">{z.report_count}</span> reports
                          </span>
                          <span className="faint">·</span>
                          <span>{z.source_count} src</span>
                          <div className="fbar" style={{ flex: 1, minWidth: 26 }}>
                            <div
                              className="fbar__fill"
                              style={{
                                width: `${z.avg_freshness * 100}%`,
                                background: scoreColor(z.avg_freshness),
                              }}
                            />
                          </div>
                        </div>
                      </div>
                    );
                  })}
                  {!zones.length ? <Empty message="No zones defined" /> : null}
                </div>
              </section>
            </div>

            <div className="scope-row">
              <section className="panel panel--radar">
                <h3 className="panel__title">Source scope</h3>
                {blips.length ? (
                  <Radar blips={blips} size={280} />
                ) : (
                  <Empty
                    message="No contacts on scope"
                    hint="Add a report, then run analysis."
                  />
                )}
              </section>

              <section className="panel panel--feed">
                <h3 className="panel__title">Live feed ({reports.length})</h3>
                {reports.length ? (
                  <div className="log scroll-y" style={{ maxHeight: 320 }}>
                    {reports.map((r: Report) => (
                      <div className="log__row" key={r.id}>
                        <span className="log__time">{clockTime(r.timestamp)}</span>
                        <div className="log__msg" style={{ minWidth: 0 }}>
                          <div style={{ display: 'flex', gap: '0.35rem', alignItems: 'center', flexWrap: 'wrap' }}>
                            <SourceChip type={r.source_type} />
                            <span className="faint" style={{ fontSize: '0.62rem' }}>
                              {r.source} · {r.location}
                            </span>
                          </div>
                          <div style={{ marginTop: '0.15rem' }}>{r.event}</div>
                        </div>
                        <button
                          className="button button--danger button--sm"
                          onClick={() => removeReport(r.id)}
                          disabled={busy}
                          title="Delete report"
                        >
                          ✕
                        </button>
                      </div>
                    ))}
                  </div>
                ) : (
                  <Empty
                    message="Feed is empty"
                    hint="Every report here is one you entered."
                  />
                )}
              </section>
            </div>

            {/* ENTRY + FEED */}
            <div>
              <section className="panel" style={{ marginBottom: '0.85rem' }}>
                <h3 className="panel__title">Log field report</h3>
                {formError ? (
                  <div className="banner banner--err" style={{ marginBottom: '0.6rem' }}>
                    <span>{formError}</span>
                  </div>
                ) : null}

                <div className="form-grid">
                  <div className="field">
                    <label className="field__label">Equipment</label>
                    <select
                      className="select"
                      value={selectedEquipment}
                      onChange={(e) => setSelectedEquipment(e.target.value)}
                    >
                      <option value="">— unattributed —</option>
                      {data?.equipment.map((e) => (
                        <option key={e.equipment_id} value={e.equipment_id}>
                          {e.name} ({e.source_type})
                        </option>
                      ))}
                    </select>
                  </div>

                  <div className="form-row">
                    <div className="field">
                      <label className="field__label">Zone</label>
                      <select
                        className="select"
                        value={formZone}
                        onChange={(e) => setFormZone(e.target.value)}
                      >
                        {zones.map((z) => (
                          <option key={z.zone_id} value={z.name}>
                            {z.name}
                          </option>
                        ))}
                      </select>
                    </div>
                    <div className="field">
                      <label className="field__label">Observed at</label>
                      <input
                        className="input"
                        type="datetime-local"
                        value={formTime}
                        onChange={(e) => setFormTime(e.target.value)}
                      />
                    </div>
                  </div>

                  <div className="field">
                    <label className="field__label">Observation</label>
                    <textarea
                      className="textarea"
                      placeholder="3 vehicles moving north along the ridge road. No markings visible."
                      value={formText}
                      onChange={(e) => setFormText(e.target.value)}
                    />
                  </div>

                  <button
                    className="button button--solid"
                    onClick={submitReport}
                    disabled={busy}
                  >
                    {busy ? 'Transmitting…' : 'Transmit report'}
                  </button>

                  {activeEquipment ? (
                    <p className="section__sub" style={{ marginTop: 0 }}>
                      Attributed to <b style={{ color: 'var(--neon)' }}>{activeEquipment.name}</b>{' '}
                      · type {activeEquipment.source_type} · τ governs how fast it decays.
                    </p>
                  ) : null}
                </div>
              </section>

              
          </div>

          {/* ── Verdict summary ─────────────────────────────────────────── */}
          {result ? (
            <section className="panel" style={{ gridColumn: '1 / -1' }}>
              <div className="section__head">
                <div>
                  <h3 className="panel__title" style={{ marginBottom: 0 }}>
                    Latest verdict
                  </h3>
                  <p className="section__sub">
                    {result.summary.scenario_time} · {result.summary.total_claims} claims ·{' '}
                    {result.summary.locations_checked} location(s)
                  </p>
                </div>
                <Link className="button button--sm" to={`/analysis?zone=${encodeURIComponent(zoneFilter ?? '')}`}>
                  Full breakdown →
                </Link>
              </div>

              <div className="stat-strip" style={{ marginBottom: '0.6rem' }}>
                <span>contradictions <b>{result.summary.total_contradictions}</b></span>
                <span>supports <b>{result.summary.total_supports}</b></span>
                <span>stale <b>{result.summary.stale_count}</b></span>
                <span>gaps <b>{result.summary.total_gaps}</b></span>
                <span>avg freshness <b>{pct(result.summary.avg_freshness, 1)}</b></span>
              </div>

              <p className="verdict-hero__rationale">{result.rationale}</p>

              {result.claims.length ? (
                <div className="log" style={{ marginTop: '0.75rem' }}>
                  {result.claims.slice(0, 6).map((c) => (
                    <div className="log__row" key={c.id}>
                      <span className="log__time">{c.id}</span>
                      <span className="log__msg">
                        {c.source} · {c.location} · {c.event}
                      </span>
                      <span className="faint nowrap">{ageHuman(c.age_minutes)}</span>
                      <FreshnessChip label={c.freshness_label} score={c.freshness_score} />
                    </div>
                  ))}
                </div>
              ) : null}
            </section>
          ) : null}
        </div>
        </>
      ) : null}

      {loading ? <Loading label="Loading area" /> : null}
    </div>
  );
}
