"""
Main entry point for the FastAPI application.
This file is used by Gunicorn to serve the application.
"""
import uvicorn
from app.main.routes import router as main_router
from app.core.config import settings
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Chatbot API",
    description="API para el Chatbot Multimarca",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(main_router, prefix="/api/v1", tags=["api"])

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(settings.PORT) if hasattr(settings, 'PORT') else 8000,
        reload=settings.DEBUG if hasattr(settings, 'DEBUG') else True
    )
