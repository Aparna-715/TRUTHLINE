/**
 * TRUTHLINE — error boundary
 * ==========================================================================
 * Without this, one bad render unmounts the whole tree and the operator gets a
 * blank screen with no explanation. With it, the failing page is replaced by a
 * readable diagnostic and the rest of the shell (sidebar, nav) survives.
 */

import { Component } from 'react';
import type { ErrorInfo, ReactNode } from 'react';

interface Props {
  children: ReactNode;
}

interface State {
  error: Error | null;
  info: string | null;
}

export default class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null, info: null };

  static getDerivedStateFromError(error: Error): Partial<State> {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // Keep the component stack: it names the exact element that threw.
    this.setState({ info: info.componentStack ?? null });
    // eslint-disable-next-line no-console
    console.error('[TRUTHLINE] render error:', error, info.componentStack);
  }

  reset = () => this.setState({ error: null, info: null });

  render() {
    const { error, info } = this.state;

    if (!error) return this.props.children;

    return (
      <div className="page">
        <div className="banner banner--err" style={{ marginBottom: '0.85rem' }}>
          <span>RENDER FAULT — this view failed to mount</span>
        </div>

        <section className="panel">
          <h3 className="panel__title">Diagnostic</h3>
          <p
            className="mono"
            style={{ color: 'var(--v-conflicting)', fontSize: '0.8rem', marginTop: 0 }}
          >
            {error.name}: {error.message}
          </p>

          {info ? (
            <pre
              className="mono"
              style={{
                fontSize: '0.68rem',
                color: 'var(--text-muted)',
                background: 'var(--inset)',
                border: '1px solid var(--line)',
                padding: '0.6rem',
                overflowX: 'auto',
                maxHeight: 260,
                margin: 0,
              }}
            >
              {info.trim()}
            </pre>
          ) : null}

          <div style={{ marginTop: '0.85rem', display: 'flex', gap: '0.5rem' }}>
            <button className="button button--solid" onClick={this.reset}>
              Retry render
            </button>
            <button className="button" onClick={() => window.location.reload()}>
              Reload
            </button>
          </div>
        </section>
      </div>
    );
  }
}
