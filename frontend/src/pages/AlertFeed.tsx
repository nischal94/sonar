// frontend/src/pages/AlertFeed.tsx
import { useEffect, useState } from 'react';
import { Alert, alertsAPI } from '../api/client';
import { AlertCard } from '../components/AlertCard';

export function AlertFeed() {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [filter, setFilter] = useState<'all' | 'high' | 'medium' | 'low'>('all');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      setLoading(true);
      const resp = await alertsAPI.list({ priority: filter === 'all' ? undefined : filter });
      setAlerts(resp.data);
      setLoading(false);
    }
    load();
  }, [filter]);

  function handleFeedback(alertId: string, feedback: 'positive' | 'negative') {
    setAlerts(prev => prev.map(a => a.id === alertId ? { ...a, feedback } : a));
  }

  return (
    <div style={{ maxWidth: 640, margin: '0 auto', padding: '24px 16px' }}>
      <h2 style={{ fontSize: 20, marginBottom: 16 }}>⚡ Signal Feed</h2>

      <div style={{ display: 'flex', gap: 8, marginBottom: 20 }}>
        {(['all', 'high', 'medium', 'low'] as const).map(p => (
          <button
            key={p}
            onClick={() => setFilter(p)}
            style={{
              padding: '4px 12px', borderRadius: 20, fontSize: 12, cursor: 'pointer',
              background: filter === p ? '#0077b5' : '#f3f4f6',
              color: filter === p ? 'white' : '#444',
              border: 'none', fontWeight: filter === p ? 600 : 400,
            }}
          >
            {p === 'all' ? 'All' : `${p === 'high' ? '🔴' : p === 'medium' ? '🟡' : '🟢'} ${p}`}
          </button>
        ))}
      </div>

      {loading && <p style={{ color: '#888' }}>Loading signals...</p>}

      {!loading && alerts.length === 0 && (
        <div style={{ textAlign: 'center', padding: 40, color: '#888' }}>
          <p>No signals yet.</p>
          <p style={{ fontSize: 13 }}>Install the Chrome extension and open LinkedIn to start syncing.</p>
        </div>
      )}

      {alerts.map(alert => (
        <AlertCard key={alert.id} alert={alert} onFeedback={handleFeedback} />
      ))}
    </div>
  );
}
