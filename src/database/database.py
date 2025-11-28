"""Database connection and session management."""

import os
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Generator, Optional

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from src.models.base import Base


@dataclass
class DatabaseConfig:
    """Database configuration settings."""
    
    host: str = "localhost"
    port: int = 5432
    database: str = "embi"
    username: str = "postgres"
    password: str = ""
    pool_size: int = 5
    max_overflow: int = 10
    echo: bool = False
    
    @classmethod
    def from_env(cls) -> "DatabaseConfig":
        """Create config from environment variables."""
        return cls(
            host=os.getenv("DB_HOST", "localhost"),
            port=int(os.getenv("DB_PORT", "5432")),
            database=os.getenv("DB_NAME", "embi"),
            username=os.getenv("DB_USER", "postgres"),
            password=os.getenv("DB_PASSWORD", ""),
            pool_size=int(os.getenv("DB_POOL_SIZE", "5")),
            max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "10")),
            echo=os.getenv("DB_ECHO", "false").lower() == "true",
        )
    
    @property
    def url(self) -> str:
        """Generate SQLAlchemy database URL."""
        return f"postgresql://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"


# Module-level engine and session factory (initialized lazily)
_engine: Optional[Engine] = None
_session_factory: Optional[sessionmaker[Session]] = None


def get_engine(config: Optional[DatabaseConfig] = None) -> Engine:
    """
    Get or create the SQLAlchemy engine.
    
    Uses singleton pattern to reuse engine across requests.
    """
    global _engine
    
    if _engine is None:
        if config is None:
            config = DatabaseConfig.from_env()
        
        _engine = create_engine(
            config.url,
            pool_size=config.pool_size,
            max_overflow=config.max_overflow,
            echo=config.echo,
            pool_pre_ping=True,  # Verify connections before use
        )
    
    return _engine


def get_session_factory(config: Optional[DatabaseConfig] = None) -> sessionmaker[Session]:
    """
    Get or create the session factory.
    
    Uses singleton pattern to reuse factory across requests.
    """
    global _session_factory
    
    if _session_factory is None:
        engine = get_engine(config)
        _session_factory = sessionmaker(
            bind=engine,
            autocommit=False,
            autoflush=False,
            expire_on_commit=False,
        )
    
    return _session_factory


def get_db() -> Generator[Session, None, None]:
    """
    Dependency that provides a database session.
    
    Use with FastAPI's Depends() for automatic session management.
    Commits on success, rolls back on exception.
    """
    session_factory = get_session_factory()
    session = session_factory()
    
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@contextmanager
def get_db_context() -> Generator[Session, None, None]:
    """
    Context manager for database sessions outside of FastAPI.
    
    Useful for scripts, migrations, and background tasks.
    """
    session_factory = get_session_factory()
    session = session_factory()
    
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db(config: Optional[DatabaseConfig] = None) -> None:
    """
    Initialize database by creating all tables.
    
    Should only be used in development/testing.
    Use Alembic migrations for production.
    """
    engine = get_engine(config)
    Base.metadata.create_all(bind=engine)


def dispose_engine() -> None:
    """
    Dispose of the engine and reset module state.
    
    Useful for testing and graceful shutdown.
    """
    global _engine, _session_factory
    
    if _engine is not None:
        _engine.dispose()
        _engine = None
        _session_factory = None

