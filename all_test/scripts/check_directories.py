"""
Script para verificar la estructura de directorios, archivos y configuración
necesarios para el sistema RAG del chatbot multimarca.

Este script ayuda a diagnosticar problemas antes de recrear el índice FAISS.
"""
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import json

# Ajuste de rutas para importar módulos de la app
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT_DIR))

# Intenta importar configuraciones del proyecto
try:
    from app.core.config import settings
    SETTINGS_LOADED = True
    print("✅ Configuraciones cargadas correctamente")
except ImportError:
    SETTINGS_LOADED = False
    print("❌ Error al cargar configuraciones: app.core.config no encontrado")
    settings = None

def check_directory(path: Path, expected_files_extension: str = None) -> Tuple[bool, int]:
    """
    Verifica si un directorio existe y contiene archivos (opcionalmente de una extensión específica).
    
    Args:
        path: Ruta del directorio a verificar
        expected_files_extension: Extensión de archivos a buscar (opcional)
    
    Returns:
        Tupla con (existe_directorio, número_de_archivos)
    """
    if not path.exists():
        return False, 0
    
    if not path.is_dir():
        return False, 0
    
    if expected_files_extension:
        files = list(path.glob(f"*.{expected_files_extension}"))
        return True, len(files)
    else:
        files = [f for f in path.iterdir() if f.is_file()]
        return True, len(files)

def list_first_n_files(path: Path, pattern: str = "*", n: int = 5) -> List[Path]:
    """Lista los primeros N archivos que coincidan con el patrón"""
    if not path.exists() or not path.is_dir():
        return []
    
    files = list(path.glob(pattern))
    return files[:n]

def check_brands_structure() -> Tuple[bool, Dict[str, int]]:
    """
    Verifica la estructura del directorio de marcas y cuenta archivos por marca.
    
    Returns:
        Tupla con (éxito, diccionario de recuento de archivos por marca)
    """
    brands_dir = Path(getattr(settings, "BRANDS_DIR", "data/brands"))
    
    if not brands_dir.exists() or not brands_dir.is_dir():
        return False, {}
    
    brand_counts = {}
    
    # Contar archivos txt directamente en el directorio brands
    txt_files = list(brands_dir.glob("*.txt"))
    if txt_files:
        brand_counts["root"] = len(txt_files)
    
    # Buscar subdirectorios para estructura jerárquica
    subdirs = [d for d in brands_dir.iterdir() if d.is_dir()]
    for subdir in subdirs:
        brand_name = subdir.name
        brand_txt_files = list(subdir.glob("*.txt"))
        brand_counts[brand_name] = len(brand_txt_files)
    
    return True, brand_counts

def check_azure_storage_config() -> bool:
    """
    Verifica si las variables de entorno para Azure Storage están configuradas.
    
    Returns:
        True si la configuración parece correcta, False en caso contrario
    """
    if not SETTINGS_LOADED:
        return False
    
    required_vars = [
        "STORAGE_ACCOUNT_NAME",
        "CONTAINER_NAME",
        "AZURE_STORAGE_CONNECTION_STRING",
        "FAISS_INDEX_NAME"
    ]
    
    all_vars_present = True
    for var in required_vars:
        if not hasattr(settings, var) or not getattr(settings, var):
            print(f"❌ Variable '{var}' no encontrada o vacía en la configuración")
            all_vars_present = False
        else:
            print(f"✅ Variable '{var}' configurada: '{getattr(settings, var)}'")
    
    return all_vars_present

def check_faiss_index_files() -> Dict[str, bool]:
    """
    Verifica si los archivos del índice FAISS existen localmente.
    
    Returns:
        Diccionario con estado de cada archivo del índice
    """
    faiss_folder = Path(getattr(settings, "FAISS_FOLDER_PATH", "faiss_index"))
    index_name = getattr(settings, "FAISS_INDEX_NAME", "index")
    
    result = {
        "folder_exists": faiss_folder.exists() and faiss_folder.is_dir(),
        "faiss_file_exists": (faiss_folder / f"{index_name}.faiss").exists(),
        "pkl_file_exists": (faiss_folder / f"{index_name}.pkl").exists(),
    }
    
    return result

