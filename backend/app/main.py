# backend/app/main.py
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from app.rate_limit import limiter
from app.routers.auth import router as auth_router, workspace_router
from app.routers.profile import router as profile_router
from app.routers.ingest import router as ingest_router
from app.routers.alerts import router as alerts_router
from app.routers.signals import router as signals_router
from app.routers.dashboard import router as dashboard_router
from app.routers.backfill import router as backfill_router

app = FastAPI(title="Sonar API", version="1.0.0")

app.state.limiter = limiter


def _rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    # Do NOT echo slowapi's default "N per X" policy string — it hands
    # credential-stuffing bots a calibration signal. Retry-After is
    # standard and safe to include.
    response = JSONResponse(
        status_code=429,
        content={"detail": "Too many requests"},
    )
    response.headers["Retry-After"] = "60"
    return response


app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Vite dev server
        # Content scripts on linkedin.com fetch with Origin: https://www.linkedin.com
        # (MV3 content scripts share the page's network origin, not the extension's).
        # Safe because /extension/* endpoints still require the Bearer token held
        # only in chrome.storage.local, inaccessible from page-world scripts. Prod
        # should route these calls through the service worker (chrome-extension
        # origin already allowed via allow_origin_regex below) — tracked as a
        # hardening follow-up.
        "https://www.linkedin.com",
    ],
    # Chrome extensions send requests from chrome-extension://<id> — the id is
    # per-install and unpredictable, so we match the scheme with a regex.
    allow_origin_regex=r"^chrome-extension://[a-z0-9]+$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(workspace_router)
app.include_router(profile_router)
app.include_router(ingest_router)
app.include_router(alerts_router)
app.include_router(signals_router)
app.include_router(dashboard_router)
app.include_router(backfill_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
