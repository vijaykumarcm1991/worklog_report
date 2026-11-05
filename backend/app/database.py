"""Database engine, session and init."""
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from .config import get_settings

settings = get_settings()

_is_sqlite = settings.database_url.startswith("sqlite")

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False, "timeout": 30} if _is_sqlite else {},
)

if _is_sqlite:

    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_conn, _record):  # noqa: ANN001
        # SQLite ignores ON DELETE CASCADE unless foreign keys are switched on
        # for every connection.
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    from . import models

    models.Base.metadata.create_all(bind=engine)

    # Remove rows orphaned before foreign keys were enforced (deleted
    # instances/users whose data was left behind).
    db = SessionLocal()
    try:
        instance_ids = db.query(models.Instance.id)
        db.query(models.User).filter(~models.User.instance_id.in_(instance_ids)).delete(
            synchronize_session=False
        )
        db.query(models.Worklog).filter(~models.Worklog.instance_id.in_(instance_ids)).delete(
            synchronize_session=False
        )
        db.commit()
    finally:
        db.close()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