# Función principal para realizar todas las verificaciones
def main():
    print("\n=== Verificación de Estructura para RAG Multimarca ===\n")
    
    # 1. Verificar configuraciones
    print("\n[1] Verificando configuraciones:")
    if SETTINGS_LOADED:
        brands_dir = Path(getattr(settings, "BRANDS_DIR", "data/brands"))
        faiss_dir = Path(getattr(settings, "FAISS_FOLDER_PATH", "faiss_index"))
        print(f"- BRANDS_DIR: {brands_dir}")
        print(f"- FAISS_FOLDER_PATH: {faiss_dir}")
    else:
        brands_dir = Path("data/brands")
        faiss_dir = Path("faiss_index")
        print("⚠️ Usando rutas por defecto (settings no disponible):")
        print(f"- BRANDS_DIR: {brands_dir}")
        print(f"- FAISS_FOLDER_PATH: {faiss_dir}")
    
    # 2. Verificar directorios y archivos
    print("\n[2] Verificando directorios:")
    
    # Verificar directorio brands
    brands_exists, brands_file_count = check_directory(brands_dir, "txt")
    print(f"- Directorio de marcas ({brands_dir}): {'✅ Existe' if brands_exists else '❌ No existe'}")
    if brands_exists:
        print(f"  - Contiene {brands_file_count} archivos TXT")
        print(f"  - Primeros archivos:")
        for file in list_first_n_files(brands_dir, "*.txt"):
            print(f"    * {file.name}")
    
    # Estructura detallada de marcas
    print("\n[3] Estructura detallada de marcas:")
    brands_ok, brand_counts = check_brands_structure()
    if brands_ok and brand_counts:
        print(f"- Se encontraron documentos para {len(brand_counts)} marca(s):")
        for brand, count in brand_counts.items():
            print(f"  - {brand}: {count} documentos")
    else:
        print("❌ No se encontró estructura de marcas válida")
    
    # Verificar directorio y archivos FAISS
    print("\n[4] Verificando archivos del índice FAISS:")
    faiss_status = check_faiss_index_files()
    if faiss_status["folder_exists"]:
        print(f"- Directorio FAISS ({faiss_dir}): ✅ Existe")
        print(f"- Archivo .faiss: {'✅ Existe' if faiss_status['faiss_file_exists'] else '❌ No existe'}")
        print(f"- Archivo .pkl: {'✅ Existe' if faiss_status['pkl_file_exists'] else '❌ No existe'}")
    else:
        print(f"- Directorio FAISS ({faiss_dir}): ❌ No existe")
    
    # Verificar configuración de Azure Storage
    print("\n[5] Verificando configuración de Azure Storage:")
    azure_config_ok = check_azure_storage_config()
    if azure_config_ok:
        print("✅ Configuración de Azure Storage completa")
    else:
        print("⚠️ Configuración de Azure Storage incompleta")
    
    # Resumen final
    print("\n=== Resumen de Verificación ===")
    if brands_exists and brands_file_count > 0 and faiss_status["folder_exists"]:
        print("✅ La estructura básica para recrear el índice FAISS está presente")
        
        if not (faiss_status["faiss_file_exists"] and faiss_status["pkl_file_exists"]):
            print("⚠️ Los archivos del índice FAISS no existen localmente. Ejecute:")
            print("   python scripts/recreate_faiss_index.py")
        else:
            print("✅ Los archivos del índice FAISS existen localmente. Para verificar su integridad, ejecute:")
            print("   python scripts/check_faiss_index_integrity.py")
        
        if not azure_config_ok:
            print("⚠️ Configuración de Azure Storage incompleta, la sincronización remota no funcionará")
    else:
        print("❌ Faltan elementos esenciales para recrear el índice FAISS:")
        if not brands_exists or brands_file_count == 0:
            print(f"- Cree el directorio {brands_dir} y añada documentos TXT de marcas")
        if not faiss_status["folder_exists"]:
            print(f"- Cree el directorio {faiss_dir} para almacenar el índice FAISS")

if __name__ == "__main__":
    main()
