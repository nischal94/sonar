// frontend/src/components/ScoreBar.tsx
interface ScoreBarProps {
  label: string;
  score: number;
}

export function ScoreBar({ label, score }: ScoreBarProps) {
  const pct = Math.round(score * 100);
  const color = pct >= 80 ? '#dc2626' : pct >= 55 ? '#d97706' : '#16a34a';

  return (
    <div style={{ marginBottom: 4 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, color: '#666' }}>
        <span>{label}</span>
        <span>{pct}%</span>
      </div>
      <div style={{ background: '#e5e7eb', borderRadius: 4, height: 6, overflow: 'hidden' }}>
        <div style={{ width: `${pct}%`, background: color, height: '100%', borderRadius: 4 }} />
      </div>
    </div>
  );
}
