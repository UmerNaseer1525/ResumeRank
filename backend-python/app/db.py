from __future__ import annotations

from pymongo import MongoClient
from pymongo.errors import ConfigurationError
from pymongo.database import Database

from app.config import settings

_client: MongoClient | None = None
_db: Database | None = None


def _configure_dns_resolver() -> None:
    dns_servers = [item.strip() for item in settings.mongo_dns_servers.split(",") if item.strip()]
    if not dns_servers:
        return

    try:
        import dns.resolver

        resolver = dns.resolver.get_default_resolver()
        resolver.nameservers = dns_servers
        print(f"Using custom DNS servers for MongoDB: {', '.join(dns_servers)}")
    except Exception as exc:
        print(f"Unable to configure custom DNS servers ({exc}). Continuing with system DNS.")


def _build_client(uri: str) -> MongoClient:
    # Assumption: this app runs as a long-lived API server with moderate traffic.
    return MongoClient(
        uri,
        maxPoolSize=50,
        minPoolSize=5,
        maxIdleTimeMS=300000,
        connectTimeoutMS=10000,
        socketTimeoutMS=30000,
        serverSelectionTimeoutMS=10000,
        waitQueueTimeoutMS=5000,
    )


def connect_db() -> Database:
    global _client
    global _db

    if _db is not None:
        return _db

    if not settings.mongo_uri:
        raise RuntimeError("MONGO_URI is missing in environment variables.")

    _configure_dns_resolver()

    try:
        _client = _build_client(settings.mongo_uri)
        _client.admin.command("ping")
    except Exception as exc:
        exc_message = str(exc)
        is_srv_uri = settings.mongo_uri.startswith("mongodb+srv://")
        is_srv_dns_error = isinstance(exc, ConfigurationError) and (
            "querysrv" in exc_message.lower() or "dns query name does not exist" in exc_message.lower()
        )

        if is_srv_uri and is_srv_dns_error and settings.mongo_uri_direct:
            print("MongoDB SRV lookup failed. Retrying with MONGO_URI_DIRECT fallback URI.")
            _client = _build_client(settings.mongo_uri_direct)
            _client.admin.command("ping")
        else:
            raise

    default_db = _client.get_default_database()
    _db = default_db if default_db is not None else _client[settings.db_name]

    _db.users.create_index("email", unique=True)
    print("MongoDB connected successfully")
    return _db


def get_db() -> Database:
    if _db is None:
        return connect_db()
    return _db


def close_db() -> None:
    global _client
    global _db

    if _client is not None:
        _client.close()
    _client = None
    _db = None
