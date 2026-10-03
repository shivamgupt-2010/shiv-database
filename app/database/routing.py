import asyncio
import json
import logging
from typing import Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.providers.base import DatabaseProvider
from app.database.providers.shiv_native import ShivNativeDatabaseProvider
from app.database.providers.supabase import SupabaseDatabaseProvider
from app.database.providers.firebase import FirebaseDatabaseProvider
from app.core.exceptions import ProviderError
from app.core.constants import ProviderTypeEnum

logger = logging.getLogger(__name__)

import random

class PoolRouter:
    """
    True Data Pooling System: Treats multiple free-tier database shards as a unified pool.
    Distributes records across the pool and supports scatter-gather querying.
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        self.native_provider = ShivNativeDatabaseProvider(session)
        self.providers: Dict[str, DatabaseProvider] = {
            "shiv_native": self.native_provider
        }
        
        self.pool_nodes: list[str] = []
        self.default_provider_id = "shiv_native"

    def load_configuration(self, config_dict: dict):
        instances = config_dict.get("instances", {})
        
        for instance_id, instance_config in instances.items():
            provider_type = instance_config.get("type")
            try:
                if provider_type == ProviderTypeEnum.FIREBASE.value:
                    self.providers[instance_id] = FirebaseDatabaseProvider(instance_config, instance_id)
                elif provider_type == ProviderTypeEnum.SUPABASE.value:
                    self.providers[instance_id] = SupabaseDatabaseProvider(instance_config, instance_id)
                else:
                    logger.warning(f"Unknown provider type '{provider_type}' for instance '{instance_id}'")
            except Exception as e:
                logger.error(f"Failed to initialize storage node '{instance_id}': {e}")
                
        self.pool_nodes = config_dict.get("pool", [])
        self.default_provider_id = config_dict.get("default", "shiv_native")
        logger.info(f"True Data Pool initialized with {len(self.pool_nodes)} active nodes (Total available providers: {len(self.providers)}).")

    def get_provider_for_new_record(self) -> tuple[DatabaseProvider, str]:
        """Picks an instance from the pool for a new record (Round Robin / Random)."""
        if not self.pool_nodes:
            logger.warning("No pool nodes configured. Falling back to native.")
            return self.native_provider, "shiv_native"
            
        instance_id = random.choice(self.pool_nodes)
        provider = self.providers.get(instance_id)
        if not provider:
            return self.native_provider, "shiv_native"
            
        return provider, instance_id

    def get_provider_by_id(self, instance_id: str) -> DatabaseProvider:
        """Fetch the exact provider where a record lives."""
        return self.providers.get(instance_id, self.native_provider)

    def get_all_pool_providers(self) -> Dict[str, DatabaseProvider]:
        """Returns all configured pool instances for scatter-gather operations."""
        return {node: self.providers[node] for node in self.pool_nodes if node in self.providers}

    async def health_check_all(self) -> Dict[str, str]:
        names = list(self.providers.keys())
        tasks = [provider.health_check() for provider in self.providers.values()]
        
        results = []
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
        health_status = {}
        for name, result in zip(names, results):
            if isinstance(result, Exception):
                health_status[name] = "unhealthy (error)"
            else:
                health_status[name] = result
        return health_status
