from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import os

# Create a minimal FastAPI app for Vercel deployment
app = FastAPI(title="IramBot API")

# Basic health check endpoint
@app.get("/")
async def root():
    return {"status": "ok", "message": "IramBot API is running"}

@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "service": "IramBot API"}

# Error handling
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"error": str(exc), "type": type(exc).__name__},
    )
