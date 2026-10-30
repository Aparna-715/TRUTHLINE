/**
 * TRUTHLINE — sidebar
 * ==========================================================================
 * Logo, nav, and a live backend status block so the operator can see at a
 * glance whether Qdrant / the LLM are reachable.
 */

import { useEffect, useState } from 'react';
import { NavLink } from 'react-router-dom';
import { fetchHealth } from '../api';
import type { HealthResponse } from '../types';
import './Sidebar.css';

const NAV = [
  { to: '/', label: 'Console', glyph: '▸', end: true },
  { to: '/analysis', label: 'Analysis', glyph: '◉', end: false },
  { to: '/validation', label: 'Validation', glyph: '▤', end: false },
];

export default function Sidebar() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [down, setDown] = useState(false);

  useEffect(() => {
    let alive = true;
    fetchHealth()
      .then((h) => {
        if (alive) setHealth(h);
      })
      .catch(() => {
        if (alive) setDown(true);
      });
    return () => {
      alive = false;
    };
  }, []);

  return (
    <nav className="sidebar">
      <div className="sidebar__brand">
        <img src="/logo.svg" alt="TRUTHLINE" className="sidebar__logo" />
        <div>
          <div className="sidebar__name">TRUTHLINE</div>
          <div className="sidebar__tag">Evidence Integrity</div>
        </div>
      </div>

      <ul className="sidebar__nav">
        {NAV.map((n) => (
          <li key={n.to}>
            <NavLink
              to={n.to}
              end={n.end}
              className={({ isActive }) => (isActive ? 'active' : '')}
            >
              <span className="sidebar__glyph">{n.glyph}</span>
              <span>{n.label}</span>
            </NavLink>
          </li>
        ))}
      </ul>

      <div className="sidebar__status">
        <div className="sidebar__status-title">Systems</div>
        {down ? (
          <div className="status-row">
            <span className="dot dot--err" />
            <span>API unreachable</span>
          </div>
        ) : health ? (
          <>
            <div className="status-row">
              <span className={`dot ${health.qdrant.available ? 'dot--ok' : 'dot--warn'}`} />
              <span>QDRANT {health.qdrant.available ? 'LIVE' : 'OFFLINE'}</span>
            </div>
            <div className="status-row">
              <span className={`dot ${health.llm.available ? 'dot--ok' : 'dot--warn'}`} />
              <span>LLM {health.llm.available ? 'LIVE' : 'RULES'}</span>
            </div>
            <div className="status-row">
              <span className="dot dot--info" />
              <span>SQLITE OK</span>
            </div>
            <div className="status-row faint">
              <span className="dot dot--info" />
              <span>{health.totals.sources} reports</span>
            </div>
          </>
        ) : (
          <div className="status-row faint">
            <span className="dot dot--info" />
            <span>CHECKING…</span>
          </div>
        )}
      </div>
    </nav>
  );
}
