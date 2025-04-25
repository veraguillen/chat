# app/ai/knowledge_retriever.py
import os
from pathlib import Path
from app.core.config import settings # Asumimos que settings tiene KNOWLEDGE_BASE_PATH
from app.utils.logger import logger

# Determinar la ruta raíz del proyecto de forma más robusta
# Sube niveles desde este archivo (ai -> app -> raíz del proyecto)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Construye la ruta completa a la carpeta knowledge_base
# Asume que settings.KNOWLEDGE_BASE_PATH = "knowledge_base"
KNOWLEDGE_BASE_FULL_PATH = PROJECT_ROOT / settings.KNOWLEDGE_BASE_PATH

logger.info(f"Ruta base de conocimiento configurada: {KNOWLEDGE_BASE_FULL_PATH}")

# Mapeo para asegurar nombres de archivo correctos y en minúsculas
FILENAME_MAP = {
    "Fundacion": "fundacion.txt",
    "Ehecatl": "ehecatl.txt",
    "Javier Bazan": "javier_bazan.txt",
    "UDD": "udd.txt",
    "FES": "fes.txt"
}

# --- CORRECCIÓN: Quitar async ---
def get_brand_context(brand_name: str) -> str:
    """
    Lee el contenido del archivo de conocimiento para la marca especificada.
    Esta es una operación síncrona.
    Devuelve el contenido del archivo o un mensaje de error/vacío.
    """
    filename = FILENAME_MAP.get(brand_name)
    if not filename:
        logger.warning(f"Nombre de marca no mapeado a archivo: {brand_name}")
        return f"Error interno: Nombre de marca '{brand_name}' no reconocido."

    knowledge_file_path: Path = KNOWLEDGE_BASE_FULL_PATH / filename
    absolute_path_str = str(knowledge_file_path.resolve()) # Convertir a string para logging
    logger.debug(f"Intentando leer archivo: {absolute_path_str}")

    try:
        # Verificar si la carpeta base existe
        if not KNOWLEDGE_BASE_FULL_PATH.is_dir():
            logger.error(f"Directorio knowledge_base no encontrado en la ruta esperada: {KNOWLEDGE_BASE_FULL_PATH.resolve()}")
            return f"Error interno: Base de conocimientos no encontrada."

        # Verificar si el archivo específico existe
        if not knowledge_file_path.is_file():
            logger.error(f"Archivo de conocimiento no encontrado para brand '{brand_name}' en: {absolute_path_str}")
            return f"No tengo información detallada específica sobre '{brand_name}' en este momento."

        # Leer el archivo (operación síncrona)
        content = knowledge_file_path.read_text(encoding='utf-8')
        logger.info(f"Contexto cargado exitosamente para {brand_name} desde {filename} ({len(content)} caracteres)")
        return content.strip() # Devolver contenido sin espacios extra al inicio/final

    except PermissionError:
        logger.error(f"Error de permisos leyendo archivo '{absolute_path_str}' para {brand_name}.", exc_info=True)
        return f"Error interno: No se pudo leer la información para {brand_name}."
    except Exception as e:
        logger.error(f"Error inesperado leyendo archivo '{absolute_path_str}' para {brand_name}: {e}", exc_info=True)
        return f"Error interno al leer la información para {brand_name}."