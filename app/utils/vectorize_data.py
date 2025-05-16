import logging
from pathlib import Path
import sys
import os # Importado para os.environ.get, aunque ahora no lo usaremos en la línea problemática

# --- Ajuste de Rutas para Importar Configuración y Módulos de la App ---
# Asumiendo que este script está en /ruta/al/proyecto/app/utils/vectorize_data.py
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT_DIR = SCRIPT_DIR.parent.parent  # Esto debería ser /ruta/al/proyecto
sys.path.insert(0, str(PROJECT_ROOT_DIR)) # Añadir la raíz del proyecto al PYTHONPATH

try:
    from langchain.schema import Document
    from langchain.text_splitter import RecursiveCharacterTextSplitter
    from langchain_huggingface import HuggingFaceEmbeddings
    from langchain_community.vectorstores import FAISS

    from app.core.config import settings # Importar la instancia de settings directamente
    # !! AJUSTA ESTA IMPORTACIÓN SEGÚN DÓNDE ESTÉ TU FUNCIÓN normalize_brand_name !!
    from app.main.webhook_handler import normalize_brand_name
    # from app.utils.text_utils import normalize_brand_name # Alternativa si la mueves
except ImportError as e:
    print(f"Error al importar módulos necesarios: {e}")
    print(f"Asegúrate de que el script esté en la ubicación correcta (app/utils) y que el PYTHONPATH incluya la raíz del proyecto ('{PROJECT_ROOT_DIR}').")
    print(f"sys.path actual: {sys.path}")
    logging.basicConfig(level=logging.ERROR)
    logging.error(f"Error al importar módulos: {e}", exc_info=True)
    exit(1)


# --- Configuración de Logging (usando settings) ---
settings.LOG_DIR.mkdir(parents=True, exist_ok=True)
log_file_path = settings.LOG_DIR / "vectorization.log"

vectorizer_logger = logging.getLogger("vectorizer_script")
vectorizer_logger.setLevel(settings.log_level.upper())

fh = logging.FileHandler(log_file_path, mode='w')
fh.setFormatter(logging.Formatter(settings.log_format))
vectorizer_logger.addHandler(fh)

ch = logging.StreamHandler()
ch.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
vectorizer_logger.addHandler(ch)

vectorizer_logger.propagate = False

# --- Constantes y Configuraciones desde Settings ---
EMBEDDING_MODEL_NAME = settings.embedding_model_name
CHUNK_SIZE = settings.rag_chunk_size
CHUNK_OVERLAP = settings.rag_chunk_overlap
FAISS_INDEX_PATH = str(settings.faiss_folder_path)
MIN_FILE_CONTENT_LENGTH = 10

# --- Definición de Directorios Fuente desde Settings ---
SOURCE_DIRS_TO_SCAN = []
if settings.KNOWLEDGE_BASE_DIR and settings.KNOWLEDGE_BASE_DIR.is_dir():
    SOURCE_DIRS_TO_SCAN.append({"path": settings.KNOWLEDGE_BASE_DIR, "type": "kb", "name": "Knowledge Base"})
    vectorizer_logger.info(f"Directorio Knowledge Base a escanear: {settings.KNOWLEDGE_BASE_DIR}")
else:
    vectorizer_logger.warning(f"Directorio KNOWLEDGE_BASE_DIR ('{settings.KNOWLEDGE_BASE_DIR}') no configurado, no existe o no es un directorio. No se escaneará.")

if settings.BRANDS_DIR and settings.BRANDS_DIR.is_dir():
    SOURCE_DIRS_TO_SCAN.append({"path": settings.BRANDS_DIR, "type": "brand", "name": "Brands"})
    vectorizer_logger.info(f"Directorio Brands a escanear: {settings.BRANDS_DIR}")
else:
    vectorizer_logger.warning(f"Directorio BRANDS_DIR ('{settings.BRANDS_DIR}') no configurado, no existe o no es un directorio. No se escaneará.")


