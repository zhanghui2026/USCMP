"""Core configuration using pydantic-settings."""

from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_env: str = "development"
    backend_port: int = 8000
    frontend_port: int = 3000

    # PostgreSQL
    postgres_host: str = "postgres"
    postgres_port: int = 5432
    postgres_db: str = "congress_graph"
    postgres_user: str = "congress_user"
    postgres_password: str = "congress_password"

    # SQLite fallback (for lightweight deployment without PostgreSQL)
    use_sqlite_fallback: bool = True
    sqlite_fallback_path: str = "data/congress.db"

    # Neo4j
    neo4j_uri: str = "bolt://neo4j:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "neo4j_password"

    # LLM (disabled in Phase 1)
    enable_llm: bool = False
    llm_provider: str = ""
    llm_api_key: str = ""

    # ETL (disabled in Phase 1)
    enable_real_etl: bool = False

    # Graph query limits
    default_graph_limit: int = 200
    max_graph_limit: int = 500
    max_graph_depth: int = 2

    # Mock seed
    mock_random_seed: int = 42
    mock_member_count: int = 50
    mock_org_count: int = 100
    mock_political_entity_count: int = 20
    mock_event_count: int = 100
    mock_claim_count: int = 500
    mock_source_doc_count: int = 500
    mock_relation_count: int = 300

    @property
    def postgres_url(self) -> str:
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def postgres_url_sync(self) -> str:
        return (
            f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()

# Scoring weights config path — reserved for future real scoring model.
# Currently all scoring/metrics use Mock demo values with fixed baselines.
# See app/core/scoring_weights.yaml and docs/scoring_methodology.md.
SCORING_WEIGHTS_PATH = Path(__file__).parent / "scoring_weights.yaml"
