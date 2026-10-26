import uvicorn
from core.config import settings

if __name__ == "__main__":
    host = settings.HOST
    port = settings.PORT
    print(f"Starting FixForge Backend on {host}:{port}...")
    uvicorn.run("api.main:app", host=host, port=port, reload=True)
