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
    
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

settings = Settings()
