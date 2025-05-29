from fastapi import FastAPI, Request, HTTPException, Depends, Body, Header
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import os
import json
import httpx

# Create a FastAPI app for Vercel deployment
app = FastAPI(title="IramBot API", description="API Gateway para IramBot")

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Basic health check endpoint
@app.get("/")
async def root():
    return {"status": "ok", "message": "IramBot API Gateway", "version": "1.0.0"}

@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "service": "IramBot API Gateway"}

# Endpoints para la aplicación principal
# Estos endpoints servirán como un gateway y redirigirán
# al servidor de procesamiento principal cuando esté disponible

@app.post("/api/webhook")
async def webhook_handler(request: Request):
    try:
        # Procesar el webhook aquí o redirigir a otro servicio
        data = await request.json()
        return {"status": "received", "message": "Webhook procesado correctamente"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/config")
async def get_config():
    # Proporcionar información de configuración básica
    return {
        "api_version": "1.0",
        "environment": os.environ.get("VERCEL_ENV", "development"),
        "features": {
            "webhook": True,
            "ml_processing": False  # Indicar que el procesamiento ML no está disponible aquí
        }
    }

# Manejador de errores
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"error": str(exc), "type": type(exc).__name__},
    )
