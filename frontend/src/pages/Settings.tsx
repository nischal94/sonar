// frontend/src/pages/Settings.tsx
import { useState } from 'react';
import api from '../api/client';

export function Settings() {
  const [slackWebhook, setSlackWebhook] = useState('');
  const [email, setEmail] = useState('');
  const [telegram, setTelegram] = useState('');
  const [whatsapp, setWhatsapp] = useState('');
  const [saved, setSaved] = useState(false);

  async function save(e: React.FormEvent) {
    e.preventDefault();
    const channels: Record<string, unknown> = {};
    if (slackWebhook) channels.slack = { webhook_url: slackWebhook, min_priority: 'low' };
    if (email) channels.email = { address: email };
    if (telegram) channels.telegram = { chat_id: telegram };
    if (whatsapp) channels.whatsapp = { phone: whatsapp };

    await api.patch('/workspace/channels', { delivery_channels: channels });
    setSaved(true);
    setTimeout(() => setSaved(false), 3000);
  }

  return (
    <div style={{ maxWidth: 480, margin: '0 auto', padding: '24px 16px' }}>
      <h2 style={{ fontSize: 20, marginBottom: 20 }}>⚙️ Delivery Channels</h2>
      <form onSubmit={save}>
        <label style={labelStyle}>Slack Webhook URL</label>
        <input value={slackWebhook} onChange={e => setSlackWebhook(e.target.value)} placeholder="https://hooks.slack.com/..." style={inputStyle} />

        <label style={labelStyle}>Email Address</label>
        <input type="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="you@company.com" style={inputStyle} />

        <label style={labelStyle}>Telegram Chat ID</label>
        <input value={telegram} onChange={e => setTelegram(e.target.value)} placeholder="123456789" style={inputStyle} />

        <label style={labelStyle}>WhatsApp Phone (with country code)</label>
        <input value={whatsapp} onChange={e => setWhatsapp(e.target.value)} placeholder="+14155238886" style={inputStyle} />

        <button type="submit" style={btnStyle}>{saved ? '✓ Saved!' : 'Save Channels'}</button>
      </form>
    </div>
  );
}

const labelStyle: React.CSSProperties = { display: 'block', fontSize: 13, fontWeight: 600, marginBottom: 4, color: '#444' };
const inputStyle: React.CSSProperties = { width: '100%', padding: '8px 12px', marginBottom: 16, fontSize: 14, border: '1px solid #e5e7eb', borderRadius: 6, boxSizing: 'border-box' };
const btnStyle: React.CSSProperties = { width: '100%', padding: '10px 0', background: '#0077b5', color: 'white', border: 'none', borderRadius: 6, fontSize: 14, fontWeight: 600, cursor: 'pointer' };
