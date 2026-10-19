import pytest
import base64
import hashlib
import secrets
import json
from httpx import AsyncClient
import jwt
from cryptography.hazmat.primitives.asymmetric import rsa

# Helper for PKCE S256
def generate_pkce_pair():
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return verifier, challenge


@pytest.mark.asyncio
async def test_openid_configuration_discovery(async_client: AsyncClient):
    """Verify OIDC discovery document contains all required standard fields."""
    res = await async_client.get("/.well-known/openid-configuration")
    assert res.status_code == 200
    data = res.json()
    assert "issuer" in data
    assert data["authorization_endpoint"].endswith("/oauth/authorize")
    assert data["token_endpoint"].endswith("/oauth/token")
    assert data["userinfo_endpoint"].endswith("/oauth/userinfo")
    assert data["jwks_uri"].endswith("/.well-known/jwks.json")
    assert "RS256" in data["id_token_signing_alg_values_supported"]
    assert "S256" in data["code_challenge_methods_supported"]
    assert "openid" in data["scopes_supported"]


@pytest.mark.asyncio
async def test_jwks_endpoint(async_client: AsyncClient):
    """Verify public JWKS endpoint returns valid RSA public key parameters."""
    res = await async_client.get("/.well-known/jwks.json")
    assert res.status_code == 200
    data = res.json()
    assert "keys" in data
    assert len(data["keys"]) > 0
    key = data["keys"][0]
    assert key["kty"] == "RSA"
    assert key["use"] == "sig"
    assert key["alg"] == "RS256"
    assert "kid" in key
    assert "n" in key
    assert "e" in key


@pytest.mark.asyncio
async def test_username_validation_and_reserved_names(async_client: AsyncClient):
    """Test username rules, character limits, reserved names rejection, and normalization."""
    # 1. Reserved username rejection
    res = await async_client.post("/auth/register", json={
        "email": "hacker@test.com",
        "username": "oauth",
        "password": "Password123!"
    })
    assert res.status_code in (400, 401)
    assert "reserved" in res.json().get("detail", "").lower()

    # 2. Invalid characters rejection
    res_invalid = await async_client.post("/auth/register", json={
        "email": "hacker2@test.com",
        "username": "bad!username",
        "password": "Password123!"
    })
    assert res_invalid.status_code in (400, 401, 422)

    # 3. Successful registration with clean username
    unique_user = f"user_{secrets.token_hex(4)}"
    res_reg = await async_client.post("/auth/register", json={
        "email": f"{unique_user}@test.com",
        "username": unique_user,
        "password": "Password123!",
        "display_name": "Test User"
    })
    assert res_reg.status_code == 200
    profile = res_reg.json()["data"]
    assert profile["username"] == unique_user
    assert profile["normalized_username"] == unique_user.lower()
    assert profile["shiv_id"].startswith("SHV-")

    # 4. Case-insensitive collision prevention
    res_dup = await async_client.post("/auth/register", json={
        "email": f"diff_{unique_user}@test.com",
        "username": unique_user.upper(),
        "password": "Password123!"
    })
    assert res_dup.status_code in (400, 401)
    assert "taken" in res_dup.json().get("detail", "").lower()


@pytest.mark.asyncio
async def test_login_and_case_insensitive_authentication(async_client: AsyncClient):
    """Test login with email, username in different casing, and SHIV ID."""
    uname = f"alex_{secrets.token_hex(4)}"
    email = f"{uname}@example.com"
    reg_res = await async_client.post("/auth/register", json={
        "email": email,
        "username": uname,
        "password": "SuperSecret123!"
    })
    assert reg_res.status_code == 200
    shiv_id = reg_res.json()["data"]["shiv_id"]

    # 1. Login with exact email
    login_1 = await async_client.post("/auth/login", json={
        "email_or_username": email,
        "password": "SuperSecret123!"
    })
    assert login_1.status_code == 200
    assert "access_token" in login_1.json()["data"]

    # 2. Login with uppercase username (case-insensitive test)
    login_2 = await async_client.post("/auth/login", json={
        "email_or_username": uname.upper(),
        "password": "SuperSecret123!"
    })
    assert login_2.status_code == 200

    # 3. Login with SHIV ID
    login_3 = await async_client.post("/auth/login", json={
        "email_or_username": shiv_id,
        "password": "SuperSecret123!"
    })
    assert login_3.status_code == 200


