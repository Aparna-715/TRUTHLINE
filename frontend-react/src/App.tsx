/**
 * TRUTHLINE — app shell
 * ==========================================================================
 * Routing only. No data fetching here — each page owns its own.
 *
 *   /            Console      the operational workspace (real reports)
 *   /analysis    Analysis     full pipeline readout over those reports
 *   /validation  Validation   the five labelled fixtures (proof, not demo)
 *   /case/:id    CaseDetail   drill-down on one fixture
 */

import { BrowserRouter as Router, Navigate, Route, Routes } from 'react-router-dom';
import Sidebar from './components/Sidebar';
import MatrixRain from './components/MatrixRain';
import ErrorBoundary from './components/ErrorBoundary';
import Console from './pages/Console';
import Analysis from './pages/Analysis';
import Validation from './pages/Validation';
import CaseDetail from './pages/CaseDetail';
import './App.css';

function App() {
  return (
    <Router>
      <MatrixRain />
      <div className="app-container">
        <Sidebar />
        <main className="main-content">
          <ErrorBoundary>
            <Routes>
              <Route path="/" element={<Console />} />
              <Route path="/analysis" element={<Analysis />} />
              <Route path="/validation" element={<Validation />} />
              <Route path="/case/:id" element={<CaseDetail />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </ErrorBoundary>
        </main>
      </div>
    </Router>
  );
}

export default App;
