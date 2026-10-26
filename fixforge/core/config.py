from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = "https://api.ai.kodekloud.com/v1"
    GROQ_API_KEY: str = ""
    OPENROUTER_API_KEY: str = ""
    CHROMA_PERSIST_DIR: str = "./chroma_data"
    DATABASE_URL: str = "sqlite+aiosqlite:///./fixforge.db"
    DOCKER_SANDBOX_IMAGE: str = "fixforge-sandbox:latest"
    MAX_RETRIES: int = 3
    CONTAINER_TIMEOUT_SEC: int = 60
    MAX_CONTAINER_MEMORY: str = "512m"
    GITHUB_WEBHOOK_SECRET: str = ""
    GITHUB_TOKEN: str = ""
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:5173,http://127.0.0.1:3000,http://127.0.0.1:5173"
    GIT_CLONE_TIMEOUT_SEC: int = 60
    # Stage 8: Default to dry-run; set GITHUB_DRY_RUN=false to post real comments.
    GITHUB_DRY_RUN: bool = True
    # Stage 5: Per-session workflow timeout (seconds). Prevents hung sessions.
    WORKFLOW_TIMEOUT_SEC: int = 300
    # Stage 7: LLM consistency check — number of low-temp samples for the Fixer.
    LLM_CONSISTENCY_SAMPLES: int = 2
    FIXFORGE_MODEL: str = "claude-haiku-5-5"


    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()
