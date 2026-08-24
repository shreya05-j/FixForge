from fastapi import FastAPI
from api.routes import webhooks, sessions
from db.session import init_db

app = FastAPI(title="FixForge API", version="1.0.0")

@app.on_event("startup")
def on_startup():
    init_db()

app.include_router(webhooks.router, prefix="/api/webhooks", tags=["Webhooks"])
app.include_router(sessions.router, prefix="/api/sessions", tags=["Sessions"])

@app.get("/")
def health_check():
    return {"status": "healthy", "service": "FixForge Orchestrator"}
