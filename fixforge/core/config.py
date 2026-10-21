from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
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
    PORT: int = 8000
    GIT_CLONE_TIMEOUT_SEC: int = 60
    # Stage 8: Default to dry-run; set GITHUB_DRY_RUN=false to post real comments.
    GITHUB_DRY_RUN: bool = True
    # Stage 5: Per-session workflow timeout (seconds). Prevents hung sessions.
    WORKFLOW_TIMEOUT_SEC: int = 300
    # Stage 7: LLM consistency check — number of low-temp samples for the Fixer.
    LLM_CONSISTENCY_SAMPLES: int = 2

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

settings = Settings()
