#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Script para verificar la estructura y contenido del índice FAISS usando LangChain.
Analiza el índice cargado para confirmar que los documentos tienen contenido
y metadatos correctos, especialmente el campo 'brand' para filtrado.
"""

import sys
import os # Added for os.makedirs
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
import logging
import time
from pathlib import Path
from collections import Counter
from typing import Dict, Any

# Ajustar el path para importar módulos del proyecto
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))

try:
    from app.core.config import settings
    # Si la importación de settings inicializa toda la app, los logs de la app aparecerán.
    # Para un script más aislado, se podrían leer las variables de entorno directamente.
except ImportError as e:
    print(f"Error importando configuración del proyecto: {e}. Usando valores por defecto.")
    
    class DefaultSettings:
        def __init__(self):
            self.FAISS_FOLDER_PATH = PROJECT_ROOT / "data" / "faiss_index_kb_spanish_v1"
            self.FAISS_INDEX_NAME = "index"
            self.EMBEDDING_MODEL_NAME = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
            self.EMBEDDING_DEVICE = "cpu"
            # Añade aquí otras configuraciones que el script pueda necesitar,
            # como STORAGE_ACCOUNT_NAME y CONTAINER_NAME si se usaran para descargar.
    
    settings = DefaultSettings()

# Configuración de logging para este script
log_file_path = PROJECT_ROOT / "logs" / "verify_faiss_index_lc.log" # Nombre de log diferente
os.makedirs(log_file_path.parent, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout), # Asegurar que salga a la consola
        logging.FileHandler(log_file_path, mode="w", encoding='utf-8')
    ]
)
logger = logging.getLogger("verify_faiss_lc")


def get_file_info(file_path: Path) -> Dict[str, Any]:
    """Obtiene información básica sobre un archivo."""
    if not file_path.exists():
        return {
            "exists": False,
            "size_bytes": 0,
            "size_human": "0 B",
            "modified": None
        }
    
    size_bytes = file_path.stat().st_size
    modified_timestamp = file_path.stat().st_mtime
    modified_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(modified_timestamp))
    
    size_names = ["B", "KB", "MB", "GB"]
    size_human_val = size_bytes
    size_idx = 0
    while size_human_val >= 1024 and size_idx < len(size_names) - 1:
        size_human_val /= 1024
        size_idx += 1
    size_human = f"{size_human_val:.2f} {size_names[size_idx]}"
    
    return {
        "exists": True,
        "size_bytes": size_bytes,
        "size_human": size_human,
        "modified": modified_time
    }

def analyze_faiss_index_with_langchain(index_dir: Path, index_name: str = "index") -> Dict[str, Any]:
    """
    Analiza la estructura del índice FAISS cargándolo con LangChain.
    
    Args:
        index_dir: Directorio donde se encuentra el índice FAISS.
        index_name: Nombre base del índice (sin extensión).
        
    Returns:
        Diccionario con estadísticas y análisis del índice.
    """
    faiss_file = index_dir / f"{index_name}.faiss"
    pkl_file = index_dir / f"{index_name}.pkl"
    
    faiss_info = get_file_info(faiss_file)
    pkl_info = get_file_info(pkl_file)
    
    result = {
        "faiss_file": {
            "path": str(faiss_file),
            **faiss_info
        },
        "pkl_file": {
            "path": str(pkl_file),
            **pkl_info
        },
        "documents": {
            "total": 0,
            "with_content": 0,
            "empty_content": 0,
            "with_brand": 0,
            "without_brand": 0,
            "brands_count": Counter(),  # Usar Counter para facilitar conteo
            "metadata_fields": set()
        },
        "structure": {},
        "success": False,  # Inicializar success a False
        "error": None
    }
    
    if not (faiss_info["exists"] and pkl_info["exists"]):
        logger.error(f"Archivos del índice FAISS no encontrados en {index_dir}.")
        result["error"] = "Archivos de índice no encontrados."
        return result
    
    faiss_instance = None
    try:
        logger.info(f"Intentando cargar el índice FAISS desde '{index_dir}' con nombre base '{index_name}' usando LangChain.")
        embedding_model_name = getattr(settings, 'EMBEDDING_MODEL_NAME', 'sentence-transformers/paraphrase-multilingual-mpnet-base-v2')
        embedding_device = getattr(settings, 'EMBEDDING_DEVICE', 'cpu')
        logger.info(f"Usando modelo de embeddings: '{embedding_model_name}' en dispositivo: '{embedding_device}'.")

        embeddings_model = HuggingFaceEmbeddings(
            model_name=embedding_model_name,
            model_kwargs={'device': embedding_device},
        )

        faiss_instance = FAISS.load_local(
            folder_path=str(index_dir),
            embeddings=embeddings_model,
            index_name=index_name,
            allow_dangerous_deserialization=True
        )
        logger.info("Índice FAISS cargado exitosamente con LangChain.")
        
        result["structure"] = {
            "type": type(faiss_instance).__name__,
            "docstore_type": type(faiss_instance.docstore).__name__ if hasattr(faiss_instance, 'docstore') else 'N/A',
            "index_type": type(faiss_instance.index).__name__ if hasattr(faiss_instance, 'index') else 'N/A',
            "num_vectors_in_index": faiss_instance.index.ntotal if hasattr(faiss_instance, 'index') and faiss_instance.index else 0
        }

        # Procesar los documentos del docstore
        if hasattr(faiss_instance, 'docstore') and hasattr(faiss_instance.docstore, '_dict'):
            # .values() de un FAISS docstore._dict devuelve los Documentos directamente
            docs_data = list(faiss_instance.docstore._dict.values())
            result["documents"]["total"] = len(docs_data)
            
            if not docs_data:
                logger.warning("El docstore está presente pero no contiene documentos.")
                result["error"] = "Docstore presente pero vacío."
                result["success"] = False # No es un éxito si no hay documentos para verificar
            else:
                logger.info(f"Analizando {len(docs_data)} documentos del docstore...")
                all_metadata_keys = set()
                brand_counts = Counter()

                for doc in docs_data: # doc es un objeto Document
                    if not hasattr(doc, 'page_content') or not hasattr(doc, 'metadata'):
                        logger.warning(f"Documento con estructura inesperada encontrado: {type(doc)}")
                        continue

                    if doc.page_content and doc.page_content.strip():
                        result["documents"]["with_content"] += 1
                    else:
                        result["documents"]["empty_content"] += 1
                    
                    if doc.metadata:
                        all_metadata_keys.update(doc.metadata.keys())
                        brand = doc.metadata.get("brand")
                        if brand:
                            result["documents"]["with_brand"] += 1
                            brand_counts[str(brand)] += 1 # Asegurar que brand sea string para Counter
                        else:
                            result["documents"]["without_brand"] += 1
                    else:
                        result["documents"]["without_brand"] += 1

                result["documents"]["brands_count"] = dict(brand_counts)
                result["documents"]["metadata_fields"] = sorted(list(all_metadata_keys))

                if result["documents"]["with_content"] > 0 and result["documents"]["with_brand"] > 0:
                    result["success"] = True
                    logger.info("Análisis de documentos completado. Se encontraron documentos con contenido y metadatos de marca.")
                else:
                    result["success"] = False # No es un éxito completo si faltan datos clave
                    logger.warning("Análisis de documentos completado, pero no todos los documentos tienen contenido y/o marca.")
                    if result["documents"]["with_content"] == 0 and result["documents"]["total"] > 0:
                        result["error"] = "Ningún documento con contenido encontrado en el docstore."
                    elif result["documents"]["with_brand"] == 0 and result["documents"]["total"] > 0:
                        result["error"] = "Ningún documento con metadatos de 'brand' encontrado."
        else:
            logger.warning("El objeto FAISS cargado no tiene un 'docstore' o '_dict' accesible.")
            result["error"] = "Docstore no accesible en el objeto FAISS cargado."
            result["success"] = False

        return result

    except Exception as e:
        logger.error(f"Error crítico analizando el índice FAISS con LangChain: {e}", exc_info=True)
        result["error"] = str(e)
        result["success"] = False
        return result

def print_analysis_report(analysis: Dict[str, Any]) -> None:
    """Imprime un reporte formateado del análisis del índice FAISS."""
    # (Esta función se mantiene igual que la proporcionaste, no necesita cambios para la Opción A)
    print("\n" + "="*80)
    print(" REPORTE DE ANÁLISIS DEL ÍNDICE FAISS (CON LANGCHAIN) ".center(80, "="))
    print("="*80)
    
    print("\n[ARCHIVOS DEL ÍNDICE]")
    for file_type in ["faiss_file", "pkl_file"]:
        file_info = analysis.get(file_type, {})
        path_str = file_info.get("path", "N/A")
        print(f"  • {path_str}:")
        if file_info.get("exists"):
            print(f"    - Tamaño: {file_info.get('size_human', 'N/A')}")
            print(f"    - Modificado: {file_info.get('modified', 'N/A')}")
        else:
            print(f"    - ARCHIVO NO ENCONTRADO")
    
    print("\n[ESTRUCTURA DEL ÍNDICE CARGADO CON LANGCHAIN]")
    structure = analysis.get("structure", {})
    if structure:
        print(f"  • Tipo de VectorStore: {structure.get('type', 'Desconocido')}")
        print(f"  • Tipo de Docstore interno: {structure.get('docstore_type', 'Desconocido')}")
        print(f"  • Número de vectores en FAISS index: {structure.get('index_num_vectors', 'N/A')}")
    else:
        print("  • No se pudo determinar la estructura del índice cargado por LangChain.")
    
    print("\n[ESTADÍSTICAS DE DOCUMENTOS]")
    docs_stats = analysis.get("documents", {})
    total_docs = docs_stats.get("total", 0)
    
    if total_docs > 0:
        print(f"  • Total de documentos en Docstore: {total_docs}")
        
        with_content = docs_stats.get("with_content", 0)
        empty_content = docs_stats.get("empty_content", 0)
        with_content_pct = (with_content / total_docs * 100) if total_docs > 0 else 0
        
        print(f"  • Documentos con contenido: {with_content} ({with_content_pct:.1f}%)")
        if empty_content > 0:
             print(f"  • Documentos sin contenido: {empty_content} ({(empty_content / total_docs * 100):.1f}%)")
        
        with_brand = docs_stats.get("with_brand", 0)
        without_brand = docs_stats.get("without_brand", 0)
        with_brand_pct = (with_brand / total_docs * 100) if total_docs > 0 else 0

        print(f"  • Documentos con metadato 'brand' válido: {with_brand} ({with_brand_pct:.1f}%)")
        if without_brand > 0:
            print(f"  • Documentos sin metadato 'brand' o con 'brand' inválido: {without_brand} ({(without_brand / total_docs * 100):.1f}%)")
        
        metadata_fields = docs_stats.get("metadata_fields", [])
        if metadata_fields:
            print(f"  • Campos de metadatos encontrados: {', '.join(metadata_fields)}")
        
        brands_count = docs_stats.get("brands_count", {})
        if brands_count:
            print("\n[DISTRIBUCIÓN POR MARCA]")
            # Ordenar marcas para una salida consistente, si es necesario
            for brand, count in sorted(brands_count.items()):
                brand_pct = (count / total_docs * 100) if total_docs > 0 else 0
                print(f"  • {brand}: {count} documentos ({brand_pct:.1f}%)")
    else:
        print("  • No se encontraron documentos en el Docstore del índice.")
    
    print("\n[RESULTADO DE LA VERIFICACIÓN]")
    if analysis.get("success", False):
        print("  ✅ El índice FAISS (cargado con LangChain) parece VÁLIDO: Todos los documentos tienen contenido y metadato 'brand'.")
    else:
        print("  ❌ El índice FAISS (cargado con LangChain) parece INVÁLIDO o INCOMPLETO.")
        if analysis.get("error"):
            print(f"  • Error encontrado: {analysis['error']}")
        elif total_docs == 0:
             print(f"  • Causa: No se encontraron documentos en el docstore.")
        else:
            if docs_stats.get("with_content", 0) != total_docs:
                 print(f"  • Causa: No todos los documentos tienen contenido.")
            if docs_stats.get("with_brand", 0) != total_docs:
                 print(f"  • Causa: No todos los documentos tienen un metadato 'brand' válido.")
    
    print("\n" + "="*80 + "\n")

def main():
    """Función principal."""
    try:
        index_dir = settings.FAISS_FOLDER_PATH
        index_name = settings.FAISS_INDEX_NAME
    except AttributeError as e:
        logger.error(f"Error accediendo a settings (FAISS_FOLDER_PATH o FAISS_INDEX_NAME): {e}")
        logger.error("Asegúrate de que la configuración del proyecto se cargue correctamente o que DefaultSettings esté bien definido.")
        return 1
        
    logger.info(f"Analizando índice FAISS en '{index_dir}' (nombre base: '{index_name}') usando LangChain.")
    
    analysis_start_time = time.time()
    analysis_result = analyze_faiss_index_with_langchain(index_dir, index_name)
    analysis_duration = time.time() - analysis_start_time
    logger.info(f"Análisis completado en {analysis_duration:.2f} segundos.")
    
    print_analysis_report(analysis_result)
    
    return 0 if analysis_result.get("success", False) else 1

if __name__ == "__main__":
    # Para aislar un poco más la ejecución del script y evitar que la importación de 'settings'
    # de la app principal imprima todos sus logs antes que los de este script,
    # podríamos reconfigurar el logger raíz si 'app.core.config' ya lo configuró.
    # Esto es un poco hacky; idealmente, 'app.core.config' no debería tener efectos
    # secundarios de logging global al ser importado por un script de utilidad.
    
    # Si se detecta que el logger 'ChatbotMultimarcaBeta' (de la app) ya existe,
    # se asume que la config de la app ya se ejecutó.
    # if 'ChatbotMultimarcaBeta' in logging.Logger.manager.loggerDict:
    #     logger.info("Logger de la app principal detectado. Este script usará su propia config de logging.")
    #     # (La reconfiguración aquí puede ser compleja y depende de cómo esté hecho el logger de la app)

    sys.exit(main())