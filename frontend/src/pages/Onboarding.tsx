// frontend/src/pages/Onboarding.tsx
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { authAPI, profileAPI } from '../api/client';

export function Onboarding() {
  const [step, setStep] = useState<'register' | 'profile'>('register');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const navigate = useNavigate();

  async function handleRegister(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setLoading(true);
    setError('');
    const form = e.currentTarget;
    const data = {
      workspace_name: (form.elements.namedItem('workspace') as HTMLInputElement).value,
      email: (form.elements.namedItem('email') as HTMLInputElement).value,
      password: (form.elements.namedItem('password') as HTMLInputElement).value,
    };
    try {
      await authAPI.register(data);
      const loginResp = await authAPI.login(data.email, data.password);
      localStorage.setItem('sonar_token', loginResp.data.access_token);
      setStep('profile');
    } catch {
      setError('Registration failed. Email may already be taken.');
    }
    setLoading(false);
  }

  async function handleProfile(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setLoading(true);
    setError('');
    const form = e.currentTarget;
    const url = (form.elements.namedItem('url') as HTMLInputElement).value;
    try {
      await profileAPI.extract({ url });
      navigate('/alerts');
    } catch {
      setError('Failed to extract profile. Check the URL and try again.');
    }
    setLoading(false);
  }

  return (
    <div style={{ maxWidth: 480, margin: '80px auto', padding: 24 }}>
      <h1 style={{ fontSize: 24, marginBottom: 8 }}>⚡ Welcome to Sonar</h1>
      <p style={{ color: '#666', marginBottom: 32 }}>Network-aware LinkedIn intent intelligence.</p>

      {step === 'register' && (
        <form onSubmit={handleRegister}>
          <h2 style={{ fontSize: 18, marginBottom: 16 }}>Create your workspace</h2>
          <input name="workspace" placeholder="Agency / Company name" required style={inputStyle} />
          <input name="email" type="email" placeholder="Email" required style={inputStyle} />
          <input name="password" type="password" placeholder="Password" required style={inputStyle} />
          {error && <p style={{ color: '#dc2626', fontSize: 13 }}>{error}</p>}
          <button type="submit" disabled={loading} style={btnStyle}>
            {loading ? 'Creating...' : 'Create Workspace →'}
          </button>
        </form>
      )}

      {step === 'profile' && (
        <form onSubmit={handleProfile}>
          <h2 style={{ fontSize: 18, marginBottom: 8 }}>Tell Sonar what you do</h2>
          <p style={{ color: '#666', fontSize: 14, marginBottom: 16 }}>
            Paste your website URL. Sonar will learn your capabilities automatically.
          </p>
          <input name="url" type="url" placeholder="https://yourcompany.com" required style={inputStyle} />
          {error && <p style={{ color: '#dc2626', fontSize: 13 }}>{error}</p>}
          <button type="submit" disabled={loading} style={btnStyle}>
            {loading ? 'Analyzing your website...' : 'Start Listening →'}
          </button>
        </form>
      )}
    </div>
  );
}

const inputStyle: React.CSSProperties = {
  width: '100%', padding: '10px 12px', marginBottom: 12, fontSize: 14,
  border: '1px solid #e5e7eb', borderRadius: 6, boxSizing: 'border-box',
};
const btnStyle: React.CSSProperties = {
  width: '100%', padding: '10px 0', background: '#0077b5', color: 'white',
  border: 'none', borderRadius: 6, fontSize: 14, fontWeight: 600, cursor: 'pointer',
};
