import random
import os
import json
import logging
from typing import Dict, Any, Tuple

logger = logging.getLogger(__name__)

class StoragePoolService:
    """
    Unlimited File & Image Pooling (Media Sharding).
    Distributes raw file uploads across multiple Firebase Storage buckets.
    """
    def __init__(self):
        self.storage_nodes: Dict[str, Dict[str, Any]] = {}
        self.pool: list[str] = []
        
        # Load config
        config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "providers_config.json")
        try:
            if os.path.exists(config_path):
                with open(config_path, "r") as f:
                    config = json.load(f)
                    self.pool = config.get("storage_pool", [])
                    instances = config.get("instances", {})
                    for node_id in self.pool:
                        if node_id in instances:
                            self.storage_nodes[node_id] = instances[node_id]
        except Exception as e:
            logger.error(f"Failed to load storage config: {e}")

    def _get_random_node(self) -> Tuple[str, Dict[str, Any]]:
        if not self.pool:
            raise RuntimeError("No storage nodes available in the pool")
        node_id = random.choice(self.pool)
        return node_id, self.storage_nodes[node_id]

    async def upload_file(self, project_id: str, file_name: str, file_bytes: bytes, content_type: str) -> Dict[str, Any]:
        """
        Picks a random bucket from the pool and uploads the file there.
        In a real implementation, uses firebase_admin.storage or direct REST.
        """
        node_id, node_config = self._get_random_node()
        bucket_name = node_config.get("storage_bucket")
        
        # Mock upload implementation (in production, use firebase-admin SDK to upload file_bytes)
        logger.info(f"[StoragePool] Uploading {file_name} to {bucket_name} on node {node_id}")
        
        file_url = f"https://firebasestorage.googleapis.com/v0/b/{bucket_name}/o/{file_name}?alt=media"
        
        return {
            "file_name": file_name,
            "url": file_url,
            "node_id": node_id,
            "bucket": bucket_name,
            "size": len(file_bytes),
            "content_type": content_type
        }
