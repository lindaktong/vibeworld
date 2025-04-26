#!/bin/bash

# Create models directory if it doesn't exist
mkdir -p models

# Download a sample tree model from a CDN
# This is a small low-poly tree model that's free to use
curl -L "https://cdn.glitch.global/3b2e5e26-710c-432c-a551-3a09497f5b80/tree.glb?v=1619657167910" -o models/tree.glb

echo "Tree model downloaded to models/tree.glb" 