from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    GROQ_API_KEY: str = ""
    OPENROUTER_API_KEY: str = ""
    GITHUB_TOKEN: str = ""
    SANDBOX_TIMEOUT: int = 30
    CHROMA_DB_PATH: str = "./chroma_data"
    DATABASE_URL: str = "sqlite:///./fixforge.db"

    class Config:
        env_file = ".env"

settings = Settings()
