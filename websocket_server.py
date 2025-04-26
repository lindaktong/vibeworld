#!/usr/bin/env python
import asyncio
import websockets
import json
import random
import time
import logging
import uuid

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# List to store active WebSocket connections
CONNECTIONS = set()

# Store the latest positions received from clients
WORLD_STATE = {}

async def register(websocket):
    """Register a new client connection"""
    CONNECTIONS.add(websocket)
    logger.info(f"Client connected. Total connections: {len(CONNECTIONS)}")

async def unregister(websocket):
    """Unregister a client connection"""
    CONNECTIONS.remove(websocket)
    logger.info(f"Client disconnected. Total connections: {len(CONNECTIONS)}")

async def send_object(path="models/tree.glb", interval=5):
    """Send objects to all connected clients at specified interval
    
    Args:
        path (str): Path to the 3D model file
        interval (int): Seconds between object placements
    """
    while True:
        if CONNECTIONS:  # Only send if there are connections
            # First, request current positions from the client
            await request_positions()
            await asyncio.sleep(1)  # Wait a moment for positions to come back
            
            # Get object type from filename (without extension)
            object_type = path.split('/')[-1].split('.')[0]
            
            # Create a message with positioning for the object
            # Use world state to make smarter placement decisions if available
            object_position = generate_object_position()
            
            object_message = {
                "type": "load-object",
                "id": f"{object_type}_{int(time.time())}_{random.randint(1000, 9999)}",  # Unique ID
                "path": path,
                "position": object_position,
                "rotation": {
                    "x": 0,
                    "y": random.uniform(0, 6.28),  # Random rotation around Y axis (0 to 2π)
                    "z": 0
                },
                "scale": {
                    "x": random.uniform(2.5, 7.5),
                    "y": random.uniform(2.5, 7.5),
                    "z": random.uniform(2.5, 7.5)
                }
            }

            # Convert to JSON string
            message = json.dumps(object_message)
            
            # Send to all connected clients
            for websocket in CONNECTIONS.copy():
                try:
                    await websocket.send(message)
                    logger.info(f"Sent {object_type} at position: {object_message['position']}")
                except websockets.exceptions.ConnectionClosed:
                    # Connection might have closed between iterations
                    await unregister(websocket)
        
        # Wait for the specified interval
        await asyncio.sleep(interval)

async def request_positions():
    """Request current object positions from clients"""
    if not CONNECTIONS:
        return
        
    request_id = str(uuid.uuid4())
    position_request = {
        "type": "get-object-positions",
        "requestId": request_id,
        "timestamp": int(time.time() * 1000)
    }
    
    message = json.dumps(position_request)
    
    # Send request to all connected clients
    for websocket in CONNECTIONS.copy():
        try:
            await websocket.send(message)
            logger.info("Sent position request to client")
        except websockets.exceptions.ConnectionClosed:
            await unregister(websocket)

def generate_object_position():
    """Generate a position for a new object, potentially using world state"""
    if not WORLD_STATE or 'objects' not in WORLD_STATE:
        # If we don't have world state yet, use random position
        return {
            "x": random.uniform(-10, 10),
            "y": 0,  # Place on ground
            "z": random.uniform(-10, 10)
        }
    
    # Try to place objects in interesting patterns or away from existing objects
    existing_positions = []
    
    # Extract positions of existing objects
    for obj_id, obj_data in WORLD_STATE.get('objects', {}).items():
        if 'position' in obj_data:
            existing_positions.append((
                obj_data['position'].get('x', 0),
                obj_data['position'].get('z', 0)
            ))
    
    # Try to place object at least 3 units away from any existing object
    MIN_DISTANCE = 3.0
    MAX_ATTEMPTS = 10
    
    for _ in range(MAX_ATTEMPTS):
        x = random.uniform(-10, 10)
        z = random.uniform(-10, 10)
        
        # Check distance from all existing objects
        too_close = False
        for pos_x, pos_z in existing_positions:
            dist = ((x - pos_x) ** 2 + (z - pos_z) ** 2) ** 0.5
            if dist < MIN_DISTANCE:
                too_close = True
                break
                
        if not too_close:
            return {"x": x, "y": 0, "z": z}
    
    # If we couldn't find a good position after MAX_ATTEMPTS, just return random
    return {
        "x": random.uniform(-10, 10),
        "y": 0,
        "z": random.uniform(-10, 10)
    }

async def handle_client(websocket):
    """Handle a connection from a client"""
    await register(websocket)
    
    try:
        # Keep the connection alive
        while True:
            # Process messages from client
            message = await websocket.recv()
            
            try:
                data = json.loads(message)
                
                # Handle position data response
                if data.get('type') == 'object-positions':
                    global WORLD_STATE
                    WORLD_STATE = data
                    logger.info(f"Received object positions. Objects: {len(data.get('objects', {}))}")
                    logger.debug(f"World state: {WORLD_STATE}")
                
                # Handle other message types
                # ...
                
            except json.JSONDecodeError:
                logger.error(f"Received invalid JSON: {message}")
                
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        await unregister(websocket)

async def main():
    # Start the WebSocket server
    server_host = "localhost"
    server_port = 8080
    
    # Start sending objects in the background
    asyncio.create_task(send_object(path="models/tree.glb", interval=5))
    
    # Optional: Start sending other types of objects
    # asyncio.create_task(send_object(path="models/rock.glb", interval=8))
    # asyncio.create_task(send_object(path="models/flower.glb", interval=10))
    
    # Start the server using the new API format
    server = await websockets.serve(handle_client, server_host, server_port)
    logger.info(f"WebSocket server started at ws://{server_host}:{server_port}")
    
    # Keep the server running forever
    await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main()) 