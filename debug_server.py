#!/usr/bin/env python3
"""
Debug launcher for FastAPI server.
Use this when VS Code debugger has configuration issues.

Usage:
1. Open this file in VS Code
2. Set breakpoints in your code (app/main.py, app/routers/*, etc.)
3. Press F5 or click "Run Python File" in debug panel
"""

import sys
import os

# Ensure we're in the server directory
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# Add server directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    import uvicorn

    print("=" * 70)
    print("🐛 DEBUG MODE - FastAPI Server")
    print("=" * 70)
    print(f"Python: {sys.executable}")
    print(f"Working Directory: {os.getcwd()}")
    print(f"PYTHONPATH: {sys.path[:3]}")
    print("=" * 70)
    print("\n🚀 Starting server at http://localhost:8000")
    print("📚 API Docs: http://localhost:8000/docs")
    print("⏸️  Set breakpoints in your code and they will trigger!\n")

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
