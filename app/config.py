import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Agentic Employee AI Assistant"
    app_env: str = "development"
    debug: bool = True
    
    # OpenAI Settings
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    
    # RAG Settings
    data_dir: Path = Path(__file__).parent.parent / "data"
    chroma_persist_directory: str = "./chroma_db"
    embedding_model: str = "all-MiniLM-L6-v2"
    chunk_size: int = 500
    chunk_overlap: int = 50

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
