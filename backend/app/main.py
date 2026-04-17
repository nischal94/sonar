# backend/app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from app.rate_limit import limiter
from app.routers.auth import router as auth_router, workspace_router
from app.routers.profile import router as profile_router
from app.routers.ingest import router as ingest_router
from app.routers.alerts import router as alerts_router

app = FastAPI(title="Sonar API", version="1.0.0")

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(workspace_router)
app.include_router(profile_router)
app.include_router(ingest_router)
app.include_router(alerts_router)

@app.get("/health")
async def health():
    return {"status": "ok"}