# --- Inicio del Script ---
vectorizer_logger.info("="*30 + " Iniciando Proceso de Vectorización " + "="*30)
vectorizer_logger.info(f"Usando modelo de embeddings: {EMBEDDING_MODEL_NAME}")
vectorizer_logger.info(f"Directorio Raíz del Proyecto (calculado): {PROJECT_ROOT_DIR}")
vectorizer_logger.info(f"Ruta del Índice FAISS a crear/actualizar: {FAISS_INDEX_PATH}")
vectorizer_logger.info(f"Ruta del Archivo Log: {log_file_path}")

if not SOURCE_DIRS_TO_SCAN:
    vectorizer_logger.error("No hay directorios fuente válidos (Knowledge Base o Brands) configurados para escanear. Saliendo.")
    exit(1)

all_documents = []
files_processed_total = 0
files_skipped_empty_total = 0
files_failed_read_total = 0

for source_info in SOURCE_DIRS_TO_SCAN:
    current_source_dir = source_info["path"]
    doc_type = source_info["type"]
    source_name = source_info["name"]
    vectorizer_logger.info(f"--- Escaneando Directorio: '{source_name}' en '{current_source_dir}' (tipo: {doc_type}) ---")

    try:
        current_files = list(current_source_dir.rglob("*.txt"))
        vectorizer_logger.info(f"Encontrados {len(current_files)} archivos .txt potenciales en '{current_source_dir}'.")

        if not current_files:
            vectorizer_logger.info(f"No se encontraron archivos .txt en '{current_source_dir}'. Saltando este directorio.")
            continue

        for txt_file_path in current_files:
            relative_log_path = txt_file_path.relative_to(PROJECT_ROOT_DIR) if txt_file_path.is_relative_to(PROJECT_ROOT_DIR) else txt_file_path
            vectorizer_logger.debug(f"Procesando archivo: {relative_log_path}")
            try:
                with open(txt_file_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                if not content or len(content.strip()) < MIN_FILE_CONTENT_LENGTH:
                    vectorizer_logger.warning(f"Saltando archivo vacío o muy corto: {relative_log_path}")
                    files_skipped_empty_total += 1
                    continue

                source_filename = txt_file_path.name
                relative_path_in_scanned_dir = str(txt_file_path.relative_to(current_source_dir))

                metadata = {
                    'source': relative_path_in_scanned_dir,
                    'filename': source_filename,
                    'doc_type': doc_type
                }

                if doc_type == "kb":
                    parent_folder = txt_file_path.parent
                    if parent_folder != current_source_dir:
                        metadata['category'] = parent_folder.name
                    else:
                        metadata['category'] = "General"
                elif doc_type == "brand":
                    brand_name_from_file = source_filename.replace(".txt", "")
                    normalized_brand = normalize_brand_name(brand_name_from_file)
                    metadata['brand'] = normalized_brand
                    metadata['category'] = "BrandSpecific"

                doc = Document(page_content=content, metadata=metadata)
                all_documents.append(doc)
                files_processed_total += 1

            except UnicodeDecodeError:
                vectorizer_logger.error(f"Error de codificación leyendo {relative_log_path}. Asegúrate que sea UTF-8.", exc_info=False)
                files_failed_read_total += 1
            except Exception as e_read:
                vectorizer_logger.error(f"Error inesperado leyendo o procesando el archivo {relative_log_path}: {e_read}", exc_info=True)
                files_failed_read_total += 1

    except Exception as e_glob:
        vectorizer_logger.error(f"Error buscando archivos en {current_source_dir}: {e_glob}", exc_info=True)

if not all_documents:
    vectorizer_logger.error("No se cargó ningún documento válido para procesar de los directorios fuente especificados.")
    vectorizer_logger.info(f"Resumen: Procesados: {files_processed_total}. Saltados: {files_skipped_empty_total}. Fallidos: {files_failed_read_total}.")
    exit(1)

vectorizer_logger.info(f"Total documentos cargados y pre-procesados de todas las fuentes: {files_processed_total}")
vectorizer_logger.info(f"(Saltados por vacíos/cortos: {files_skipped_empty_total}, Fallos de lectura: {files_failed_read_total})")

vectorizer_logger.info(f"Dividiendo {len(all_documents)} documentos en chunks (Tamaño: {CHUNK_SIZE}, Solapamiento: {CHUNK_OVERLAP})...")
try:
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        length_function=len,
        add_start_index=True,
    )
    chunked_documents = text_splitter.split_documents(all_documents)
    vectorizer_logger.info(f"Número total de chunks creados: {len(chunked_documents)}")
    if not chunked_documents:
        vectorizer_logger.error("La división no produjo ningún chunk. Revisa los documentos de entrada y la configuración del splitter.")
        exit(1)

    if chunked_documents:
        vectorizer_logger.debug(f"Metadatos del primer chunk: {chunked_documents[0].metadata}")
        if len(chunked_documents) > 1:
            vectorizer_logger.debug(f"Metadatos del último chunk: {chunked_documents[-1].metadata}")
