import asyncio
import json
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Dict, List

router = APIRouter(prefix="/realtime", tags=["Realtime"])
logger = logging.getLogger(__name__)

class ConnectionManager:
    """Manages active WebSocket connections for realtime sync."""
    def __init__(self):
        # Maps collection_name to list of active websocket connections
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, collection: str):
        await websocket.accept()
        if collection not in self.active_connections:
            self.active_connections[collection] = []
        self.active_connections[collection].append(websocket)
        logger.info(f"WebSocket Client connected to collection: {collection}")

    def disconnect(self, websocket: WebSocket, collection: str):
        if collection in self.active_connections:
            self.active_connections[collection].remove(websocket)
            logger.info(f"WebSocket Client disconnected from collection: {collection}")

    async def broadcast_update(self, collection: str, record_id: str, data: dict):
        """Broadcast an update to all clients listening to a specific collection."""
        if collection in self.active_connections:
            message = {
                "event": "update",
                "collection": collection,
                "record_id": record_id,
                "data": data
            }
            for connection in self.active_connections[collection]:
                try:
                    await connection.send_text(json.dumps(message))
                except Exception as e:
                    logger.error(f"Error sending ws message: {e}")

manager = ConnectionManager()

@router.websocket("/ws/{collection}")
async def websocket_endpoint(websocket: WebSocket, collection: str):
    """
    WebSocket endpoint for frontends to listen to realtime data changes.
    URL: ws://server/realtime/ws/{collection}
    """
    await manager.connect(websocket, collection)
    try:
        while True:
            # We keep the connection open and wait for incoming messages if needed,
            # though usually it's one-way from Server -> Client for live updates.
            data = await websocket.receive_text()
            # Can handle incoming pings if necessary
    except WebSocketDisconnect:
        manager.disconnect(websocket, collection)
