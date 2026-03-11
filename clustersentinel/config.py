"""Central configuration via Pydantic BaseSettings — loaded from .env."""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from pathlib import Path


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # LLM
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    llm_model: str = Field(default="claude-sonnet-4-20250514", alias="LLM_MODEL")
    llm_max_tokens: int = Field(default=1500, alias="LLM_MAX_TOKENS")
    llm_provider: str = Field(default="anthropic", alias="LLM_PROVIDER")  # "anthropic" | "ollama"
    ollama_base_url: str = Field(default="http://localhost:11434", alias="OLLAMA_BASE_URL")
    ollama_model: str = Field(default="llama3", alias="OLLAMA_MODEL")

    # Database
    database_url: str = Field(default="sqlite:///./clustersentinel.db", alias="DATABASE_URL")
    chroma_persist_dir: str = Field(default="./chroma_db", alias="CHROMA_PERSIST_DIR")

    # Simulation
    default_cluster_nodes: int = Field(default=4, alias="DEFAULT_CLUSTER_NODES")
    metric_interval_seconds: int = Field(default=30, alias="METRIC_INTERVAL_SECONDS")
    anomaly_ensemble_threshold: float = Field(default=0.65, alias="ANOMALY_ENSEMBLE_THRESHOLD")

    # Models
    models_dir: Path = Field(default=Path("./models"), alias="MODELS_DIR")

    # API
    api_host: str = Field(default="0.0.0.0", alias="API_HOST")
    api_port: int = Field(default=8000, alias="API_PORT")


settings = Settings()
