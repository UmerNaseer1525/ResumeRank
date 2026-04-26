import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")


@dataclass(frozen=True)
class Settings:
    mongo_uri: str = os.getenv("MONGO_URI", "")
    mongo_uri_direct: str = os.getenv("MONGO_URI_DIRECT", "")
    mongo_dns_servers: str = os.getenv("MONGO_DNS_SERVERS", "")
    db_name: str = os.getenv("DB_NAME", "resumesDB")
    jwt_secret: str = os.getenv("JWT_SECRET", "resume-rank-dev-secret")
    port: int = int(os.getenv("PORT", "5000"))
    cors_origins: str = os.getenv("CORS_ORIGINS", "*")

    @property
    def cors_origin_list(self) -> list[str]:
        if self.cors_origins.strip() == "*":
            return ["*"]
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


settings = Settings()
