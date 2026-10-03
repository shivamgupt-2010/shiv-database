from typing import Dict, Any, Optional
import httpx
from app.auth.providers.base import AuthProvider
from app.core.exceptions import AuthenticationError


class SupabaseAuthProvider(AuthProvider):
    """Dynamic Supabase Authentication provider for multi-tenancy."""

    def __init__(self, config: dict, project_id: str):
        self.config = config
        self.project_id = project_id
        
        self.url = config.get("url")
        self.api_key = config.get("anon_key") or config.get("service_role_key")
        
        if self.url and self.api_key:
            self.client = httpx.AsyncClient(
                base_url=f"{self.url}/auth/v1",
                headers={
                    "apikey": self.api_key,
                    "Content-Type": "application/json",
                }
            )
        else:
            self.client = None

    def _check_config(self):
        if not self.client:
            raise AuthenticationError(f"Supabase Auth is not configured for project {self.project_id}.")

    async def register_user(self, user_data: Dict[str, Any]) -> Dict[str, Any]:
        self._check_config()
        
        payload = {
            "email": user_data.get("email"),
            "password": user_data.get("password"),
            "data": {
                "full_name": user_data.get("full_name")
            }
        }
        
        response = await self.client.post("/signup", json=payload)
        
        if response.status_code >= 400:
            raise AuthenticationError(f"Supabase registration failed: {response.text}")
            
        data = response.json()
        return {
            "uid": data.get("user", {}).get("id"),
            "email": data.get("user", {}).get("email"),
            "provider": "supabase"
        }

    async def authenticate_user(self, credentials: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        self._check_config()
        
        payload = {
            "email": credentials.get("email"),
            "password": credentials.get("password")
        }
        
        response = await self.client.post("/token?grant_type=password", json=payload)
        
        if response.status_code == 200:
            data = response.json()
            return {
                "uid": data.get("user", {}).get("id"),
                "email": data.get("user", {}).get("email"),
                "token": data.get("access_token"),
                "refresh_token": data.get("refresh_token"),
                "provider": "supabase"
            }
            
        raise AuthenticationError(f"Invalid Supabase credentials: {response.text}")

    async def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        self._check_config()
        
        # To verify a token with Supabase REST, we fetch the user using the token
        response = await self.client.get(
            "/user", 
            headers={"Authorization": f"Bearer {token}"}
        )
        
        if response.status_code == 200:
            data = response.json()
            return {
                "uid": data.get("id"),
                "email": data.get("email"),
                "provider": "supabase"
            }
            
        raise AuthenticationError(f"Supabase token verification failed: {response.text}")

    async def revoke_sessions(self, user_id: str) -> bool:
        self._check_config()
        # Requires service_role key to log out another user admin-side
        response = await self.client.post(f"/admin/users/{user_id}/logout")
        return response.status_code in (200, 204)
