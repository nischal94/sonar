// frontend/src/pages/OpportunityBoard.tsx
import { useEffect, useState } from 'react';
import { Alert, alertsAPI } from '../api/client';

const COLUMNS = [
  { key: 'pending', label: 'Open Signals' },
  { key: 'acted', label: 'Contacted' },
  { key: 'dismissed', label: 'Dismissed' },
];

export function OpportunityBoard() {
  const [alerts, setAlerts] = useState<Alert[]>([]);

  useEffect(() => {
    alertsAPI.list({ limit: 200 }).then(r => setAlerts(r.data));
  }, []);

  return (
    <div style={{ padding: '24px 16px' }}>
      <h2 style={{ fontSize: 20, marginBottom: 20 }}>📋 Opportunity Board</h2>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16 }}>
        {COLUMNS.map(col => {
          const colAlerts = alerts.filter(a => a.status === col.key);
          return (
            <div key={col.key} style={{ background: '#f9fafb', borderRadius: 8, padding: 12 }}>
              <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 12, color: '#444' }}>
                {col.label} ({colAlerts.length})
              </h3>
              {colAlerts.map(alert => (
                <div key={alert.id} style={{
                  background: 'white', borderRadius: 6, padding: 10, marginBottom: 8,
                  border: '1px solid #e5e7eb', fontSize: 13
                }}>
                  <div style={{ fontWeight: 600, marginBottom: 4 }}>
                    {alert.priority === 'high' ? '🔴' : alert.priority === 'medium' ? '🟡' : '🟢'} {alert.opportunity_type?.replace('_', ' ')}
                  </div>
                  <div style={{ color: '#888', fontSize: 12 }}>
                    Score: {Math.round(alert.combined_score * 100)}%
                  </div>
                </div>
              ))}
              {colAlerts.length === 0 && (
                <p style={{ color: '#bbb', fontSize: 13 }}>Empty</p>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
