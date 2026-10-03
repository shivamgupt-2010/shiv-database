import uuid
from typing import Any, Dict, List, Optional
from app.database.providers.base import DatabaseProvider
from app.database.schemas.records import QueryRequest
from app.core.exceptions import ProviderError

try:
    import firebase_admin
    from firebase_admin import credentials, firestore
    from google.cloud.firestore_v1.base_query import FieldFilter
    FIREBASE_AVAILABLE = True
except ImportError:
    FIREBASE_AVAILABLE = False


class FirebaseDatabaseProvider(DatabaseProvider):
    """Dynamic Firebase Firestore database provider for multi-tenancy."""

    def __init__(self, config: dict, project_id: str):
        self.config = config
        self.project_id = project_id
        self.app_name = f"shiv_db_{project_id}"
        self.db = None
        
        firebase_project_id = config.get("project_id")
        credentials_json = config.get("credentials_json")

        if FIREBASE_AVAILABLE and firebase_project_id:
            try:
                # Get existing app instance for this project to prevent collisions
                app = firebase_admin.get_app(name=self.app_name)
            except ValueError:
                # Initialize new app instance specifically for this project
                if credentials_json and credentials_json != {}:
                    import json
                    cred_dict = credentials_json if isinstance(credentials_json, dict) else json.loads(credentials_json)
                    cred = credentials.Certificate(cred_dict)
                    app = firebase_admin.initialize_app(cred, name=self.app_name)
                else:
                    app = None
                    
            if app:
                self.db = firestore.client(app=app)
            else:
                # Mock DB for demo purposes if no service account is provided
                class MockDB:
                    def __init__(self):
                        self._data = {}
                    def collection(self, name):
                        return self
                    def document(self, name):
                        return self
                    def set(self, data):
                        self._data = data
                    def get(self):
                        class MockDoc:
                            def __init__(self, d): self.d = d
                            @property
                            def exists(self): return True
                            def to_dict(self): return self.d
                        return MockDoc(self._data)
                    def update(self, data):
                        self._data.update(data)
                    def delete(self):
                        self._data = {}
                    def where(self, *args, **kwargs):
                        return self
                    def order_by(self, *args, **kwargs):
                        return self
                    def limit(self, *args, **kwargs):
                        return self
                    def offset(self, *args, **kwargs):
                        return self
                    def stream(self):
                        class MockDoc:
                            def __init__(self, d): self.d = d
                            def to_dict(self): return self.d
                        return [MockDoc(self._data)] if self._data else []
                self.db = MockDB()

    def _check_config(self):
        if not FIREBASE_AVAILABLE:
            raise ProviderError("Firebase Admin SDK is not installed.")
        if not self.db:
            raise ProviderError(f"Firebase is not properly configured for project {self.project_id}.")

    async def create(
        self,
        project_id: str,
        collection: str,
        data: Dict[str, Any],
        record_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        self._check_config()
        r_id = record_id or str(uuid.uuid4())
        
        # We can store directly in the collection since the Firebase DB instance is dedicated
        # Pattern: {collection}/{r_id} or projects/{project_id}/{collection}/{r_id}
        # Let's keep the multi-tenant namespace pattern just in case they share a Firebase DB
        doc_ref = self.db.collection("projects").document(project_id).collection(collection).document(r_id)
        
        payload = {
            "id": r_id,
            "project_id": project_id,
            "data": data
        }
        
        try:
            doc_ref.set(payload)
            return payload
        except Exception as e:
            raise ProviderError(f"Firebase create failed: {str(e)}")

    async def get(
        self,
        project_id: str,
        collection: str,
        record_id: str,
    ) -> Optional[Dict[str, Any]]:
        self._check_config()
        doc_ref = self.db.collection("projects").document(project_id).collection(collection).document(record_id)
        doc = doc_ref.get()
        if doc.exists:
            return doc.to_dict()
        return None

    async def update(
        self,
        project_id: str,
        collection: str,
        record_id: str,
        data: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        self._check_config()
        doc_ref = self.db.collection("projects").document(project_id).collection(collection).document(record_id)
        try:
            update_payload = {f"data.{k}": v for k, v in data.items()}
            doc_ref.update(update_payload)
            doc = doc_ref.get()
            return doc.to_dict()
        except Exception as e:
            raise ProviderError(f"Firebase update failed: {str(e)}")

    async def delete(
        self,
        project_id: str,
        collection: str,
        record_id: str,
    ) -> bool:
        self._check_config()
        doc_ref = self.db.collection("projects").document(project_id).collection(collection).document(record_id)
        try:
            doc_ref.delete()
            return True
        except Exception as e:
            raise ProviderError(f"Firebase delete failed: {str(e)}")

    async def query(
        self,
        project_id: str,
        collection: str,
        query_params: QueryRequest,
    ) -> List[Dict[str, Any]]:
        self._check_config()
        coll_ref = self.db.collection("projects").document(project_id).collection(collection)
        
        query = coll_ref
        
        if query_params.filters:
            op_map = {
                "eq": "==", "neq": "!=", "gt": ">", "lt": "<", 
                "gte": ">=", "lte": "<="
            }
            for f in query_params.filters:
                op = op_map.get(f.operator)
                if op:
                    query = query.where(filter=FieldFilter(f"data.{f.field}", op, f.value))
                elif f.operator == "contains":
                    query = query.where(filter=FieldFilter(f"data.{f.field}", "array_contains", f.value))
                    
        if query_params.order_by:
            for ob in query_params.order_by:
                direction = firestore.Query.DESCENDING if ob.direction == "desc" else firestore.Query.ASCENDING
                query = query.order_by(f"data.{ob.field}", direction=direction)
                
        if query_params.limit:
            query = query.limit(query_params.limit)
            
        if query_params.offset:
            query = query.offset(query_params.offset)
            
        try:
            docs = query.stream()
            return [doc.to_dict() for doc in docs]
        except Exception as e:
            raise ProviderError(f"Firebase query failed: {str(e)}")

    async def health_check(self) -> str:
        if not FIREBASE_AVAILABLE or not self.db:
            return "unconfigured"
        try:
            self.db.collection("health").limit(1).get()
            return "healthy"
        except Exception:
            return "unhealthy"
