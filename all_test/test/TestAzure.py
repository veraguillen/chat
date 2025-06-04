# test/TestAzure.py
import sys
from pathlib import Path

# Añadir el directorio raíz al path de Python
sys.path.append(str(Path(__file__).parent.parent))

from azure.storage.blob import BlobServiceClient
from app.core.config import settings

def test_azure_connection():
    """Prueba la conexión con Azure Storage y lista los contenedores y archivos."""
    try:
        # Mostrar información de conexión (sin credenciales completas)
        conn_str = settings.AZURE_STORAGE_CONNECTION_STRING
        safe_conn_str = conn_str.split(';')
        safe_conn_str = [part if not part.startswith('***REMOVED***;'.join(safe_conn_str)}")
        print(f"Contenedor: {settings.CONTAINER_NAME}")
        
        # Crear cliente de Blob Service
        blob_service_client = BlobServiceClient.from_connection_string(
            conn_str=conn_str
        )
        
        # Listar contenedores
        print("\n📦 Contenedores disponibles:")
        containers = blob_service_client.list_containers()
        for container in containers:
            print(f"  - {container['name']}")

        # Verificar archivos en el contenedor
        container_client = blob_service_client.get_container_client(settings.CONTAINER_NAME)
        print(f"\n📂 Archivos en '{settings.CONTAINER_NAME}':")
        
        blob_list = list(container_client.list_blobs())
        if not blob_list:
            print("  No se encontraron archivos en el contenedor.")
        else:
            for blob in blob_list:
                print(f"  - {blob.name} (Tamaño: {blob.size} bytes, Última modificación: {blob.last_modified})")
        
        # Verificar archivos FAISS
        faiss_files = [blob.name for blob in blob_list 
                      if blob.name.endswith(('.faiss', '.pkl', '.index'))]
        
        print("\n🔍 Archivos FAISS encontrados:")
        if faiss_files:
            for file in faiss_files:
                print(f"  - {file}")
        else:
            print("  No se encontraron archivos FAISS en el contenedor.")
            
        return True

    except Exception as e:
        print(f"\n❌ Error al conectar con Azure Storage: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🔍 Iniciando prueba de conexión con Azure Storage...")
    if test_azure_connection():
        print("\n✅ Prueba completada exitosamente!")
    else:
        print("\n❌ La prueba encontró problemas.")