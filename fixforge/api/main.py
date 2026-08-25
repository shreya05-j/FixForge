from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routes import webhooks, sessions, streams
from db.session import init_db

app = FastAPI(title="FixForge API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def on_startup():
    init_db()

app.include_router(webhooks.router, prefix="/api/webhooks", tags=["Webhooks"])
app.include_router(sessions.router, prefix="/api/sessions", tags=["Sessions"])
app.include_router(streams.router, prefix="/api/sessions", tags=["Streams"])

@app.get("/")
def health_check():
    return {"status": "healthy", "service": "FixForge Orchestrator"}
