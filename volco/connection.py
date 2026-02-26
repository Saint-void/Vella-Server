from fastapi import WebSocket
from typing import Dict

class ConnectionManager:
    def __init__(self):
        # Keeps track of users and their connected clients.
        # Structure: { "user_id": { "device": websocket, "app": websocket } }
        self.active_connections: Dict[str, Dict[str, WebSocket]] = {}

    async def connect(self, user_id: str, client_type: str, websocket: WebSocket):
        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = {}
        
        self.active_connections[user_id][client_type] = websocket
        print(f"🔌 [VOLCO-SERVER] {user_id} ({client_type}) Connected")

    def disconnect(self, user_id: str, client_type: str):
        if user_id in self.active_connections:
            if client_type in self.active_connections[user_id]:
                del self.active_connections[user_id][client_type]
            
            # Clean up if the user has no active devices/apps left
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
                
        print(f"🔌 [VOLCO-SERVER] {user_id} ({client_type}) Disconnected")

    async def broadcast_to_app(self, user_id: str, message: dict):
        """Sends JSON data to a companion app (like your normal Vella chat interface) if it's open."""
        if user_id in self.active_connections and "app" in self.active_connections[user_id]:
            try:
                await self.active_connections[user_id]["app"].send_json(message)
            except Exception as e:
                print(f"⚠️ [VOLCO-SERVER] Failed to broadcast to app: {e}")
                # Force disconnect if the socket is totally dead
                self.disconnect(user_id, "app")

# We create a single global instance here so router.py can import it easily
volco_manager = ConnectionManager()