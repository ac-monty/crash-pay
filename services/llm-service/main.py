"""
UPDATED: Main entry point for the refactored LLM service.
This file now points to the clean, modular app structure.

The old monolithic 2,883-line main.py has been refactored into:
- app/config/settings.py      (Configuration management)
- app/models/                 (Request/response models)
- app/services/               (Business logic)
- app/api/routes/             (API endpoints)  
- app/utils/                  (Utilities and logging)
- app/main.py                 (Clean FastAPI app)
"""

from app.main import app

# Export the app for uvicorn
__all__ = ["app"]

if __name__ == "__main__":
    import uvicorn
    import os
    
    # Run the application
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True if os.getenv("ENVIRONMENT", "development") == "development" else False,
        log_level="info"
    )
