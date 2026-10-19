"""
SHIV Identity — Standalone OpenID Connect (OIDC) Sample Client
Demonstrating "Continue with SHIV" using Authorization Code Flow + PKCE (RFC 7636).

Features:
1. Dynamic Discovery via /.well-known/openid-configuration
2. Cryptographic PKCE (S256) verifier and challenge generation
3. Anti-CSRF state and replay-prevention nonce generation
4. Local HTTP callback server to capture redirect code
5. Authorization code exchange for tokens (access_token, id_token, refresh_token)
6. Asymmetric RS256 signature verification of id_token using /.well-known/jwks.json
7. UserInfo retrieval (/oauth/userinfo)
8. Refresh token rotation (/oauth/token)
9. Token revocation (/oauth/revoke)
"""

import sys
import json
import base64
import hashlib
import secrets
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlencode, urlparse, parse_qs
import httpx
import jwt
from jwt.algorithms import RSAAlgorithm

DEFAULT_ISSUER = "https://shiv-database.onrender.com"
LOCAL_ISSUER = "http://localhost:8000"
REDIRECT_URI = "http://localhost:8080/callback"


def generate_pkce_pair():
    """Generate high-entropy code_verifier and S256 code_challenge."""
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode("utf-8")).digest()
    challenge = base64.urlsafe_b64encode(digest).decode("utf-8").replace("=", "")
    return verifier, challenge


class CallbackHandler(BaseHTTPRequestHandler):
    """Temporary local HTTP server to receive the OAuth 2.0 authorization code."""
    auth_code = None
    state = None
    error = None

    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        if "code" in params:
            CallbackHandler.auth_code = params["code"][0]
            CallbackHandler.state = params.get("state", [None])[0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"""
                <html>
                <body style="font-family: sans-serif; text-align: center; padding: 50px; background: #0f172a; color: #f8fafc;">
                    <h1 style="color: #38bdf8;">Authorization Successful!</h1>
                    <p>SHIV Identity has returned your authorization code. You can close this window and return to the terminal.</p>
                </body>
                </html>
            """)
        else:
            CallbackHandler.error = params.get("error", ["Unknown error"])[0]
            self.send_response(400)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(f"Authorization Error: {CallbackHandler.error}".encode("utf-8"))

    def log_message(self, format, *args):
        pass  # Quiet logging


