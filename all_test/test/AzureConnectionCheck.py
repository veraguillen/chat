import subprocess
import sys
import os
import json
from pathlib import Path
from azure.storage.blob import BlobServiceClient
from azure.identity import DefaultAzureCredential # Asegúrate de que esta importación esté
from azure.core.exceptions import AzureError, HttpResponseError # Para manejo de errores más específico
from dotenv import load_dotenv

# Cargar variables de entorno desde un archivo .env
load_dotenv()

# Configuración de Azure (usar variables de entorno para mayor seguridad)
# Asegúrate de que estas variables estén en tu .env o configuradas en tu entorno
AZURE_CONFIG = {
    'SUBSCRIPTION_ID': os.getenv('AZURE_SUBSCRIPTION_ID'),
    'RESOURCE_GROUP': os.getenv('AZURE_RESOURCE_GROUP'),
    # 'TENANT_NAME' no se usa directamente en las llamadas a CLI de esta manera,
    # pero es bueno tenerlo para referencia. 'LOCATION' tampoco se usa en este script.
}

# Configuración de Azure Storage (usar variables de entorno)
STORAGE_ACCOUNT_NAME = os.getenv('STORAGE_ACCOUNT_NAME', '').strip()  # Eliminar espacios y comentarios
# Eliminar comentarios y texto después del nombre de la cuenta
if '#' in STORAGE_ACCOUNT_NAME:
    STORAGE_ACCOUNT_NAME = STORAGE_ACCOUNT_NAME.split('#')[0].strip()
CONTAINER_NAME = os.getenv('CONTAINER_NAME', '').strip()  # Eliminar espacios y comentarios
# Eliminar comentarios y texto después del nombre del contenedor
if '#' in CONTAINER_NAME:
    CONTAINER_NAME = CONTAINER_NAME.split('#')[0].strip()

# Ruta al comando Azure CLI (ajusta si es necesario, aunque 'az' debería estar en el PATH)
# Si 'az' está en tu PATH, puedes simplemente usar ['az', ...]
# AZURE_CLI_PATH = r"C:\Program Files (x86)\Microsoft SDKs\Azure\CLI2\wbin\az.cmd"
# Usaremos 'az' directamente asumiendo que está en el PATH, ya que funcionó antes.
AZURE_CLI_COMMAND = "az"


def verify_azure_cli():
    """Verifica la instalación de Azure CLI y obtiene información de la versión."""
    try:
        result = subprocess.run([AZURE_CLI_COMMAND, "version", "--output", "json"], capture_output=True, text=True, check=True, shell=(os.name == 'nt'))
        version_info = json.loads(result.stdout)
        print("\n✅ Azure CLI verificado!")
        print(f"Versión: {version_info.get('azure-cli', 'desconocida')}")
        # 'python-location' puede no estar siempre presente o ser consistente, así que es opcional
        # print(f"Python CLI: {version_info.get('pythonLocation', 'desconocida')}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Error al ejecutar Azure CLI: {e}")
        print(f"   Stdout: {e.stdout}")
        print(f"   Stderr: {e.stderr}")
        return False
    except json.JSONDecodeError as e:
        print(f"❌ Error al procesar la salida de versión de Azure CLI: {e}")
        return False
    except Exception as e:
        print(f"❌ Fallo en la verificación de Azure CLI: {e}")
        return False

