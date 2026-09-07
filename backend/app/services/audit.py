"""Append-only, hash-linked audit chain. Any alteration breaks verification."""
from __future__ import annotations
import datetime as dt
import hashlib, json
from typing import Any
from sqlalchemy.orm import Session
from ..models import AuditLog, utcnow

GENESIS = "0" * 64


def canonical_ts(value: Any) -> str:
    """
    Canonical timestamp string for hashing.

    utcnow() is timezone-aware, but SQLite hands the value back naive. Hashing
    `isoformat()` directly therefore produces one string on write ("...+00:00")
    and a different one on verification — every entry would fail its own digest
    while the prev-hash links still looked intact. Normalise on both paths.
    """
    if isinstance(value, str):
        return value
    if value is None:
        return ""
    if value.tzinfo is not None:
        value = value.astimezone(dt.timezone.utc).replace(tzinfo=None)
    return value.isoformat(timespec="microseconds")


def _digest(prev_hash: str, occurred_at: str, action: str, component: str,
            actor: str, evidence_ref: str | None, evidence_hash: str | None,
            payload: dict[str, Any] | None) -> str:
    blob = json.dumps({
        "prev": prev_hash, "at": occurred_at, "action": action, "component": component,
        "actor": actor, "evidence_ref": evidence_ref, "evidence_hash": evidence_hash,
        "payload": payload or {},
    }, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(blob.encode()).hexdigest()


def record(db: Session, *, case_id: int, action: str, component: str,
           evidence_ref: str | None = None, evidence_hash: str | None = None,
           payload: dict[str, Any] | None = None, actor: str = "system") -> AuditLog:
    last = (db.query(AuditLog).filter(AuditLog.case_id == case_id)
            .order_by(AuditLog.id.desc()).first())
    prev = last.current_hash if last else GENESIS
    at = utcnow()
    cur = _digest(prev, canonical_ts(at), action, component, actor,
                  evidence_ref, evidence_hash, payload)
    row = AuditLog(case_id=case_id, evidence_ref=evidence_ref, occurred_at=at,
                   action=action, component=component, actor=actor,
                   payload_json=payload or {}, evidence_hash=evidence_hash,
                   prev_hash=prev, current_hash=cur)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def verify_chain(db: Session, case_id: int) -> dict[str, Any]:
    rows = (db.query(AuditLog).filter(AuditLog.case_id == case_id)
            .order_by(AuditLog.id.asc()).all())
    prev = GENESIS
    for r in rows:
        expected = _digest(prev, canonical_ts(r.occurred_at), r.action, r.component,
                           r.actor, r.evidence_ref, r.evidence_hash, r.payload_json)
        if r.prev_hash != prev:
            return {"verified": False, "entries": len(rows), "broken_at_id": r.id,
                    "reason": "link",
                    "message": f"Audit chain integrity failure at entry {r.id}: the entry does "
                               f"not link to the preceding entry (insertion or deletion)."}
        if r.current_hash != expected:
            return {"verified": False, "entries": len(rows), "broken_at_id": r.id,
                    "reason": "content",
                    "message": f"Audit chain integrity failure at entry {r.id}: the recorded "
                               f"content no longer matches its stored digest (alteration)."}
        prev = r.current_hash
    return {"verified": True, "entries": len(rows), "broken_at_id": None, "reason": None,
            "message": f"Audit chain verified — {len(rows)} entries, no discontinuity detected."}
