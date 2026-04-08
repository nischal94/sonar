// frontend/src/components/AlertCard.tsx
import { useState } from 'react';
import { Alert, alertsAPI } from '../api/client';
import { ScoreBar } from './ScoreBar';

interface AlertCardProps {
  alert: Alert;
  onFeedback: (alertId: string, feedback: 'positive' | 'negative') => void;
}

const PRIORITY_COLOR: Record<string, string> = { high: '#dc2626', medium: '#d97706', low: '#16a34a' };
const PRIORITY_EMOJI: Record<string, string> = { high: '🔴', medium: '🟡', low: '🟢' };

export function AlertCard({ alert, onFeedback }: AlertCardProps) {
  const [copied, setCopied] = useState<'a' | 'b' | null>(null);
  const [feedbackSent, setFeedbackSent] = useState(false);

  async function handleFeedback(feedback: 'positive' | 'negative') {
    await alertsAPI.feedback(alert.id, { feedback });
    setFeedbackSent(true);
    onFeedback(alert.id, feedback);
  }

  function copyDraft(which: 'a' | 'b') {
    const text = which === 'a' ? alert.outreach_draft_a : alert.outreach_draft_b;
    navigator.clipboard.writeText(text);
    setCopied(which);
    setTimeout(() => setCopied(null), 2000);
  }

  const borderColor = PRIORITY_COLOR[alert.priority] || '#666';

  return (
    <div style={{
      border: `2px solid ${borderColor}`,
      borderRadius: 8,
      padding: 16,
      marginBottom: 12,
      background: 'white',
      boxShadow: '0 1px 3px rgba(0,0,0,0.1)'
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
        <span style={{ fontWeight: 700, fontSize: 14 }}>
          {PRIORITY_EMOJI[alert.priority]} {alert.priority.toUpperCase()} SIGNAL
        </span>
        <span style={{ fontSize: 12, color: '#888' }}>
          {new Date(alert.created_at).toLocaleTimeString()}
        </span>
      </div>

      <p style={{ fontSize: 13, color: '#444', marginBottom: 12 }}>{alert.match_reason}</p>

      <div style={{ marginBottom: 12 }}>
        <ScoreBar label="Relevance" score={alert.relevance_score} />
        <ScoreBar label="Relationship" score={alert.relationship_score} />
        <ScoreBar label="Timing" score={alert.timing_score} />
      </div>

      <div style={{ background: '#f9fafb', borderRadius: 6, padding: 10, marginBottom: 8 }}>
        <div style={{ fontSize: 11, color: '#888', marginBottom: 4 }}>DRAFT A — DIRECT</div>
        <p style={{ fontSize: 13, margin: 0 }}>{alert.outreach_draft_a}</p>
        <button onClick={() => copyDraft('a')} style={{ marginTop: 6, fontSize: 11, cursor: 'pointer', background: 'none', border: '1px solid #e5e7eb', borderRadius: 4, padding: '2px 8px' }}>
          {copied === 'a' ? '✓ Copied!' : 'Copy'}
        </button>
      </div>

      <div style={{ background: '#f9fafb', borderRadius: 6, padding: 10, marginBottom: 12 }}>
        <div style={{ fontSize: 11, color: '#888', marginBottom: 4 }}>DRAFT B — QUESTION</div>
        <p style={{ fontSize: 13, margin: 0 }}>{alert.outreach_draft_b}</p>
        <button onClick={() => copyDraft('b')} style={{ marginTop: 6, fontSize: 11, cursor: 'pointer', background: 'none', border: '1px solid #e5e7eb', borderRadius: 4, padding: '2px 8px' }}>
          {copied === 'b' ? '✓ Copied!' : 'Copy'}
        </button>
      </div>

      {!feedbackSent && alert.feedback === null && (
        <div style={{ display: 'flex', gap: 8 }}>
          <button
            onClick={() => handleFeedback('positive')}
            style={{ flex: 1, padding: '6px 0', background: '#057642', color: 'white', border: 'none', borderRadius: 4, cursor: 'pointer', fontSize: 13 }}
          >
            ✓ Acted on this
          </button>
          <button
            onClick={() => handleFeedback('negative')}
            style={{ flex: 1, padding: '6px 0', background: '#f3f4f6', color: '#444', border: 'none', borderRadius: 4, cursor: 'pointer', fontSize: 13 }}
          >
            ✗ Not relevant
          </button>
        </div>
      )}

      {(feedbackSent || alert.feedback !== null) && (
        <p style={{ fontSize: 12, color: '#888', textAlign: 'center', margin: 0 }}>
          ✓ Sonar is learning your preferences.
        </p>
      )}
    </div>
  );
}
