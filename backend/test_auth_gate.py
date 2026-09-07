"""
Automated validation suite for SROT Police Authentication Gate.

Tests:
1. Unauthenticated requests to protected endpoints return HTTP 401 with WWW-Authenticate header.
2. Health check (/api/health) remains publicly accessible with HTTP 200.
3. Invalid badge ID or password returns HTTP 401.
4. Correct demo credentials authenticate successfully and return session token.
5. Session verification (/api/auth/session) returns officer profile.
6. Authenticated requests with Bearer token succeed with HTTP 200.
7. Logout invalidates session token; subsequent requests return HTTP 401.
"""
import requests

BASE_URL = "http://127.0.0.1:8077/api"
DEMO_BADGE = "DEMO-OFFICER"
DEMO_PASSWORD = "Forensic#2026!SecOps"


def test_public_health():
    res = requests.get(f"{BASE_URL}/health")
    assert res.status_code == 200, f"Expected 200 from health, got {res.status_code}"
    data = res.json()
    assert data.get("status") == "ok"
    print("PASS: /api/health is publicly accessible (HTTP 200)")


def test_unauthenticated_protected_endpoints():
    protected_paths = [
        "/cases",
        "/cases/CASE-2026-001",
        "/benchmark/adversarial-summary",
        "/auth/session",
    ]
    for path in protected_paths:
        res = requests.get(f"{BASE_URL}{path}")
        assert res.status_code == 401, f"Expected 401 for {path}, got {res.status_code}"
        assert "Bearer" in res.headers.get("www-authenticate", ""), f"Missing WWW-Authenticate on {path}"
        data = res.json()
        assert "detail" in data, f"Expected detail in 401 response for {path}"
    print("PASS: Unauthenticated requests to protected endpoints return HTTP 401")


def test_invalid_login():
    # Empty credentials
    res = requests.post(f"{BASE_URL}/auth/login", json={"badge_id": "", "password": ""})
    assert res.status_code == 401, f"Expected 401 for empty credentials, got {res.status_code}"

    # Invalid badge
    res = requests.post(f"{BASE_URL}/auth/login", json={"badge_id": "UNKNOWN-OFFICER", "password": "any"})
    assert res.status_code == 401, f"Expected 401 for unknown badge, got {res.status_code}"

    # Invalid password
    res = requests.post(f"{BASE_URL}/auth/login", json={"badge_id": DEMO_BADGE, "password": "WrongPassword123!"})
    assert res.status_code == 401, f"Expected 401 for wrong password, got {res.status_code}"
    print("PASS: Invalid login attempts correctly rejected (HTTP 401)")


def test_login_and_authenticated_flow():
    # 1. Login with demo credentials
    res = requests.post(f"{BASE_URL}/auth/login", json={"badge_id": DEMO_BADGE, "password": DEMO_PASSWORD})
    assert res.status_code == 200, f"Expected 200 for valid login, got {res.status_code}: {res.text}"
    body = res.json()
    token = body.get("token")
    assert token, "Login did not return a session token"
    officer = body.get("officer", {})
    assert officer.get("badge_id") == DEMO_BADGE
    assert officer.get("name")
    assert "last_login_at" in officer
    print(f"PASS: Demo officer login succeeded for {officer['name']} (Badge: {officer['badge_id']})")

    # 2. Check session endpoint with token
    headers = {"Authorization": f"Bearer {token}"}
    res_session = requests.get(f"{BASE_URL}/auth/session", headers=headers)
    assert res_session.status_code == 200, f"Expected 200 for session check, got {res_session.status_code}"
    session_data = res_session.json()
    assert session_data.get("authenticated") is True
    assert session_data.get("officer", {}).get("badge_id") == DEMO_BADGE
    print("PASS: Session verification endpoint validates active token")

    # 3. Access protected resource with token
    res_cases = requests.get(f"{BASE_URL}/cases", headers=headers)
    assert res_cases.status_code == 200, f"Expected 200 for /cases with token, got {res_cases.status_code}"
    cases = res_cases.json()
    assert isinstance(cases, list), "Expected cases list"
    print(f"PASS: Protected endpoint accessible with Bearer token ({len(cases)} cases retrieved)")

    # 4. Logout and verify token revocation
    res_logout = requests.post(f"{BASE_URL}/auth/logout", headers=headers)
    assert res_logout.status_code == 200, f"Expected 200 for logout, got {res_logout.status_code}"
    print("PASS: Officer logout succeeded")

    # 5. Verify revoked token cannot access protected endpoint
    res_revoked = requests.get(f"{BASE_URL}/cases", headers=headers)
    assert res_revoked.status_code == 401, f"Expected 401 for revoked token, got {res_revoked.status_code}"
    print("PASS: Revoked token rejected with HTTP 401")


if __name__ == "__main__":
    print("=" * 60)
    print("RUNNING SROT POLICE AUTHENTICATION GATE TEST SUITE")
    print("=" * 60)
    test_public_health()
    test_unauthenticated_protected_endpoints()
    test_invalid_login()
    test_login_and_authenticated_flow()
    print("=" * 60)
    print("ALL AUTHENTICATION GATE TESTS PASSED!")
    print("=" * 60)
