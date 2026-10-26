from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routes import webhooks, sessions, streams, health, memory
from db.session import init_db
from core.config import settings

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield

app = FastAPI(title="FixForge API", version="1.0.0", lifespan=lifespan)

cors_origins = [origin.strip() for origin in settings.CORS_ORIGINS.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins if cors_origins else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api", tags=["Health"])
app.include_router(webhooks.router, prefix="/api/webhooks", tags=["Webhooks"])
app.include_router(sessions.router, prefix="/api/sessions", tags=["Sessions"])
app.include_router(streams.router, prefix="/api/sessions", tags=["Streams"])
app.include_router(memory.router, prefix="/api/memory", tags=["Memory"])

@app.get("/")
def health_check():
    return health.get_system_health()
