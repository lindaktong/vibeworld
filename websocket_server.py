#!/usr/bin/env python
import asyncio
import websockets
import json
import random
import time
import logging
import uuid
import threading
from elevenlabs import stream
from elevenlabs.client import ElevenLabs
from dotenv import load_dotenv
import anthropic
import os
import assemblyai as aai
load_dotenv()

aai.settings.api_key = os.getenv("ASSEMBLYAI_API_KEY")
anthropic_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
elevenlabs_client = ElevenLabs(
    api_key=os.getenv("ELEVENLABS_API_KEY"),
)

model_response = None
transcriber = None
full_transcript = [
    {"role": "user", "content": "The user is walking around in a blank 3d virtual world. You are a helpful assistant that can create 3D objects in the world by synthesizing a text prompt and calling an API for the user. Your goal is to respond to the user's ideas and help them add objects to the world. Listen to the user's thoughts. Then, create a prompt for the API describing the new object to add to the world. When it's time to give the API prompt, say, 'Let's create a <insert description of an object>.' Note that the object description should be brief but descriptive, and it should describe a standalone object that can be dropped into a 3d world (i.e. don't describe the background or surroundings of the object). Make the description short and concise. Don't say anything before 'let's create' since we want the object description to come out fast."},
]


def on_error(error: aai.RealtimeError):
    print("An error occurred:", error)
    return  

def on_close():
    pass

def on_open(session_opened: aai.RealtimeSessionOpened):
    print("Session ID:", session_opened.session_id)
    return

def start_transcription():
    global transcriber
    print("inside start transcription")
    def transcription_thread():
        global transcriber
        transcriber = aai.RealtimeTranscriber(
            sample_rate=16000,
            on_data=on_data,
            on_error=on_error,
            on_open=on_open,
            on_close=on_close,
            end_utterance_silence_threshold=1000
        )
        transcriber.connect()
        microphone_stream = aai.extras.MicrophoneStream(sample_rate=16000)
        print('calling stream')
        transcriber.stream(microphone_stream)
        print('called stream')
    
    # Start transcription in a separate thread
    thread = threading.Thread(target=transcription_thread)
    thread.daemon = True  # Make thread terminate when main program exits
    thread.start()
    return thread

def stop_transcription():
    global transcriber
    if transcriber:
        transcriber.close()
        transcriber = None

def generate_audio(text: str):
    global elevenlabs_client
    global full_transcript
    full_transcript.append({"role": "assistant", "content": text})
    print(f"\nAI: {text}", end="\n")
    audio_stream = elevenlabs_client.text_to_speech.convert(
        text=text,
        voice_id="JBFqnCBsd6RMkjVDRZzb",
        model_id="eleven_multilingual_v2",
        output_format="mp3_44100_128",
    )
    stream(audio_stream)

def on_data(transcript: aai.RealtimeTranscript):
    if not transcript.text:
        return
    if isinstance(transcript, aai.RealtimeFinalTranscript):
        generate_ai_response(transcript.text)
    else:
        print(transcript.text, end="\r")

def generate_ai_response(transcript: str):
    global model_response
    print("calling stop transcription")
    stop_transcription()
    print('calling anthropic')
    global full_transcript
    full_transcript.append({"role": "user", "content": transcript})
    print(f"\nUser: {transcript}", end="\n")
    
    # USE CLAUDE HERE INSTEAD
    response = anthropic_client.messages.create(
        model="claude-3-7-sonnet-20250219",
        max_tokens=1024,
        messages=full_transcript
    )
    
    # MAKE SURE THIS IS THE RIGHT RESPONSE
    ai_response = response.content[0].text
    model_response = ai_response
    generate_audio(ai_response)
    # start_transcription()

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
    greeting = "Hello! What do you want to explore today?"
    generate_audio(greeting)
    while True:
        if CONNECTIONS:  # Only send if there are connections
            # First, request current positions from the client
            breakpoint()
            await request_positions()
            await asyncio.sleep(1)  # Wait a moment for positions to come back

            # Create an object based on user
            global model_response
            model_response = None
            
            # Start transcription in a separate thread
            print("starting transcription")
            transcription_thread = start_transcription()
            print("started transcription")
            
            # Wait for the model response with timeout
            timeout = 60  # 60 seconds timeout
            start_time = time.time()
            
            while model_response is None:
                print("Waiting for model response...")
                await asyncio.sleep(2)
                
                # # Check if we've timed out
                # if time.time() - start_time > timeout:
                #     print("Timeout waiting for model response")
                #     stop_transcription()
                #     break
            
            # print(f"Model response: {model_response}")
            
            prompt = model_response
            prompt = prompt.replace("Let's create", '')
            clean_prompt = prompt.lower().replace(' ', '_').replace('/', '_').replace(',', '_').replace('.', '_').replace('\'', '_').replace('\"', '_').replace('(', '_').replace(')', '_')
            path = f"models/{clean_prompt}.glb"
            command = f"python test_model_generation_client.py text '{prompt}' -o '{path}'"
            print(f"Running command: {command}")
            os.system(command)
            model_response = None
            
            # Get object type from filename (without extension)
            object_type = path.split('/')[-1].split('.')[0]
            
            # Create a message with positioning for the object
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
                    # "x": random.uniform(2.5, 7.5),
                    # "y": random.uniform(2.5, 7.5),
                    # "z": random.uniform(2.5, 7.5)
                    "x": 4,
                    "y": 4,
                    "z": 4
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
    # asyncio.create_task(send_object(path="models/cute_house.glb", interval=3))
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