except Exception as e_split:
     vectorizer_logger.error(f"Error durante la división de documentos: {e_split}", exc_info=True)
     exit(1)

vectorizer_logger.info(f"Inicializando modelo de embeddings: '{EMBEDDING_MODEL_NAME}'...")
try:
    # FORZAR CPU para la creación de embeddings en este script para simplificar.
    device_to_use = 'cpu' # <--- CORRECCIÓN APLICADA AQUÍ
    
    embedding_model = HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL_NAME,
        model_kwargs={'device': device_to_use}, # <--- Usa la variable device_to_use
        encode_kwargs={'normalize_embeddings': True} 
    )
    vectorizer_logger.info(f"Modelo embeddings '{EMBEDDING_MODEL_NAME}' inicializado correctamente en '{device_to_use}'.")
except Exception as e_embed:
     vectorizer_logger.error(f"Error fatal inicializando modelo de embeddings '{EMBEDDING_MODEL_NAME}': {e_embed}", exc_info=True)
     vectorizer_logger.error("Posibles causas: biblioteca 'sentence-transformers' no instalada, nombre del modelo incorrecto, problemas de descarga (requiere internet la primera vez), o problemas de memoria.")
     exit(1)

vectorizer_logger.info(f"Creando/Actualizando índice vectorial FAISS desde {len(chunked_documents)} chunks. Esto puede tardar...")
try:
    Path(FAISS_INDEX_PATH).parent.mkdir(parents=True, exist_ok=True)

    vectorizer_logger.info(f"Creando un nuevo índice FAISS en '{FAISS_INDEX_PATH}' (reemplazará cualquier índice existente en esa ruta).")
    vector_store = FAISS.from_documents(chunked_documents, embedding_model)

    vectorizer_logger.info("Índice FAISS creado en memoria.")
    vectorizer_logger.info(f"Guardando índice FAISS en disco en: {FAISS_INDEX_PATH}")
    # Langchain FAISS.save_local guarda usando "index" como nombre base por defecto
    # si FAISS_INDEX_PATH es solo una carpeta.
    # El nombre base usado aquí debe coincidir con settings.faiss_index_name para la carga.
    # Si settings.faiss_index_name es "index" (recomendado), no se necesita pasar index_name aquí.
    vector_store.save_local(folder_path=FAISS_INDEX_PATH, index_name=settings.faiss_index_name)
    vectorizer_logger.info(f"¡Índice FAISS guardado exitosamente en '{FAISS_INDEX_PATH}' con nombre base '{settings.faiss_index_name}'!")
except Exception as e_faiss:
    vectorizer_logger.error(f"Error fatal creando o guardando el índice FAISS en '{FAISS_INDEX_PATH}': {e_faiss}", exc_info=True)
    exit(1)

vectorizer_logger.info("="*30 + " Proceso de Vectorización Finalizado Exitosamente " + "="*30)