def check_and_configure_azure():
    """Verifica el estado de inicio de sesión y configura el entorno de Azure."""
    if not AZURE_CONFIG['SUBSCRIPTION_ID'] or not AZURE_CONFIG['RESOURCE_GROUP']:
        print("❌ Error: AZURE_SUBSCRIPTION_ID y AZURE_RESOURCE_GROUP deben estar definidos en el archivo .env o como variables de entorno.")
        return False
    if not STORAGE_ACCOUNT_NAME or not CONTAINER_NAME:
        print("❌ Error: STORAGE_ACCOUNT_NAME y CONTAINER_NAME deben estar definidos en el archivo .env o como variables de entorno.")
        return False

    try:
        print(f"\nUsando los siguientes parámetros de configuración:")
        print(f"  ID de Suscripción: {AZURE_CONFIG['SUBSCRIPTION_ID']}")
        print(f"  Grupo de Recursos: {AZURE_CONFIG['RESOURCE_GROUP']}")
        print(f"  Cuenta de Almacenamiento: {STORAGE_ACCOUNT_NAME}")
        print(f"  Contenedor: {CONTAINER_NAME.strip()}")

        # Verifica el estado de inicio de sesión
        result = subprocess.run([AZURE_CLI_COMMAND, "account", "show", "--output", "json"], capture_output=True, text=True, shell=(os.name == 'nt'))
        if result.returncode != 0 or not result.stdout.strip():
            print("\n🔑 No hay sesión activa o la sesión es inválida. Iniciando sesión en Azure...")
            # Intenta iniciar sesión sin especificar la suscripción primero, para que el usuario elija si hay varias
            # o para usar la predeterminada si solo hay una.
            subprocess.run([AZURE_CLI_COMMAND, "login"], check=True, shell=(os.name == 'nt'))
            result = subprocess.run([AZURE_CLI_COMMAND, "account", "show", "--output", "json"], capture_output=True, text=True, check=True, shell=(os.name == 'nt'))
        
        account_info = json.loads(result.stdout)
        current_user = account_info.get('user', {}).get('name', 'Usuario desconocido')
        print(f"\n✅ Sesión activa como: {current_user}")

        # Configura la suscripción específica
        print(f"\n🔧 Estableciendo suscripción activa a: {AZURE_CONFIG['SUBSCRIPTION_ID']}")
        subprocess.run([
            AZURE_CLI_COMMAND, "account", "set",
            "--subscription", AZURE_CONFIG['SUBSCRIPTION_ID']
        ], check=True, shell=(os.name == 'nt'))

        # Verifica la suscripción activa
        result = subprocess.run([AZURE_CLI_COMMAND, "account", "show", "--output", "json"], capture_output=True, text=True, check=True, shell=(os.name == 'nt'))
        active_subscription = json.loads(result.stdout)
        print(f"✅ Usando suscripción: {active_subscription.get('name')} (ID: {active_subscription.get('id')})")

        # Verifica si el grupo de recursos existe
        print(f"\n🔍 Verificando si el grupo de recursos '{AZURE_CONFIG['RESOURCE_GROUP']}' existe...")
        result = subprocess.run([
            AZURE_CLI_COMMAND, "group", "show",
            "--name", AZURE_CONFIG['RESOURCE_GROUP'],
            "--output", "json"
        ], capture_output=True, text=True, shell=(os.name == 'nt'))
        
        if result.returncode == 0:
            print(f"✅ El grupo de recursos '{AZURE_CONFIG['RESOURCE_GROUP']}' ya existe.")
        else:
            print(f"❌ El grupo de recursos '{AZURE_CONFIG['RESOURCE_GROUP']}' no existe o no tienes acceso.")
            print(f"   Stderr: {result.stderr}")
            return False

        # Verifica si la cuenta de almacenamiento existe
        print(f"\n🔍 Verificando si la cuenta de almacenamiento '{STORAGE_ACCOUNT_NAME}' existe en '{AZURE_CONFIG['RESOURCE_GROUP']}'... ✅")
        result = subprocess.run([
            AZURE_CLI_COMMAND, "storage", "account", "show",
            "--name", STORAGE_ACCOUNT_NAME,
            "--resource-group", AZURE_CONFIG['RESOURCE_GROUP'],
            "--output", "json"
        ], capture_output=True, text=True, shell=(os.name == 'nt'))
        
        if result.returncode == 0:
            print(f"✅ La cuenta de almacenamiento '{STORAGE_ACCOUNT_NAME}' ya existe.")
        else:
            print(f"❌ La cuenta de almacenamiento '{STORAGE_ACCOUNT_NAME}' no existe en el grupo de recursos '{AZURE_CONFIG['RESOURCE_GROUP']}' o no tienes acceso.")
            print(f"   Stderr: {result.stderr}")
            return False
        return True

    except subprocess.CalledProcessError as e:
        print(f"❌ Fallo durante la configuración de Azure con un comando CLI: {e}")
        print(f"   Comando: {' '.join(e.cmd)}")
        print(f"   Stdout: {e.stdout}")
        print(f"   Stderr: {e.stderr}")
        if "80192EE7" in str(e.stderr) or "AADSTS500011" in str(e.stderr): # Ejemplo de códigos de error comunes
             print("⚠️ Podría ser un problema de registro del dispositivo o políticas de AAD. Consulta con tu administrador de TI.")
        return False
    except json.JSONDecodeError as e:
        print(f"❌ Error al procesar la salida JSON de un comando CLI: {e}")
        return False
    except Exception as e:
        print(f"❌ Error inesperado durante la configuración de Azure: {e}")
        return False

