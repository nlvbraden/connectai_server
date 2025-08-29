#!/usr/bin/env python3
"""Startup script for ConnectAI Server."""

import os
import sys
from pathlib import Path

# Add the app directory to Python path
app_dir = Path(__file__).parent / "app"
sys.path.insert(0, str(app_dir.parent))

# Import and run the server
from app.main import run_server

if __name__ == "__main__":
    print("Starting ConnectAI Server...")
    print("=" * 50)
    
    # Check for .env file
    env_file = Path(__file__).parent / ".env"
    if not env_file.exists():
        print("WARNING: .env file not found!")
        print("Please copy .env.example to .env and configure your settings.")
        print("=" * 50)
    
    try:
        run_server()
    except KeyboardInterrupt:
        print("\nServer stopped by user")
    except Exception as e:
        print(f"Error starting server: {e}")
        sys.exit(1)
