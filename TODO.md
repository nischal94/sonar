# TODO

## Before running the app (blocked on API keys)

Copy `.env.example` to `.env` and fill in:

| Key | Where to get it | Required? |
|-----|----------------|-----------|
| `SECRET_KEY` | Any random 32+ char string | ✅ Yes |
| `OPENAI_API_KEY` | platform.openai.com | ✅ Yes (embeddings + GPT-4o mini) |
| `GROQ_API_KEY` | console.groq.com (free) | ✅ Yes (Llama for med/low alerts) |
| `SENDGRID_API_KEY` | sendgrid.com | ❌ Optional |
| `TWILIO_ACCOUNT_SID` / `TWILIO_AUTH_TOKEN` | twilio.com | ❌ Optional |
| `TELEGRAM_BOT_TOKEN` | @BotFather on Telegram | ❌ Optional |
| `APIFY_API_TOKEN` | apify.com | ❌ Optional |

Once `.env` is ready:
```bash
cd sonar
docker compose up --build
docker compose exec api alembic upgrade head
```

Then open http://localhost:5173