def connect_to_storage():
    """Conecta a Azure Storage usando DefaultAzureCredential y lista los blobs."""
    print(f"\n🔄 Intentando conectar a Azure Storage...")
    print(f"   Cuenta de Almacenamiento: {STORAGE_ACCOUNT_NAME}")
    print(f"   Contenedor: {CONTAINER_NAME}")
    try:
        # Usa DefaultAzureCredential para autenticación.
        # Esta credencial intentará varios métodos, incluyendo la sesión activa de Azure CLI.
        credential = DefaultAzureCredential()
        
        # Construye la URL de la cuenta de almacenamiento
        account_url = f"https://{STORAGE_ACCOUNT_NAME}.blob.core.windows.net"

        # Crea el cliente de servicio de Blob
        print(f"   Creando BlobServiceClient para: {account_url}")
        blob_service_client = BlobServiceClient(account_url=account_url, credential=credential)
        
        # Obtiene el cliente del contenedor
        print(f"   Obteniendo cliente para el contenedor: {CONTAINER_NAME.strip()}")
        container_client = blob_service_client.get_container_client(CONTAINER_NAME.strip())

        # Lista los blobs (archivos) en el contenedor
        print(f"\n📂 Archivos en el contenedor '{CONTAINER_NAME.strip()}':")
        blob_list = container_client.list_blobs()
        
        count = 0
        for blob in blob_list:
            print(f" - {blob.name}")
            count += 1
        
        if count == 0:
            print(" (No se encontraron blobs. El contenedor podría estar vacío o no existir con ese nombre exacto, o aún tienes problemas de permisos).")
        
        print("✅ Conexión y listado de blobs (si los hay) exitoso.")
        return True

    except HttpResponseError as e: # Tipo de error común para problemas de autorización/HTTP de Azure SDK
        print(f"❌ Error HTTP al interactuar con Azure Storage: {e.message}")
        if e.status_code == 403: # Forbidden
             print("   Esto es un error de autorización (403 Forbidden).")
             print("   Causas Comunes:")
             print("     1. La identidad con la que estás autenticado (Azure CLI) no tiene los permisos RBAC necesarios (ej. 'Lector de datos de Storage Blob') en la cuenta de almacenamiento O en el contenedor específico.")
             print("     2. Los permisos RBAC se asignaron recientemente y aún no se han propagado (puede tardar varios minutos).")
             print("     3. Estás intentando acceder a un contenedor que no existe con el nombre proporcionado.")
             print(f"   Detalles del error: Status={e.status_code}, Reason='{e.reason}', ErrorCode='{e.error.code if e.error else 'N/A'}'")
        elif e.status_code == 404: # Not Found
            print(f"   Error: Recurso no encontrado (404). Es probable que el contenedor '{CONTAINER_NAME}' no exista en la cuenta '{STORAGE_ACCOUNT_NAME}'.")
        else:
            print(f"   Detalles del error: Status={e.status_code}, Reason='{e.reason}'")
        return False
    except AzureError as e: # Otras excepciones específicas del SDK de Azure
        print(f"❌ Error del SDK de Azure al conectar con Storage: {e}")
        return False
    except Exception as e: # Cualquier otra excepción inesperada
        print(f"❌ Error inesperado durante la conexión a Storage: {type(e).__name__} - {e}")
        return False

if __name__ == "__main__":
    if not verify_azure_cli():
        print("\nInstala Azure CLI o asegúrate de que esté en tu PATH.")
        sys.exit(1)

    if not check_and_configure_azure():
        print("\nRevisa la configuración de Azure, las variables de entorno o los permisos.")
        sys.exit(1)

    if not connect_to_storage():
        print("\nRevisa los permisos de la cuenta de almacenamiento, el nombre del contenedor y la propagación de roles RBAC.")
        sys.exit(1)

    print("\n🎉 ¡Verificación de conexión a Azure y Storage completada exitosamente!")
    print("\n🚀 Pasos siguientes (ejemplos):")
    print("1. Configura la base de datos (si es necesario).")
    print("2. Prepara tu aplicación Python para el despliegue.")
    print("3. Despliega tu aplicación a Azure App Service.")