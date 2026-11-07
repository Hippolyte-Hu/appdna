from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.models import Base

settings = get_settings()
settings.data_dir
engine = create_engine(
    f"sqlite:///{settings.database_path}",
    connect_args={"check_same_thread": False},
)


@event.listens_for(engine, "connect")
def _enable_wal(dbapi_connection, _connection_record) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def init_db() -> None:
    Base.metadata.create_all(engine)


def session_scope() -> Session:
    return SessionLocal()