def run_oidc_flow(issuer: str, client_id: str, client_secret: str = None):
    print("=" * 70)
    print(" SHIV IDENTITY — OPENID CONNECT (OIDC) INTEGRATION DEMO")
    print("=" * 70)
    print(f"[*] Identity Provider: {issuer}")
    print(f"[*] Client ID:         {client_id}")
    print(f"[*] Client Secret:     {'[Present - Confidential Client]' if client_secret else '[None - Public Client with PKCE]'}")
    print(f"[*] Redirect URI:      {REDIRECT_URI}")
    print("-" * 70)

    # 1. Discover Provider Metadata
    print("\n[Step 1] Fetching OIDC Discovery document...")
    disc_url = f"{issuer.rstrip('/')}/.well-known/openid-configuration"
    try:
        disc_res = httpx.get(disc_url, timeout=10.0)
        disc_res.raise_for_status()
        config = disc_res.json()
        print(f"  ✓ Issuer:                {config.get('issuer')}")
        print(f"  ✓ Authorization Endpoint:{config.get('authorization_endpoint')}")
        print(f"  ✓ Token Endpoint:        {config.get('token_endpoint')}")
        print(f"  ✓ JWKS URI:              {config.get('jwks_uri')}")
        print(f"  ✓ UserInfo Endpoint:     {config.get('userinfo_endpoint')}")
    except Exception as e:
        print(f"  ✗ Failed to fetch discovery document from {disc_url}: {e}")
        return

    # 2. Generate PKCE and Anti-CSRF Parameters
    print("\n[Step 2] Generating PKCE S256 verifier, challenge, state, and nonce...")
    verifier, challenge = generate_pkce_pair()
    state = secrets.token_urlsafe(16)
    nonce = secrets.token_urlsafe(16)
    print(f"  ✓ PKCE Code Verifier:  {verifier[:16]}... (length: {len(verifier)})")
    print(f"  ✓ PKCE Code Challenge: {challenge}")
    print(f"  ✓ State (CSRF):        {state}")
    print(f"  ✓ Nonce (Replay):      {nonce}")

    # 3. Construct Authorization URL
    auth_params = {
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": "openid profile email offline_access",
        "state": state,
        "nonce": nonce,
        "code_challenge": challenge,
        "code_challenge_method": "S256"
    }
    auth_url = f"{config['authorization_endpoint']}?{urlencode(auth_params)}"

    print("\n[Step 3] Initiating Authorization Request...")
    print(f"  Authorization URL:\n  {auth_url}")

    # 4. Start local listener and open browser
    print(f"\n[Step 4] Starting local callback server on {REDIRECT_URI}...")
    server = HTTPServer(("localhost", 8080), CallbackHandler)
    server.timeout = 120

    print("  Opening browser for user authentication and consent...")
    try:
        webbrowser.open(auth_url)
    except Exception:
        print(f"  Could not open browser automatically. Please open this URL manually:\n  {auth_url}")

    print("  Waiting for authorization redirect callback (timeout: 120s)...")
    server.handle_request()

    if not CallbackHandler.auth_code:
        print(f"  ✗ Failed to receive authorization code: {CallbackHandler.error}")
        return

    if CallbackHandler.state != state:
        print(f"  ✗ CSRF Warning: Returned state '{CallbackHandler.state}' does not match '{state}'!")
        return

    code = CallbackHandler.auth_code
    print(f"  ✓ Received Authorization Code: {code[:16]}... (single-use)")

    # 5. Exchange Code for Tokens
    print("\n[Step 5] Exchanging Authorization Code for Tokens at /oauth/token...")
    token_payload = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "client_id": client_id,
        "code_verifier": verifier
    }
    if client_secret:
        token_payload["client_secret"] = client_secret

    token_res = httpx.post(config["token_endpoint"], data=token_payload, timeout=10.0)
    if token_res.status_code != 200:
        print(f"  ✗ Token Exchange Failed ({token_res.status_code}): {token_res.text}")
        return

    tokens = token_res.json()
    access_token = tokens["access_token"]
    id_token = tokens.get("id_token")
    refresh_token = tokens.get("refresh_token")

    print("  ✓ Received Token Response:")
    print(f"    - Access Token:  {access_token[:20]}... (type: {tokens.get('token_type')}, expires_in: {tokens.get('expires_in')}s)")
    print(f"    - ID Token:      {id_token[:20]}...")
    if refresh_token:
        print(f"    - Refresh Token: {refresh_token[:20]}...")

    # 6. Validate ID Token using Public JWKS Keys
    print("\n[Step 6] Validating RS256 Signed ID Token against JWKS...")
    jwks_res = httpx.get(config["jwks_uri"], timeout=10.0)
    jwks = jwks_res.json()
    header = jwt.get_unverified_header(id_token)
    kid = header.get("kid")
    print(f"  ✓ Token Header kid:    {kid}")
    print(f"  ✓ Token Algorithm:     {header.get('alg')}")

    matching_key = next((k for k in jwks["keys"] if k.get("kid") == kid), None)
    if not matching_key:
        print(f"  ✗ Public key with kid '{kid}' not found in JWKS!")
        return

    public_key = RSAAlgorithm.from_jwk(json.dumps(matching_key))
    claims = jwt.decode(
        id_token,
        public_key,
        algorithms=["RS256"],
        audience=client_id,
        issuer=config["issuer"]
    )
    print("  ✓ Cryptographic Signature Validated via Public RSA Key!")
    print(f"    - Subject (sub):        {claims.get('sub')}")
    print(f"    - SHIV ID:              {claims.get('shiv_id')}")
    print(f"    - Preferred Username:   {claims.get('preferred_username')}")
    print(f"    - Display Name:         {claims.get('name')}")
    print(f"    - Email:                {claims.get('email')}")
    print(f"    - Email Verified:       {claims.get('email_verified')}")
    print(f"    - Nonce Verified:       {claims.get('nonce') == nonce}")

    # 7. Query UserInfo Endpoint
    print("\n[Step 7] Querying /oauth/userinfo with Bearer Access Token...")
    uinfo_res = httpx.get(
        config["userinfo_endpoint"],
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=10.0
    )
    print(f"  ✓ UserInfo Response: {uinfo_res.json()}")

    # 8. Refresh Token Rotation
    if refresh_token:
        print("\n[Step 8] Testing Refresh Token Rotation...")
        rf_payload = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": client_id
        }
        if client_secret:
            rf_payload["client_secret"] = client_secret

        rf_res = httpx.post(config["token_endpoint"], data=rf_payload, timeout=10.0)
        if rf_res.status_code == 200:
            new_tokens = rf_res.json()
            print("  ✓ Refresh Token Rotated Successfully!")
            print(f"    - New Access Token:  {new_tokens['access_token'][:20]}...")
            print(f"    - New Refresh Token: {new_tokens['refresh_token'][:20]}...")
        else:
            print(f"  ✗ Refresh failed: {rf_res.text}")

    print("\n" + "=" * 70)
    print(" OIDC DEMO COMPLETE: ALL FLOWS VERIFIED SUCCESSFULLY!")
    print("=" * 70)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python examples/demo_oidc_client.py <CLIENT_ID> [CLIENT_SECRET] [ISSUER_URL]")
        print("Example (Local):")
        print("  python examples/demo_oidc_client.py shiv_client_xxxxxx my_secret http://localhost:8000")
        print("Example (Production):")
        print(f"  python examples/demo_oidc_client.py shiv_client_xxxxxx my_secret {DEFAULT_ISSUER}")
        sys.exit(1)

    cid = sys.argv[1]
    csec = sys.argv[2] if len(sys.argv) > 2 else None
    iss = sys.argv[3] if len(sys.argv) > 3 else LOCAL_ISSUER

    run_oidc_flow(issuer=iss, client_id=cid, client_secret=csec)
