from dataclasses import dataclass
import os


def _parse_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    project_name: str = os.getenv(
        "PROJECT_NAME",
        "Medical Services Price Aggregator Kazakhstan",
    )
    version: str = os.getenv("APP_VERSION", "0.1.0")
    api_v1_prefix: str = os.getenv("API_V1_PREFIX", "/api/v1")
    import_api_key: str = os.getenv("IMPORT_API_KEY", "example-secret")
    parser_user_agent_name: str = os.getenv("PARSER_USER_AGENT_NAME", "MedPriceBot")
    parser_contact: str = os.getenv("PARSER_CONTACT", "")
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://postgres:postgres@localhost:5432/aggregator",
    )
    cors_origins: list[str] = None

    def __post_init__(self) -> None:
        origins = os.getenv("BACKEND_CORS_ORIGINS", "http://localhost:3000")
        object.__setattr__(self, "cors_origins", _parse_csv(origins))


settings = Settings()
