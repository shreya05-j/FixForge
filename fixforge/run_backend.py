import uvicorn
import os

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    print(f"Starting FixForge Backend on port {port}...")
    uvicorn.run("api.main:app", host="0.0.0.0", port=port, reload=True)
