from sqlalchemy.engine import URL, make_url

from production_rag.core.settings import Settings


def build_database_url(settings: Settings) -> URL:
    """Resolve the configured PostgreSQL URL for the asyncpg driver.

    When ``DATABASE_URL`` is unset, the URL is built from the ``POSTGRES_*``
    local defaults. Otherwise the provided URL is normalized for asyncpg: the
    driver is forced to ``postgresql+asyncpg`` (so ``postgres://`` and
    ``postgresql://`` are accepted) and the libpq ``sslmode`` parameter is
    translated to asyncpg's ``ssl``. An explicit ``ssl`` parameter is preserved
    if both are present.

    ``channel_binding`` is rejected: asyncpg cannot accept it as a connection
    argument, and silently dropping it would ignore a requested authentication
    setting. The raised error never includes the connection string.
    """
    database_url = settings.database_url.strip()

    if not database_url:
        return URL.create(
            drivername="postgresql+asyncpg",
            username=settings.postgres_user,
            password=settings.postgres_password,
            host=settings.postgres_host,
            port=settings.postgres_port,
            database=settings.postgres_db,
        )

    url = make_url(database_url)
    query = dict(url.query)

    if "channel_binding" in query:
        # Referenced by name only; the URL is never included so credentials
        # cannot leak into logs or error messages.
        raise ValueError(
            "DATABASE_URL uses the 'channel_binding' parameter, which the "
            "asyncpg driver does not support. Remove 'channel_binding=require' "
            "from the URL and keep 'sslmode=require' to enforce TLS."
        )

    sslmode = query.pop("sslmode", None)
    if sslmode is not None and "ssl" not in query:
        query["ssl"] = sslmode

    return url.set(drivername="postgresql+asyncpg", query=query)
