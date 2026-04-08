// frontend/src/api/client.ts
import axios from 'axios';

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000';

const api = axios.create({ baseURL: API_BASE });

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('sonar_token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

export interface Alert {
  id: string;
  priority: 'high' | 'medium' | 'low';
  combined_score: number;
  relevance_score: number;
  relationship_score: number;
  timing_score: number;
  match_reason: string;
  outreach_draft_a: string;
  outreach_draft_b: string;
  opportunity_type: string;
  urgency_reason: string;
  status: string;
  feedback: string | null;
  created_at: string;
}

export const authAPI = {
  register: (data: { workspace_name: string; email: string; password: string }) =>
    api.post('/workspace/register', data),
  login: (email: string, password: string) => {
    const form = new URLSearchParams();
    form.append('username', email);
    form.append('password', password);
    return api.post<{ access_token: string }>('/auth/token', form);
  },
};

export const alertsAPI = {
  list: (params?: { priority?: string; status?: string; limit?: number }) =>
    api.get<Alert[]>('/alerts', { params }),
  feedback: (alertId: string, data: { feedback: string; outcome?: string; message_sent?: string }) =>
    api.post(`/alerts/${alertId}/feedback`, data),
};

export const profileAPI = {
  extract: (data: { url?: string; text?: string }) =>
    api.post('/profile/extract', data),
};

export default api;
