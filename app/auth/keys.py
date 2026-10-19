import os
import base64
import logging
from typing import Dict, Any, List
import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend

from app.core.config import settings

logger = logging.getLogger(__name__)


def int_to_b64url(val: int) -> str:
    """Encodes an integer as a base64url-encoded string without padding."""
    byte_len = (val.bit_length() + 7) // 8
    b = val.to_bytes(byte_len, "big")
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode("ascii")


class KeyManager:
    """
    Manages RSA-2048 cryptographic signing keys for OpenID Connect ID Tokens.
    Generates standard RFC 7517 JWKS for public verification at /.well-known/jwks.json.
    """

    def __init__(self):
        self.active_kid = "shiv-identity-key-2026-v1"
        self.private_key = None
        self.public_key = None
        self.jwks: Dict[str, Any] = {"keys": []}
        self.public_keys_by_kid: Dict[str, Any] = {}
        self._initialize_keys()

    def _initialize_keys(self):
        key_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".keys")
        os.makedirs(key_dir, exist_ok=True)
        key_path = os.path.join(key_dir, "oidc_rsa_private.pem")

        env_key = os.environ.get("OIDC_RSA_PRIVATE_KEY_PEM")
        if env_key:
            try:
                self.private_key = serialization.load_pem_private_key(
                    env_key.encode("utf-8"),
                    password=None,
                    backend=default_backend()
                )
            except Exception as e:
                logger.error(f"Failed to load OIDC_RSA_PRIVATE_KEY_PEM from environment: {e}")

        if not self.private_key:
            if os.path.exists(key_path):
                try:
                    with open(key_path, "rb") as f:
                        self.private_key = serialization.load_pem_private_key(
                            f.read(),
                            password=None,
                            backend=default_backend()
                        )
                except Exception as e:
                    logger.warning(f"Could not load existing key file {key_path}: {e}")

        if not self.private_key:
            # Generate fresh RSA 2048 key pair
            logger.info("Generating fresh RSA 2048 key pair for SHIV Identity OIDC provider...")
            self.private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=2048,
                backend=default_backend()
            )
            # Save to disk
            try:
                pem = self.private_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.PKCS8,
                    encryption_algorithm=serialization.NoEncryption()
                )
                with open(key_path, "wb") as f:
                    f.write(pem)
            except Exception as e:
                logger.warning(f"Could not write private key to disk: {e}")

        self.public_key = self.private_key.public_key()
        self._build_jwks()

    def _build_jwks(self):
        pn = self.public_key.public_numbers()
        jwk = {
            "kty": "RSA",
            "use": "sig",
            "alg": "RS256",
            "kid": self.active_kid,
            "n": int_to_b64url(pn.n),
            "e": int_to_b64url(pn.e),
        }
        self.jwks = {"keys": [jwk]}
        self.public_keys_by_kid[self.active_kid] = self.public_key

    def get_jwks(self) -> Dict[str, Any]:
        """Returns the public JWKS document."""
        return self.jwks

    def sign_id_token(self, payload: Dict[str, Any], kid: str = None) -> str:
        """Signs an OIDC ID Token with the RS256 private key and kid header."""
        signing_kid = kid or self.active_kid
        headers = {"kid": signing_kid, "alg": "RS256"}
        return jwt.encode(payload, self.private_key, algorithm="RS256", headers=headers)

    def verify_id_token(self, token: str, audience: str = None) -> Dict[str, Any]:
        """Verifies an OIDC ID Token signature and claims."""
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header.get("kid")
        pub_key = self.public_keys_by_kid.get(kid, self.public_key)
        kwargs = {"algorithms": ["RS256"]}
        if audience:
            kwargs["audience"] = audience
        else:
            kwargs["options"] = {"verify_aud": False}
        return jwt.decode(token, pub_key, **kwargs)


key_manager = KeyManager()