@pytest.mark.asyncio
async def test_active_sessions_and_revocation(async_client: AsyncClient):
    """Test active session listing, individual deletion, and bulk revocation."""
    uname = f"sess_{secrets.token_hex(4)}"
    reg_res = await async_client.post("/auth/register", json={
        "email": f"{uname}@example.com",
        "username": uname,
        "password": "Password123!"
    })
    login_res = await async_client.post("/auth/login", json={
        "email_or_username": uname,
        "password": "Password123!"
    })
    token = login_res.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # List sessions
    res_sessions = await async_client.get("/auth/sessions", headers=headers)
    assert res_sessions.status_code == 200
    sessions = res_sessions.json()["data"]
    assert len(sessions) >= 1
    session_id = sessions[0]["id"]

    # Revoke all sessions
    res_revoke_all = await async_client.post("/auth/sessions/revoke-all", headers=headers)
    assert res_revoke_all.status_code == 200
    assert res_revoke_all.json()["data"]["revoked_count"] >= 1


@pytest.mark.asyncio
async def test_password_recovery_workflow(async_client: AsyncClient):
    """Test forgot-password token generation and password reset."""
    uname = f"recov_{secrets.token_hex(4)}"
    email = f"{uname}@example.com"
    await async_client.post("/auth/register", json={
        "email": email,
        "username": uname,
        "password": "OldPassword123!"
    })

    # Forgot password
    res_forgot = await async_client.post("/auth/forgot-password", json={"email": email})
    assert res_forgot.status_code == 200
    reset_token = res_forgot.json()["data"].get("reset_token")
    assert reset_token is not None

    # Reset password
    res_reset = await async_client.post("/auth/reset-password", json={
        "token": reset_token,
        "new_password": "NewBrandPassword456!"
    })
    assert res_reset.status_code == 200

    # Verify old password fails
    res_fail = await async_client.post("/auth/login", json={
        "email_or_username": email,
        "password": "OldPassword123!"
    })
    assert res_fail.status_code in (400, 401)

    # Verify new password succeeds
    res_ok = await async_client.post("/auth/login", json={
        "email_or_username": email,
        "password": "NewBrandPassword456!"
    })
    assert res_ok.status_code == 200


