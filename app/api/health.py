"""
Módulo para monitoreo de salud (health) de la aplicación.
Proporciona endpoints para verificar el estado de los componentes críticos.
"""
import os
import time
import asyncio
import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from datetime import datetime, timezone
from azure.storage.blob import BlobServiceClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db
from app.ai.rag_retriever import verify_faiss_index_access

# Configurar logger específico para este módulo
logger = logging.getLogger(__name__)

# Crear router para los endpoints de health
health_router = APIRouter(tags=["health"])

# Modelo para la respuesta de salud
class HealthResponse(BaseModel):
    status: str
    version: str
    timestamp: str
    uptime_seconds: float
    environment: str
    components: Dict[str, Dict[str, Any]]

# Variables globales para tracking
start_time = time.time()

@health_router.get("/health", response_model=HealthResponse)
async def health_check(db: AsyncSession = Depends(get_db)) -> HealthResponse:
    """
    Endpoint de verificación de salud de la aplicación.
    Verifica el estado general y todos los componentes críticos.
    """
    logger.info("Verificando estado de salud de la aplicación")
    
    # Resultados iniciales
    components = {
        "database": {"status": "unknown", "details": {}},
        "azure_storage": {"status": "unknown", "details": {}},
        "faiss_index": {"status": "unknown", "details": {}},
        "huggingface": {"status": "unknown", "details": {}}
    }
    
    # Estado general inicial
    overall_status = "ok"
    
    # Verificar base de datos
    try:
        # Ejecutar una consulta simple para verificar la conexión
        result = await db.execute("SELECT 1 AS is_alive")
        row = result.fetchone()
        is_alive = row[0] if row else None
        
        components["database"] = {
            "status": "ok" if is_alive == 1 else "error",
            "details": {
                "connection": "established",
                "host": settings.PGHOST or "unknown",
                "database": settings.PGDATABASE or "unknown"
            }
        }
    except Exception as e:
        logger.error(f"Error verificando la conexión a la base de datos: {e}")
        components["database"] = {
            "status": "error",
            "details": {"error": str(e)}
        }
        overall_status = "error"
    
    # Verificar Azure Storage
    try:
        if settings.AZURE_STORAGE_CONNECTION_STRING:
            blob_service_client = BlobServiceClient.from_connection_string(settings.AZURE_STORAGE_CONNECTION_STRING)
            container_client = blob_service_client.get_container_client(settings.CONTAINER_NAME)
            
            # Verificar existencia del contenedor
            container_exists = container_client.exists()
            
            # Verificar si los archivos del índice FAISS existen
            blob_list = list(container_client.list_blobs(name_starts_with=settings.FAISS_FOLDER_NAME))
            
            components["azure_storage"] = {
                "status": "ok" if container_exists else "error",
                "details": {
                    "container_exists": container_exists,
                    "storage_account": settings.STORAGE_ACCOUNT_NAME or "unknown",
                    "container_name": settings.CONTAINER_NAME or "unknown",
                    "blobs_found": len(blob_list)
                }
            }
        else:
            components["azure_storage"] = {
                "status": "error",
                "details": {"error": "AZURE_STORAGE_CONNECTION_STRING no está configurado"}
            }
            overall_status = "error"
    except Exception as e:
        logger.error(f"Error verificando Azure Storage: {e}")
        components["azure_storage"] = {
            "status": "error", 
            "details": {"error": str(e)}
        }
        overall_status = "error"
    
    # Verificar índice FAISS
    try:
        faiss_status = await verify_faiss_index_access()
        components["faiss_index"] = {
            "status": "ok" if faiss_status["success"] else "error",
            "details": faiss_status
        }
        if not faiss_status["success"]:
            overall_status = "degraded"
    except Exception as e:
        logger.error(f"Error verificando índice FAISS: {e}")
        components["faiss_index"] = {
            "status": "error",
            "details": {"error": str(e)}
        }
        overall_status = "degraded"
    
    # Verificar HuggingFace (simple check)
    try:
        components["huggingface"] = {
            "status": "ok" if settings.HUGGINGFACE_TOKEN else "warning",
            "details": {
                "token_configured": bool(settings.HUGGINGFACE_TOKEN),
                "embedding_model": settings.EMBEDDING_MODEL_NAME
            }
        }
    except Exception as e:
        components["huggingface"] = {
            "status": "error",
            "details": {"error": str(e)}
        }
    
    # Crear respuesta
    response = HealthResponse(
        status=overall_status,
        version=settings.PROJECT_VERSION,
        timestamp=datetime.now(timezone.utc).isoformat(),
        uptime_seconds=time.time() - start_time,
        environment=settings.ENVIRONMENT,
        components=components
    )
    
    # Log para diagnóstico
    logger.info(f"Health check completado. Estado: {overall_status}")
    
    return response

# Endpoint más simple para heartbeats
@health_router.get("/ping")
async def ping():
    """Endpoint simple para verificar si la aplicación está en funcionamiento"""
    return {"status": "alive", "timestamp": datetime.now(timezone.utc).isoformat()}
