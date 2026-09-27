"""SQLite + SQLAlchemy setup. Single file DB, zero external infrastructure."""
from __future__ import annotations
import os
from pathlib import Path
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, DeclarativeBase

BASE_DIR = Path(os.environ.get("SROT_DATA", Path(__file__).resolve().parents[2] / "data"))
BASE_DIR.mkdir(parents=True, exist_ok=True)
EVIDENCE_DIR = BASE_DIR / "evidence"      # originals — never modified
WORK_DIR = BASE_DIR / "work"              # derived artefacts (frames, variants)
CORPUS_DIR = BASE_DIR / "corpus"          # synthetic reference corpus media
PACKET_DIR = BASE_DIR / "packets"
for d in (EVIDENCE_DIR, WORK_DIR, CORPUS_DIR, PACKET_DIR):
    d.mkdir(parents=True, exist_ok=True)

DB_PATH = BASE_DIR / "srot.db"
engine = create_engine(
    f"sqlite:///{DB_PATH}",
    connect_args={"check_same_thread": False, "timeout": 30},
    future=True,
)


@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA busy_timeout = 30000")
        cursor.execute("PRAGMA journal_mode = WAL")
    except Exception:
        pass
    finally:
        cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    pass


def resolve_data_path(raw: str | Path | None) -> Path:
    """
    Canonical data path resolver for all SROT assets (evidence, work, corpus, packets).
    Handles relative SROT_DATA paths, legacy absolute paths from other machines/Docker/macOS,
    and safely re-roots them to the active BASE_DIR. Enforces path traversal protection.
    """
    active_base = Path(os.environ.get("SROT_DATA", BASE_DIR))
    if not raw:
        return active_base / "evidence" / "nonexistent"

    p = Path(raw)

    # 1. Existing absolute path (legacy compatibility when file is present on disk)
    if p.is_absolute() and p.exists():
        return p

    raw_str = str(raw)
    raw_normalized = raw_str.replace("\\", "/")
    base_resolved = active_base.resolve()

    # 2. Look for known SROT data subdirectories and re-root
    for folder in ("evidence/", "work/", "corpus/", "packets/"):
        if folder in raw_normalized:
            rel_sub = raw_normalized[raw_normalized.index(folder):]
            candidate = (active_base / rel_sub).resolve()
            if not str(candidate).startswith(str(base_resolved)):
                raise ValueError(f"Path traversal detected: {raw}")
            return candidate

    # 3. Relative path under active DATA_DIR
    clean_rel = raw_normalized.lstrip("/\\")
    if p.is_absolute():
        clean_rel = p.name
    candidate = (active_base / clean_rel).resolve()
    if not str(candidate).startswith(str(base_resolved)):
        raise ValueError(f"Path traversal detected: {raw}")
    return candidate


def get_evidence_path(ev: Any) -> Path:
    """
    Canonical evidence path resolver.
    Handles legacy absolute paths, relative SROT_DATA paths, and re-roots
    historical paths when running in containers or moved data directories.
    Enforces path traversal protection.
    """
    if hasattr(ev, "stored_path"):
        raw = ev.stored_path
    elif isinstance(ev, (str, Path)):
        raw = str(ev)
    else:
        raise TypeError(f"Expected Evidence, str, or Path, got {type(ev)}")

    return resolve_data_path(raw)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from . import models  # noqa: F401  (register mappers)
    Base.metadata.create_all(engine)
    _migrate_columns()


def _migrate_columns() -> None:
    """Safely adds missing columns to existing SQLite tables if they do not exist."""
    with engine.connect() as conn:
        try:
            res = conn.exec_driver_sql("PRAGMA table_info(evidence)").fetchall()
            existing_cols = {row[1] for row in res}
            cols_to_add = [
                ("forensic_role", "VARCHAR DEFAULT 'UNKNOWN'"),
                ("reference_evidence_id", "INTEGER"),
                ("source_platform", "VARCHAR"),
                ("source_account", "VARCHAR"),
                ("source_post_id", "VARCHAR"),
                ("source_url", "VARCHAR"),
                ("source_observed_at", "DATETIME"),
                ("source_timezone", "VARCHAR"),
                ("collection_at", "DATETIME"),
                ("classification_basis", "TEXT"),
            ]
            for col_name, col_def in cols_to_add:
                if col_name not in existing_cols:
                    conn.exec_driver_sql(f"ALTER TABLE evidence ADD COLUMN {col_name} {col_def}")
            conn.commit()
        except Exception:
            pass
