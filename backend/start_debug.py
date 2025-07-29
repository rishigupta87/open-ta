#!/usr/bin/env python3
"""Debug startup script for VSCode remote debugging"""

import os
import sys
import debugpy
import uvicorn

def start_with_debug():
    """Start the application with debugpy enabled"""
    
    # Get debug configuration from environment
    debug_enabled = os.getenv("DEBUG_ENABLED", "false").lower() == "true"
    debug_port = int(os.getenv("DEBUG_PORT", "5678"))
    debug_wait = os.getenv("DEBUG_WAIT", "false").lower() == "true"
    
    if debug_enabled:
        print(f"🐛 Starting debugpy on port {debug_port}")
        print(f"🔗 Attach your debugger to localhost:{debug_port}")
        
        # Configure debugpy
        debugpy.listen(("0.0.0.0", debug_port))
        print(f"✅ Debugpy server listening on 0.0.0.0:{debug_port}")
        
        if debug_wait:
            print("⏳ Waiting for debugger to attach...")
            debugpy.wait_for_client()
            print("✅ Debugger attached!")
        else:
            print("🚀 Starting without waiting for debugger")
    
    # Start the FastAPI application
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # Enable reload for hot reloading
        reload_dirs=["/app"],  # Watch the app directory
        log_level="info"
    )

if __name__ == "__main__":
    start_with_debug()
