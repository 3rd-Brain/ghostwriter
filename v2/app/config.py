from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://ghostwriter:ghostwriter@db:5432/ghostwriter"

    # System-level fallback API keys
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    google_api_key: str = ""

    # Apify for Twitter scraping
    apify_api_token: str = ""

    # Embedding model
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536

    model_config = {"env_file": ".env"}


settings = Settings()
