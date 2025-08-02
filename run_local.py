#!/usr/bin/env python3
"""
Lokales Entwicklungs-Skript für Simple Mailer
Startet die FastAPI-Anwendung lokal
"""

import uvicorn
from web_app import app

if __name__ == "__main__":
    print("Starting Simple Mailer Web Application...")
    print("Application will be available at: http://localhost:8000")
    print("Press Ctrl+C to stop the server")
    
    uvicorn.run(
        "web_app:app", 
        host="127.0.0.1", 
        port=8000, 
        reload=True,
        log_level="info"
    )
