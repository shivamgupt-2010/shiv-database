import os
import json
import logging
from typing import Any, Dict, Optional
from cachetools import TTLCache

logger = logging.getLogger(__name__)

# Fallback in-memory cache if Redis is not available
_memory_cache = TTLCache(maxsize=10000, ttl=3600)

class CacheService:
    """
    Enterprise caching layer supporting Redis for production and 
    cachetools in-memory fallback for local development.
    """
    def __init__(self):
        self.redis_url = os.getenv("REDIS_URL")
        self.redis = None
        
        if self.redis_url:
            try:
                import redis.asyncio as redis_async
                self.redis = redis_async.from_url(self.redis_url, decode_responses=True)
                logger.info(f"Connected to Redis at {self.redis_url}")
            except ImportError:
                logger.warning("Redis package not installed. Falling back to memory cache.")
            except Exception as e:
                logger.warning(f"Could not connect to Redis: {e}. Falling back to memory cache.")
        else:
            logger.info("No REDIS_URL found. Using in-memory cachetools fallback.")

    async def get_record(self, collection: str, record_id: str) -> Optional[Dict[str, Any]]:
        cache_key = f"record:{collection}:{record_id}"
        
        if self.redis:
            try:
                data = await self.redis.get(cache_key)
                if data:
                    # Log cache hit for hot/cold tiering metrics
                    await self._increment_access_count(cache_key)
                    return json.loads(data)
            except Exception as e:
                logger.error(f"Redis get error: {e}")
                
        # Fallback to memory
        if cache_key in _memory_cache:
            return _memory_cache.get(cache_key)
            
        return None

    async def set_record(self, collection: str, record_id: str, data: Dict[str, Any], ttl_seconds: int = 3600):
        cache_key = f"record:{collection}:{record_id}"
        
        if self.redis:
            try:
                await self.redis.set(cache_key, json.dumps(data), ex=ttl_seconds)
                return
            except Exception as e:
                logger.error(f"Redis set error: {e}")
                
        # Fallback to memory
        _memory_cache[cache_key] = data

    async def invalidate_record(self, collection: str, record_id: str):
        cache_key = f"record:{collection}:{record_id}"
        if self.redis:
            try:
                await self.redis.delete(cache_key)
            except Exception as e:
                logger.error(f"Redis delete error: {e}")
                
        if cache_key in _memory_cache:
            del _memory_cache[cache_key]

    async def _increment_access_count(self, cache_key: str):
        """Track how many times a record is accessed for Hot/Cold tiering."""
        if self.redis:
            try:
                stats_key = f"stats:{cache_key}"
                await self.redis.incr(stats_key)
            except Exception:
                pass
