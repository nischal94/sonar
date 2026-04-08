# Sonar Dashboard

React 18 + Vite + TypeScript dashboard for the Sonar intent intelligence platform.

---

## Pages

| Route | Page | Description |
|---|---|---|
| `/` | Onboarding | Workspace registration → capability profile setup |
| `/alerts` | Signal Feed | Real-time alert list with priority filter and feedback |
| `/board` | Opportunity Board | Kanban view grouped by alert status |
| `/settings` | Settings | Configure delivery channels (Slack, email, Telegram, WhatsApp) |

---

## Running Locally

### With Docker (recommended)

```bash
# From repo root
docker compose up frontend
```

Visit `http://localhost:5173`.

### Without Docker

```bash
cd frontend
npm install
npm run dev
```

Requires Node 20+.

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `VITE_API_BASE` | `http://localhost:8000` | Sonar API base URL |

Set in a `.env` file at `frontend/.env`:

```env
VITE_API_BASE=http://localhost:8000
```

---

## Onboarding Flow

1. **Register** — enter workspace name, email, and password. A JWT is stored in `localStorage` as `sonar_token`.
2. **Profile setup** — paste your company website URL. Sonar fetches the page, runs it through the LLM, and stores a capability profile + embedding. This tells Sonar what to look for in your network's posts.
3. **Signal Feed** — you land here once the profile is ready.

---

## Signal Feed

- Signals are fetched from `GET /alerts` and polled when the filter changes.
- Filter by priority: All / 🔴 High / 🟡 Medium / 🟢 Low.
- Each `AlertCard` shows:
  - Priority label + timestamp
  - Match reason (why this post is relevant to your business)
  - Score breakdown bars (relevance, relationship, timing)
  - Two outreach drafts: **Draft A** (direct) and **Draft B** (question-based)
  - Copy button for each draft
  - Feedback buttons: **Acted on this** (positive) / **Not relevant** (negative)

Feedback is sent to `POST /alerts/{id}/feedback` and triggers Sonar's threshold auto-adjustment.

---

## API Client

All API calls go through `src/api/client.ts`. It is an axios instance with a request interceptor that attaches the JWT from `localStorage`:

```typescript
import { alertsAPI, authAPI, profileAPI } from './api/client';

// List alerts filtered by priority
const resp = await alertsAPI.list({ priority: 'high' });

// Submit feedback
await alertsAPI.feedback(alertId, { feedback: 'positive' });
```

---

## File Structure

```
frontend/
├── index.html
├── vite.config.ts
├── tsconfig.json
├── package.json
├── Dockerfile                  # For docker compose frontend service
└── src/
    ├── main.tsx                # React root
    ├── App.tsx                 # Router + RequireAuth guard + Nav
    ├── api/
    │   └── client.ts           # Axios client + typed API methods
    ├── components/
    │   ├── AlertCard.tsx       # Alert display with drafts + feedback
    │   └── ScoreBar.tsx        # Score dimension progress bar
    └── pages/
        ├── Onboarding.tsx      # Register + profile setup flow
        ├── AlertFeed.tsx       # Filtered signal list
        ├── OpportunityBoard.tsx # Kanban by alert status
        └── Settings.tsx        # Delivery channel config form
```

---

## Build for Production

```bash
npm run build
```

Output goes to `dist/`. Serve with any static file server or Nginx.
