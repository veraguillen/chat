import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

async def validate_azure_config():
    """Validates Azure configuration on startup"""
    try:
        # Validate Azure credentials
        credential = DefaultAzureCredential()
        
        # Validate Blob Storage
        blob_service = BlobServiceClient(
            account_url=f"https://{settings.storage_account_name}.blob.core.windows.net",
            credential=credential
        )
        container_client = blob_service.get_container_client(settings.container_name)
        blobs = list(container_client.list_blobs())
        logger.info(f"Successfully connected to Azure Blob Storage. Found {len(blobs)} blobs.")
        
        return True
    except Exception as e:
        logger.error(f"Azure validation failed: {e}")
        return False

if __name__ == "__main__":
    import asyncio
    asyncio.run(validate_azure_config())