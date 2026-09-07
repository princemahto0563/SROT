"""
SROT Officer Authentication & Session Management.

Provides secure police authentication gate:
- PBKDF2-HMAC-SHA256 password hashing with random 16-byte salt and 100,000 rounds.
- Constant-time comparison to prevent timing side-channel attacks.
- Token-based session management storing SHA-256 hashed session identifiers.
- Automatic seeding of the demo officer credentials from environment or defaults.
- FastAPI dependency for route protection.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import os
import secrets
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import OfficerSession, OfficerUser, utcnow

ITERATIONS = 100_000
HASH_ALGO = "sha256"


def hash_password(password: str) -> str:
    """Hash password using PBKDF2-HMAC-SHA256 with a random 16-byte salt."""
    salt = os.urandom(16)
    key = hashlib.pbkdf2_hmac(HASH_ALGO, password.encode("utf-8"), salt, ITERATIONS)
    return f"pbkdf2${HASH_ALGO}${ITERATIONS}${salt.hex()}${key.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    """Verify password against stored PBKDF2 hash using constant-time comparison."""
    try:
        parts = stored_hash.split("$")
        if len(parts) != 5 or parts[0] != "pbkdf2" or parts[1] != HASH_ALGO:
            return False
        iterations = int(parts[2])
        salt = bytes.fromhex(parts[3])
        expected_key = bytes.fromhex(parts[4])
        computed_key = hashlib.pbkdf2_hmac(HASH_ALGO, password.encode("utf-8"), salt, iterations)
        return hmac.compare_digest(computed_key, expected_key)
    except Exception:
        return False


def hash_token(raw_token: str) -> str:
    """Hash token for persistent storage so stolen DB dumps don't yield active tokens."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def seed_demo_officer(db: Session) -> OfficerUser:
    """Seed the default demo officer account if not already present."""
    badge_id = os.environ.get("DEMO_OFFICER_BADGE", "DEMO-OFFICER").strip()
    password = os.environ.get("DEMO_OFFICER_PASSWORD", "Forensic#2026!SecOps").strip()
    name = os.environ.get("DEMO_OFFICER_NAME", "Insp. Vikramaditya (Cyber Ops)").strip()
    role = os.environ.get("DEMO_OFFICER_ROLE", "Senior Forensic Investigator").strip()
    unit = os.environ.get("DEMO_OFFICER_UNIT", "Cyber Crime Investigation Unit").strip()

    officer = db.query(OfficerUser).filter(OfficerUser.badge_id == badge_id).first()
    if officer is None:
        officer = OfficerUser(
            badge_id=badge_id,
            name=name,
            role=role,
            unit=unit,
            password_hash=hash_password(password),
            is_active=True,
        )
        db.add(officer)
        db.commit()
        db.refresh(officer)
    else:
        # Update details and ensure password matches configuration
        officer.name = name
        officer.role = role
        officer.unit = unit
        officer.is_active = True
        officer.password_hash = hash_password(password)
        db.commit()
        db.refresh(officer)
    return officer


def create_session(db: Session, officer: OfficerUser, duration_hours: int = 24) -> tuple[str, OfficerSession]:
    """Create a new session for an officer."""
    raw_token = secrets.token_urlsafe(32)
    token_hash = hash_token(raw_token)
    expires_at = utcnow() + dt.timedelta(hours=duration_hours)

    session = OfficerSession(
        token_hash=token_hash,
        officer_id=officer.id,
        expires_at=expires_at,
        is_revoked=False,
    )
    officer.last_login_at = utcnow()
    db.add(session)
    db.commit()
    db.refresh(session)
    return raw_token, session


def validate_session_token(db: Session, raw_token: str) -> Optional[OfficerUser]:
    """Validate a session token and return the associated officer if active and not expired."""
    if not raw_token:
        return None
    token_h = hash_token(raw_token)
    session = (
        db.query(OfficerSession)
        .filter(
            OfficerSession.token_hash == token_h,
            OfficerSession.is_revoked == False,  # noqa: E712
            OfficerSession.expires_at > utcnow(),
        )
        .first()
    )
    if not session:
        return None

    officer = db.query(OfficerUser).filter(OfficerUser.id == session.officer_id, OfficerUser.is_active == True).first()  # noqa: E712
    return officer


def revoke_session_token(db: Session, raw_token: str) -> bool:
    """Revoke a session token."""
    if not raw_token:
        return False
    token_h = hash_token(raw_token)
    session = db.query(OfficerSession).filter(OfficerSession.token_hash == token_h).first()
    if session:
        session.is_revoked = True
        db.commit()
        return True
    return False


def extract_token(request: Request) -> Optional[str]:
    """Extract token from Authorization header or X-Session-Token header."""
    auth_header = request.headers.get("Authorization")
    if auth_header:
        parts = auth_header.strip().split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            return parts[1]
    # Fallback to custom header
    return request.headers.get("X-Session-Token")


def get_current_officer(request: Request, db: Session = Depends(get_db)) -> OfficerUser:
    """FastAPI route dependency ensuring the request has a valid officer session."""
    token = extract_token(request)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Police authorization credentials required to access forensic repository.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    officer = validate_session_token(db, token)
    if not officer:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Officer session expired or invalid. Please re-authenticate.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return officer
