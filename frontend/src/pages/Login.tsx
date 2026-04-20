// frontend/src/pages/Login.tsx
import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { authAPI } from '../api/client';

export function Login() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const navigate = useNavigate();

  async function handleLogin(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setLoading(true);
    setError('');
    const form = e.currentTarget;
    const email = (form.elements.namedItem('email') as HTMLInputElement).value;
    const password = (form.elements.namedItem('password') as HTMLInputElement).value;
    try {
      const resp = await authAPI.login(email, password);
      localStorage.setItem('sonar_token', resp.data.access_token);
      navigate('/dashboard');
    } catch {
      setError('Incorrect email or password.');
    }
    setLoading(false);
  }

  return (
    <div style={{ maxWidth: 480, margin: '80px auto', padding: 24 }}>
      <h1 style={{ fontSize: 24, marginBottom: 8 }}>⚡ Sign in to Sonar</h1>
      <p style={{ color: '#666', marginBottom: 32 }}>Welcome back.</p>

      <form onSubmit={handleLogin}>
        <input name="email" type="email" placeholder="Email" required style={inputStyle} />
        <input name="password" type="password" placeholder="Password" required style={inputStyle} />
        {error && <p style={{ color: '#dc2626', fontSize: 13 }}>{error}</p>}
        <button type="submit" disabled={loading} style={btnStyle}>
          {loading ? 'Signing in...' : 'Sign in →'}
        </button>
      </form>

      <p style={{ color: '#666', fontSize: 14, marginTop: 24, textAlign: 'center' }}>
        New to Sonar?{' '}
        <Link to="/" style={{ color: '#0077b5', textDecoration: 'none' }}>
          Create a workspace
        </Link>
      </p>
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
