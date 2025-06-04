from azure.storage.blob import BlobServiceClient
from azure.identity import DefaultAzureCredential
from app.core.config import settings
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)

class AzureStorageService:
    def __init__(self):
        self.account_name = settings.storage_account_name
        self.container_name = settings.container_name
        self.account_url = f"https://{self.account_name}.blob.core.windows.net"
        
        try:
            self.credential = DefaultAzureCredential()
            self.client = BlobServiceClient(
                account_url=self.account_url,
                credential=self.credential
            )
            self.container_client = self.client.get_container_client(self.container_name)
        except Exception as e:
            logger.error(f"Failed to initialize Azure Storage: {e}")
            raise

    async def list_blobs(self) -> List[str]:
        try:
            return [blob.name for blob in self.container_client.list_blobs()]
        except Exception as e:
            logger.error(f"Error listing blobs: {e}")
            return []

    async def get_blob_content(self, blob_name: str) -> Optional[str]:
        try:
            blob_client = self.container_client.get_blob_client(blob_name)
            return blob_client.download_blob().readall().decode()
        except Exception as e:
            logger.error(f"Error getting blob content for {blob_name}: {e}")
            return None