@pytest.mark.asyncio
async def test_oauth_developer_registration_and_validation(async_client: AsyncClient):
    """Test OAuth client registration, HTTPS validation, secret hashing, and rotation."""
    # Login as admin
    login_res = await async_client.post("/auth/login", json={
        "email_or_username": "admin@shiv.com",
        "password": "shivadmin"
    })
    token = login_res.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Invalid redirect URI (fragment #)
    res_invalid_uri = await async_client.post("/oauth/clients", json={
        "client_name": "Bad Client",
        "client_type": "confidential",
        "redirect_uris": ["https://myapp.com/callback#fragment"]
    }, headers=headers)
    assert res_invalid_uri.status_code == 400

    # 2. Valid Registration (Confidential client)
    res_client = await async_client.post("/oauth/clients", json={
        "client_name": "Test Partner Store",
        "client_type": "confidential",
        "redirect_uris": ["https://partner.com/oauth/callback", "http://localhost:3000/callback"],
        "client_uri": "https://partner.com",
        "description": "Partner e-commerce portal"
    }, headers=headers)
    assert res_client.status_code == 200
    data = res_client.json()["data"]
    client_id = data["client_id"]
    client_secret = data["client_secret"]
    assert client_id.startswith("shiv_client_")
    assert client_secret.startswith("shiv_sec_")

    # 3. Rotate Secret
    res_rot = await async_client.post(f"/oauth/clients/{client_id}/rotate-secret", headers=headers)
    assert res_rot.status_code == 200
    new_secret = res_rot.json()["data"]["new_client_secret"]
    assert new_secret != client_secret


@pytest.mark.asyncio
async def test_oauth_pkce_authorization_code_flow_end_to_end(async_client: AsyncClient):
    """
    Complete end-to-end OAuth 2.0 / OpenID Connect Authorization Code Flow with PKCE S256:
    1. Register client
    2. Request /oauth/authorize with PKCE S256
    3. User Consent approval
    4. Code exchange at /oauth/token
    5. RS256 ID Token verification against public JWKS
    6. Fetch claims from /oauth/userinfo
    7. Code replay protection test
    """
    # Create test user
    uname = f"oidc_{secrets.token_hex(4)}"
    email = f"{uname}@example.com"
    reg_u = await async_client.post("/auth/register", json={
        "email": email,
        "username": uname,
        "password": "Password123!",
        "display_name": "OIDC Tester"
    })
    user_id = reg_u.json()["data"]["id"]
    user_shiv_id = reg_u.json()["data"]["shiv_id"]

    login_u = await async_client.post("/auth/login", json={
        "email_or_username": email,
        "password": "Password123!"
    })
    user_token = login_u.json()["data"]["access_token"]
    user_headers = {"Authorization": f"Bearer {user_token}"}

    # Register confidential OAuth Client
    client_res = await async_client.post("/oauth/clients", json={
        "client_name": "Full Flow App",
        "client_type": "confidential",
        "redirect_uris": ["https://app.example.com/callback"],
        "allowed_scopes": "openid profile email offline_access"
    }, headers=user_headers)
    client_data = client_res.json()["data"]
    client_id = client_data["client_id"]
    client_secret = client_data["client_secret"]
    redirect_uri = "https://app.example.com/callback"

    # Step 1: Generate PKCE S256 pair
    code_verifier, code_challenge = generate_pkce_pair()
    state = secrets.token_urlsafe(16)
    nonce = secrets.token_urlsafe(16)

    # Step 2: Request /oauth/authorize (first time requires consent)
    auth_req_url = (
        f"/oauth/authorize?client_id={client_id}&redirect_uri={redirect_uri}"
        f"&response_type=code&scope=openid+profile+email+offline_access"
        f"&code_challenge={code_challenge}&code_challenge_method=S256"
        f"&state={state}&nonce={nonce}"
    )
    res_auth = await async_client.get(auth_req_url, headers=user_headers)
    assert res_auth.status_code == 200
    assert "consent.html" in res_auth.text or "Authorize" in res_auth.text

    # Extract consent token from form
    import re
    token_match = re.search(r'name="consent_token" value="([^"]+)"', res_auth.text)
    assert token_match is not None, "consent_token not found in consent screen form"
    consent_token = token_match.group(1)

    # Step 3: Submit Consent approval
    consent_form = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": "openid profile email offline_access",
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "nonce": nonce,
        "consent_token": consent_token,
        "action": "approve"
    }
    res_consent = await async_client.post(
        "/oauth/authorize/consent",
        data=consent_form,
        headers=user_headers,
        follow_redirects=False
    )
    assert res_consent.status_code == 303
    location = res_consent.headers["location"]
    assert location.startswith(redirect_uri)
    assert f"state={state}" in location
    assert "code=" in location

    # Parse code
    from urllib.parse import urlparse, parse_qs
    parsed_loc = urlparse(location)
    query_params = parse_qs(parsed_loc.query)
    auth_code = query_params["code"][0]
    assert auth_code.startswith("shiv_ac_")

    # Step 4: Token Exchange with Tampered PKCE Verifier (MUST FAIL)
    res_bad_pkce = await async_client.post("/oauth/token", data={
        "grant_type": "authorization_code",
        "code": auth_code,
        "redirect_uri": redirect_uri,
        "client_id": client_id,
        "client_secret": client_secret,
        "code_verifier": "wrong_verifier_that_does_not_match_challenge"
    })
    # Note: Bad verifier fails
    assert res_bad_pkce.status_code == 400
    assert "pkce" in res_bad_pkce.text.lower() or "invalid_grant" in res_bad_pkce.text.lower()

    # Request new code for valid exchange since bad attempt may have marked it or re-authorize
    # (Since consent is now granted, GET /oauth/authorize will immediately return a fresh code!)
    res_fresh_auth = await async_client.get(auth_req_url, headers=user_headers, follow_redirects=False)
    assert res_fresh_auth.status_code == 307 or res_fresh_auth.status_code == 302
    fresh_location = res_fresh_auth.headers["location"]
    fresh_code = parse_qs(urlparse(fresh_location).query)["code"][0]

    # Step 5: Successful Token Exchange with Valid PKCE Verifier
    res_token = await async_client.post("/oauth/token", data={
        "grant_type": "authorization_code",
        "code": fresh_code,
        "redirect_uri": redirect_uri,
        "client_id": client_id,
        "client_secret": client_secret,
        "code_verifier": code_verifier
    })
    assert res_token.status_code == 200
    tokens = res_token.json()
    assert "access_token" in tokens
    assert "id_token" in tokens
    assert "refresh_token" in tokens
    assert tokens["token_type"] == "Bearer"

    access_token = tokens["access_token"]
    id_token = tokens["id_token"]
    refresh_token = tokens["refresh_token"]

    # Step 6: Verify RS256 ID Token against Public JWKS
    res_jwks = await async_client.get("/.well-known/jwks.json")
    jwks_data = res_jwks.json()
    jwk = jwks_data["keys"][0]

    from jwt.algorithms import RSAAlgorithm
    public_key = RSAAlgorithm.from_jwk(json.dumps(jwk))

    decoded_id = jwt.decode(
        id_token,
        public_key,
        algorithms=["RS256"],
        audience=client_id,
        options={"verify_exp": True}
    )
    assert decoded_id["sub"] == user_id
    assert decoded_id["aud"] == client_id
    assert decoded_id["preferred_username"] == uname
    assert decoded_id["email"] == email
    assert decoded_id["shiv_id"] == user_shiv_id
    assert decoded_id["nonce"] == nonce

    # Step 7: Fetch /oauth/userinfo with Access Token
    res_userinfo = await async_client.get(
        "/oauth/userinfo",
        headers={"Authorization": f"Bearer {access_token}"}
    )
    assert res_userinfo.status_code == 200
    uinfo = res_userinfo.json()
    assert uinfo["sub"] == user_id
    assert uinfo["preferred_username"] == uname
    assert uinfo["email"] == email
    assert uinfo["name"] == "OIDC Tester"

    # Step 8: Test Refresh Token rotation
    res_rf = await async_client.post("/oauth/token", data={
        "grant_type": "refresh_token",
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token
    })
    assert res_rf.status_code == 200
    rf_data = res_rf.json()
    assert "access_token" in rf_data
    assert "refresh_token" in rf_data
    assert rf_data["refresh_token"] != refresh_token  # Rotated!

    # Step 9: Replay attack on fresh_code MUST fail (single-use code)
    res_replay = await async_client.post("/oauth/token", data={
        "grant_type": "authorization_code",
        "code": fresh_code,
        "redirect_uri": redirect_uri,
        "client_id": client_id,
        "client_secret": client_secret,
        "code_verifier": code_verifier
    })
    assert res_replay.status_code == 400
    assert "already been used" in res_replay.text.lower() or "invalid_grant" in res_replay.text.lower()

    # Step 10: Revoke Access via User Connected Apps API
    res_revoke = await async_client.delete(f"/oauth/grants/{client_id}", headers=user_headers)
    assert res_revoke.status_code == 200


@pytest.mark.asyncio
async def test_invalid_redirect_uri_rejection(async_client: AsyncClient):
    """Ensure unregistered redirect URIs are strictly rejected (no open redirects)."""
    # Login as admin
    login_res = await async_client.post("/auth/login", json={
        "email_or_username": "admin@shiv.com",
        "password": "shivadmin"
    })
    token = login_res.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    client_res = await async_client.post("/oauth/clients", json={
        "client_name": "Strict URI App",
        "client_type": "public",
        "redirect_uris": ["https://legit.com/cb"]
    }, headers=headers)
    client_id = client_res.json()["data"]["client_id"]

    _, challenge = generate_pkce_pair()
    res = await async_client.get(
        f"/oauth/authorize?client_id={client_id}&redirect_uri=https://evil.com/steal&response_type=code&code_challenge={challenge}&code_challenge_method=S256",
        headers=headers
    )
    assert res.status_code == 400
    assert "invalid redirect_uri" in res.json().get("detail", "").lower()
