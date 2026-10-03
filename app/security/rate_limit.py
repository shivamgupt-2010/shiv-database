import time
import asyncio
from typing import Dict, List
from fastapi import Request, HTTPException, status
from app.core.config import settings

class RateLimiter:
    """
    Simple in-memory sliding window rate limiter.
    For production scale, this should be replaced by a Redis-backed implementation.
    """
    def __init__(self, requests: int, window: int):
        self.requests = requests
        self.window = window
        self.clients: Dict[str, List[float]] = {}
        self.lock = asyncio.Lock()

    async def __call__(self, request: Request):
        if not settings.RATE_LIMIT_ENABLED:
            return True
            
        # Get client IP or API key (if authenticated early)
        client_id = request.client.host if request.client else "unknown"
        
        # Optionally, if api-key header is present, rate limit by key instead
        api_key = request.headers.get("x-api-key")
        if api_key:
            client_id = f"api_key:{api_key[:10]}" # use prefix to avoid storing full key in memory keys

        now = time.time()
        
        async with self.lock:
            if client_id not in self.clients:
                self.clients[client_id] = []
                
            # Filter out timestamps older than the window
            self.clients[client_id] = [t for t in self.clients[client_id] if now - t < self.window]
            
            if len(self.clients[client_id]) >= self.requests:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many requests"
                )
                
            self.clients[client_id].append(now)

# Default rate limiter: e.g. 100 requests per 60 seconds
default_rate_limiter = RateLimiter(requests=100, window=60)
