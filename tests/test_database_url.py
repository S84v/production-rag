import pytest
from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import create_async_engine

from production_rag.core.settings import Settings
from production_rag.db.url import build_database_url


def test_blank_database_url_falls_back_to_postgres_settings():
    settings = Settings(
        _env_file=None,
        database_url="",
        postgres_user="local_user",
        postgres_password="local_password",
        postgres_db="local_db",
        postgres_host="db.internal",
        postgres_port=6543,
    )

    url = build_database_url(settings)

    assert isinstance(url, URL)
    assert url.drivername == "postgresql+asyncpg"
    assert url.username == "local_user"
    assert url.password == "local_password"
    assert url.host == "db.internal"
    assert url.port == 6543
    assert url.database == "local_db"


def test_blank_database_url_treats_whitespace_as_unset():
    settings = Settings(
        _env_file=None,
        database_url="   ",
        postgres_host="localhost",
    )

    url = build_database_url(settings)

    assert url.drivername == "postgresql+asyncpg"
    assert url.host == "localhost"


def test_database_url_takes_precedence_over_postgres_settings():
    settings = Settings(
        _env_file=None,
        database_url=(
            "postgresql://hosted_user:hosted_password@ep-example.neon.tech/hosted_db"
        ),
        postgres_user="local_user",
        postgres_host="localhost",
        postgres_db="local_db",
    )

    url = build_database_url(settings)

    assert url.drivername == "postgresql+asyncpg"
    assert url.username == "hosted_user"
    assert url.host == "ep-example.neon.tech"
    assert url.database == "hosted_db"


@pytest.mark.parametrize("scheme", ["postgresql", "postgres"])
def test_plain_schemes_are_normalized_to_asyncpg(scheme: str):
    settings = Settings(_env_file=None, database_url=f"{scheme}://user:pass@host/db")

    url = build_database_url(settings)

    assert url.drivername == "postgresql+asyncpg"
    assert url.host == "host"


def test_already_normalized_url_is_unchanged():
    settings = Settings(
        _env_file=None,
        database_url="postgresql+asyncpg://user:pass@host/db",
    )

    url = build_database_url(settings)

    assert url.drivername == "postgresql+asyncpg"
    assert url.host == "host"
    assert dict(url.query) == {}


def test_neon_sslmode_is_translated_to_asyncpg_ssl():
    settings = Settings(
        _env_file=None,
        database_url="postgresql://user:pass@ep-example.neon.tech/db?sslmode=require",
    )

    url = build_database_url(settings)

    assert dict(url.query) == {"ssl": "require"}

    # The normalized URL yields asyncpg-compatible connect arguments. This does
    # not open a connection.
    engine = create_async_engine(url)
    _, connect_args = engine.dialect.create_connect_args(engine.url)

    assert connect_args["ssl"] == "require"
    assert "sslmode" not in connect_args


def test_channel_binding_is_rejected_with_actionable_error():
    settings = Settings(
        _env_file=None,
        database_url=(
            "postgresql://neon_user:neon_secret@ep-example.neon.tech/db"
            "?sslmode=require&channel_binding=require"
        ),
    )

    with pytest.raises(ValueError) as excinfo:
        build_database_url(settings)

    message = str(excinfo.value)

    assert "channel_binding" in message
    assert "asyncpg" in message
    assert "sslmode=require" in message
    # The error must never include any part of the connection string.
    assert "neon_secret" not in message
    assert "neon_user" not in message
    assert "ep-example.neon.tech" not in message


@pytest.mark.parametrize("sslmode", ["require", "verify-ca", "verify-full"])
def test_sslmode_values_are_passed_through(sslmode: str):
    settings = Settings(
        _env_file=None,
        database_url=f"postgresql://user:pass@host/db?sslmode={sslmode}",
    )

    url = build_database_url(settings)

    assert dict(url.query) == {"ssl": sslmode}


def test_explicit_ssl_is_preserved_when_sslmode_also_present():
    settings = Settings(
        _env_file=None,
        database_url="postgresql://user:pass@host/db?sslmode=require&ssl=verify-full",
    )

    url = build_database_url(settings)

    assert dict(url.query) == {"ssl": "verify-full"}


def test_reserved_characters_in_password_round_trip():
    settings = Settings(
        _env_file=None,
        database_url="",
        postgres_user="user",
        postgres_password="p@ss/w:rd",
        postgres_db="db",
        postgres_host="localhost",
        postgres_port=5432,
    )

    url = build_database_url(settings)
    engine = create_async_engine(url)
    _, connect_args = engine.dialect.create_connect_args(engine.url)

    assert connect_args["password"] == "p@ss/w:rd"


def test_password_is_masked_when_rendered():
    settings = Settings(
        _env_file=None,
        database_url="postgresql://user:supersecret@host/db",
    )

    url = build_database_url(settings)

    assert "supersecret" not in str(url)
    assert "***" in str(url)
