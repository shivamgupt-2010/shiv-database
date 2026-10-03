import json
from typing import Dict, Any, Optional
from app.auth.providers.base import AuthProvider
from app.core.exceptions import AuthenticationError

try:
    import firebase_admin
    from firebase_admin import credentials, auth as firebase_auth
    FIREBASE_AVAILABLE = True
except ImportError:
    FIREBASE_AVAILABLE = False


class FirebaseAuthProvider(AuthProvider):
    """Dynamic Firebase Authentication provider for multi-tenancy."""

    def __init__(self, config: dict, project_id: str):
        self.config = config
        self.project_id = project_id
        self.app_name = f"shiv_auth_{project_id}"
        
        firebase_project_id = config.get("project_id")
        credentials_json = config.get("credentials_json")

        if FIREBASE_AVAILABLE and firebase_project_id:
            try:
                self.app = firebase_admin.get_app(name=self.app_name)
            except ValueError:
                if credentials_json:
                    cred_dict = credentials_json if isinstance(credentials_json, dict) else json.loads(credentials_json)
                    cred = credentials.Certificate(cred_dict)
                    self.app = firebase_admin.initialize_app(cred, name=self.app_name)
                else:
                    self.app = None
        else:
            self.app = None

    def _check_config(self):
        if not FIREBASE_AVAILABLE:
            raise AuthenticationError("Firebase Admin SDK is not installed.")
        if not self.app:
            raise AuthenticationError(f"Firebase Auth is not configured for project {self.project_id}.")

    async def register_user(self, user_data: Dict[str, Any]) -> Dict[str, Any]:
        self._check_config()
        try:
            # Note: The Firebase Admin SDK is synchronous
            user_record = firebase_auth.create_user(
                email=user_data.get("email"),
                password=user_data.get("password"),
                display_name=user_data.get("full_name"),
                app=self.app
            )
            return {
                "uid": user_record.uid,
                "email": user_record.email,
                "provider": "firebase"
            }
        except Exception as e:
            raise AuthenticationError(f"Firebase registration failed: {str(e)}")

    async def authenticate_user(self, credentials: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        In Firebase, password verification typically happens on the client via REST API.
        The Admin SDK doesn't support password verification directly.
        For a complete backend implementation, we'd use the Firebase Identity Toolkit REST API.
        """
        self._check_config()
        email = credentials.get("email")
        password = credentials.get("password")
        web_api_key = self.config.get("web_api_key")
        
        if not web_api_key:
            raise AuthenticationError("Firebase WEB_API_KEY is required to authenticate passwords on the backend.")

        import httpx
        url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={web_api_key}"
        payload = {
            "email": email,
            "password": password,
            "returnSecureToken": True
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload)
            if response.status_code == 200:
                data = response.json()
                return {
                    "uid": data["localId"],
                    "email": data["email"],
                    "token": data["idToken"],
                    "provider": "firebase"
                }
            raise AuthenticationError(f"Invalid Firebase credentials: {response.text}")

    async def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        self._check_config()
        try:
            decoded_token = firebase_auth.verify_id_token(token, app=self.app)
            return {
                "uid": decoded_token.get("uid"),
                "email": decoded_token.get("email"),
                "provider": "firebase"
            }
        except Exception as e:
            raise AuthenticationError(f"Firebase token verification failed: {str(e)}")

    async def revoke_sessions(self, user_id: str) -> bool:
        self._check_config()
        try:
            firebase_auth.revoke_refresh_tokens(user_id, app=self.app)
            return True
        except Exception:
            return False
