#!/usr/bin/env python3
"""
Script para verificar la carga de RAG desde Azure Blob Storage.
"""

import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import List, Optional
from azure.storage.blob import BlobServiceClient

# Configuración básica de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Configuración directa de Azure Storage
CONFIG = {
    "STORAGE_ACCOUNT_NAME": "chat2025",
    "CONTAINER_NAME": "chat2025",
    "AZURE_STORAGE_CONNECTION_STRING": (
        "DefaultEndpointsProtocol=https;"
        "AccountName=chat2025;"
        "***REMOVED***;"
        "EndpointSuffix=core.windows.net"
    ),
    "FAISS_INDEX_NAME": "index"
}

async def download_faiss_files() -> bool:
    """Descarga los archivos FAISS desde Azure Blob Storage."""
    try:
        # Crear cliente de Blob Service
        blob_service_client = BlobServiceClient.from_connection_string(
            CONFIG["AZURE_STORAGE_CONNECTION_STRING"]
        )
        
        container_client = blob_service_client.get_container_client(CONFIG["CONTAINER_NAME"])
        
        # Archivos a descargar
        files_to_download = [
            f"{CONFIG['FAISS_INDEX_NAME']}.faiss",
            f"{CONFIG['FAISS_INDEX_NAME']}.pkl"
        ]
        
        # Crear directorio local si no existe
        local_dir = Path("data/faiss_indices")
        local_dir.mkdir(parents=True, exist_ok=True)
        
        # Descargar archivos
        for blob_name in files_to_download:
            blob_client = container_client.get_blob_client(blob_name)
            local_path = local_dir / blob_name
            
            logger.info(f"Descargando {blob_name} a {local_path}...")
            
            with open(local_path, "wb") as download_file:
                download_file.write(blob_client.download_blob().readall())
            
            logger.info(f"Archivo {blob_name} descargado exitosamente")
        
        return True
        
    except Exception as e:
        logger.error(f"Error al descargar archivos FAISS: {str(e)}", exc_info=True)
        return False

async def main():
    logger.info("=== Iniciando verificación de RAG ===")
    
    # Verificar conexión a Azure Storage
    logger.info("Verificando conexión a Azure Storage...")
    try:
        blob_service_client = BlobServiceClient.from_connection_string(
            CONFIG["AZURE_STORAGE_CONNECTION_STRING"]
        )
        
        # Listar contenedores para probar la conexión
        containers = blob_service_client.list_containers()
        container_names = [container.name for container in containers]
        logger.info(f"Conexión exitosa. Contenedores disponibles: {', '.join(container_names)}")
        
        # Verificar si el contenedor existe
        if CONFIG["CONTAINER_NAME"] not in container_names:
            logger.error(f"El contenedor '{CONFIG['CONTAINER_NAME']}' no existe")
            return
        
        # Verificar archivos en el contenedor
        container_client = blob_service_client.get_container_client(CONFIG["CONTAINER_NAME"])
        blobs = list(container_client.list_blobs())
        logger.info(f"Archivos en el contenedor {CONFIG['CONTAINER_NAME']}:")
        for blob in blobs:
            logger.info(f"  - {blob.name} (Tamaño: {blob.size} bytes)")
        
        # Descargar archivos FAISS
        logger.info("\nIniciando descarga de archivos FAISS...")
        success = await download_faiss_files()
        
        if success:
            logger.info("=== Verificación completada con éxito ===")
            logger.info("Los archivos FAISS se han descargado en: data/faiss_indices/")
        else:
            logger.error("=== La verificación falló ===")
            
    except Exception as e:
        logger.error(f"Error de conexión a Azure Storage: {str(e)}", exc_info=True)

if __name__ == "__main__":
    asyncio.run(main())