#!/bin/bash

# Make sure models directory exists
mkdir -p models

# Download the tree GLB model
./download_tree_model.sh

# Install required Python packages
pip install websockets

# Run the WebSocket server
python websocket_server.py 