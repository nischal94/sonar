// frontend/src/App.tsx
import { BrowserRouter, Routes, Route, Navigate, Link } from 'react-router-dom';
import { Onboarding } from './pages/Onboarding';
import { Login } from './pages/Login';
import { AlertFeed } from './pages/AlertFeed';
import { OpportunityBoard } from './pages/OpportunityBoard';
import { Settings } from './pages/Settings';
import SignalConfig from './pages/SignalConfig';
import NetworkIntelligenceDashboard from './pages/NetworkIntelligenceDashboard';

function RequireAuth({ children }: { children: React.ReactNode }) {
  const token = localStorage.getItem('sonar_token');
  return token ? <>{children}</> : <Navigate to="/" replace />;
}

function Nav() {
  return (
    <nav style={{ borderBottom: '1px solid #e5e7eb', padding: '12px 24px', display: 'flex', gap: 24, alignItems: 'center' }}>
      <span style={{ fontWeight: 700, fontSize: 16 }}>⚡ Sonar</span>
      <Link to="/alerts" style={{ fontSize: 14, color: '#444', textDecoration: 'none' }}>Signals</Link>
      <Link to="/board" style={{ fontSize: 14, color: '#444', textDecoration: 'none' }}>Board</Link>
      <Link to="/settings" style={{ fontSize: 14, color: '#444', textDecoration: 'none' }}>Settings</Link>
    </nav>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Onboarding />} />
        <Route path="/login" element={<Login />} />
        <Route path="/alerts" element={<RequireAuth><Nav /><AlertFeed /></RequireAuth>} />
        <Route path="/board" element={<RequireAuth><Nav /><OpportunityBoard /></RequireAuth>} />
        <Route path="/settings" element={<RequireAuth><Nav /><Settings /></RequireAuth>} />
        <Route path="/signals/setup" element={<RequireAuth><Nav /><SignalConfig /></RequireAuth>} />
        <Route path="/dashboard" element={<RequireAuth><Nav /><NetworkIntelligenceDashboard /></RequireAuth>} />
      </Routes>
    </BrowserRouter>
  );
}
