# AgenticArxiv/models/db.py
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from config import settings


class Base(DeclarativeBase):
    pass


engine = create_engine(
    settings.mysql_uri,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
    echo=False,
)

SyncSessionLocal = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)


def get_sync_session() -> Session:
    return SyncSessionLocal()


def init_db():
    """Create all tables (safe to call repeatedly)."""
    import models.orm  # noqa: F401 — ensure all models are registered
    Base.metadata.create_all(bind=engine)
    _add_log_metrics_columns()


def _add_log_metrics_columns() -> None:
    """Add newly introduced log columns for deployments with existing tables."""
    required_columns = {
        "chat_logs": {
            "total_time_ms": "INTEGER NULL",
            "total_llm_ms": "INTEGER NULL",
            "total_tool_ms": "INTEGER NULL",
            "framework_overhead_ms": "INTEGER NULL",
            "prompt_tokens": "INTEGER NULL",
            "completion_tokens": "INTEGER NULL",
            "total_tokens": "INTEGER NULL",
            "termination_type": "VARCHAR(32) NULL",
        },
        "agent_steps": {
            "prompt_tokens": "INTEGER NULL",
            "completion_tokens": "INTEGER NULL",
        },
    }

    inspector = inspect(engine)
    with engine.begin() as connection:
        for table_name, columns in required_columns.items():
            existing = {column["name"] for column in inspector.get_columns(table_name)}
            for column_name, column_type in columns.items():
                if column_name not in existing:
                    statement = f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"
                    connection.execute(text(statement))
