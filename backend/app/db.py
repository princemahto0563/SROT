"""SQLite + SQLAlchemy setup. Single file DB, zero external infrastructure."""
from __future__ import annotations
import os
from pathlib import Path
from sqlalchemy import create_engine
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
    connect_args={"check_same_thread": False},
    future=True,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from . import models  # noqa: F401  (register mappers)
    Base.metadata.create_all(engine)
