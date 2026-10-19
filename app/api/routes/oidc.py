from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from app.auth.keys import key_manager

router = APIRouter(tags=["OpenID Connect Discovery & JWKS"])


def get_issuer_url(request: Request) -> str:
    base = str(request.base_url).rstrip("/")
    proto = request.headers.get("x-forwarded-proto", "")
    if "https" in proto and base.startswith("http://"):
        base = "https://" + base[7:]
    return base


@router.get("/.well-known/openid-configuration")
async def openid_configuration(request: Request):
    """
    Standard OpenID Connect Discovery 1.0 Document.
    Enables zero-config client integration across all OIDC-compliant libraries.
    """
    issuer = get_issuer_url(request)

    return JSONResponse(
        content={
            "issuer": issuer,
            "authorization_endpoint": f"{issuer}/oauth/authorize",
            "token_endpoint": f"{issuer}/oauth/token",
            "userinfo_endpoint": f"{issuer}/oauth/userinfo",
            "jwks_uri": f"{issuer}/.well-known/jwks.json",
            "registration_endpoint": f"{issuer}/oauth/clients",
            "revocation_endpoint": f"{issuer}/oauth/revoke",
            "introspection_endpoint": f"{issuer}/oauth/introspect",
            "end_session_endpoint": f"{issuer}/oauth/logout",
            "response_types_supported": ["code"],
            "grant_types_supported": ["authorization_code", "refresh_token"],
            "subject_types_supported": ["public"],
            "id_token_signing_alg_values_supported": ["RS256"],
            "scopes_supported": ["openid", "profile", "email", "offline_access"],
            "token_endpoint_auth_methods_supported": [
                "client_secret_post",
                "client_secret_basic",
                "none"
            ],
            "claims_supported": [
                "sub",
                "iss",
                "aud",
                "exp",
                "iat",
                "nonce",
                "preferred_username",
                "name",
                "email",
                "email_verified",
                "picture",
                "shiv_id"
            ],
            "code_challenge_methods_supported": ["S256"],
            "claims_parameter_supported": False,
            "request_parameter_supported": False,
            "request_uri_parameter_supported": False
        },
        headers={
            "Cache-Control": "public, max-age=3600",
            "Access-Control-Allow-Origin": "*"
        }
    )


@router.get("/.well-known/jwks.json")
async def jwks():
    """
    JSON Web Key Set (RFC 7517) exposing public RSA verification keys.
    """
    return JSONResponse(
        content=key_manager.get_jwks(),
        headers={
            "Cache-Control": "public, max-age=3600",
            "Access-Control-Allow-Origin": "*"
        }
    )
