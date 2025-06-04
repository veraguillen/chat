from azure.storage.blob import BlobServiceClient, generate_blob_sas, BlobSasPermissions
from datetime import datetime, timedelta
import os

# Configuración
connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING", "TU_CONNECTION_STRING")
container_name = "whatsapp-assets"  # Cambia si usaste otro nombre de contenedor
blob_service_client = BlobServiceClient.from_connection_string(connection_string)

def get_blob_url(blob_name):
    """Genera una URL fija con SAS para un blob"""
    blob_client = blob_service_client.get_blob_client(container=container_name, blob=blob_name)
    sas_token = generate_blob_sas(
        account_name=blob_service_client.account_name,
        container_name=container_name,
        blob_name=blob_name,
        permission=BlobSasPermissions(read=True),
        expiry=datetime.utcnow() + timedelta(days=365)
    )
    return f"{blob_client.url}?{sas_token}"

def list_blobs():
    """Lista todos los blobs en el contenedor"""
    container_client = blob_service_client.get_container_client(container_name)
    return [blob.name for blob in container_client.list_blobs()]

if __name__ == "__main__":
    # Listar archivos subidos
    blobs = list_blobs()
    print("Archivos en el contenedor:", blobs)
    
    # Generar URL para un archivo específico
    for blob_name in blobs:
        url = get_blob_url(blob_name)
        print(f"URL fija para {blob_name}: {url}")