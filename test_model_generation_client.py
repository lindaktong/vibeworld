#!/usr/bin/env python
"""
Simple client for testing the Trellis API.

Example Usage:
python test_model_generation_client.py text "a cute house with flowers" -o models/cute_house_with_flowers.glb
"""

import argparse
import requests
import os
import sys
from pathlib import Path


def generate_from_text(prompt, seed=1, host="localhost", port=8000, output="model.glb"):
    """Generate a 3D model from a text prompt."""
    url = f"http://{host}:{port}/generate/text"
    print(f"Sending request to {url}")
    print(f"Prompt: '{prompt}'")
    print(f"Seed: {seed}")
    
    # Make request
    try:
        response = requests.post(
            url,
            json={"prompt": prompt, "seed": seed}
        )
        
        # Check if request was successful
        if response.status_code == 200:
            with open(output, "wb") as f:
                f.write(response.content)
            print(f"Model saved to {output}")
            return True
        else:
            print(f"Error: {response.status_code}")
            print(response.text)
            return False
    except Exception as e:
        print(f"Error: {e}")
        return False


def check_health(host="localhost", port=8000):
    """Check if the server is healthy."""
    url = f"http://{host}:{port}/health"
    print(url)
    try:
        response = requests.get(url)
        print(f"Response: {response.text}")
        return response.status_code == 200
    except Exception as e:
        print(f"Error: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Test the Trellis API")
    parser.add_argument("--host", default="localhost", help="Server host")
    parser.add_argument("--port", type=int, default=8000, help="Server port")
    
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Text command
    text_parser = subparsers.add_parser("text", help="Generate from text")
    text_parser.add_argument("prompt", help="Text prompt")
    text_parser.add_argument("--seed", type=int, default=1, help="Random seed")
    text_parser.add_argument("--output", "-o", default="model.glb", help="Output path")
    
    # Health check command
    health_parser = subparsers.add_parser("health", help="Check server health")
    
    args = parser.parse_args()
    
    if args.command == "text":
        generate_from_text(
            args.prompt, 
            args.seed, 
            args.host, 
            args.port, 
            args.output
        )
    elif args.command == "health":
        check_health(args.host, args.port)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()