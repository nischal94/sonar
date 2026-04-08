# backend/app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers.auth import router as auth_router, workspace_router
from app.routers.profile import router as profile_router
from app.routers.ingest import router as ingest_router

app = FastAPI(title="Sonar API", version="1.0.0")

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

@app.get("/health")
async def health():
    return {"status": "ok"}
