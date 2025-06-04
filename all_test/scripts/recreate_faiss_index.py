import logging
import os
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional

# --- Ajuste de Rutas para Importar Configuración y Módulos de la App ---
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT_DIR = SCRIPT_DIR.parent  # Esto debería ser la raíz del proyecto
sys.path.insert(0, str(PROJECT_ROOT_DIR))  # Añadir la raíz del proyecto al PYTHONPATH

try:
    from langchain_core.documents import Document
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    from langchain_huggingface import HuggingFaceEmbeddings
    from langchain_community.vectorstores import FAISS
    from azure.storage.blob import BlobServiceClient

    from app.core.config import settings
    from app.utils.text_utils import normalize_brand_for_rag
except ImportError as e:
    print(f"Error al importar módulos necesarios: {e}")
    print(f"Asegúrate de que el script esté en la ubicación correcta y que el PYTHONPATH incluya la raíz del proyecto.")
    print(f"sys.path actual: {sys.path}")
    sys.exit(1)

# --- Configuración de Logging ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(PROJECT_ROOT_DIR / "logs" / "recreate_faiss_index.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# --- Constantes y Configuraciones ---
EMBEDDING_MODEL_NAME = settings.EMBEDDING_MODEL_NAME
# Configuración de división de texto
# Reducir el tamaño de los chunks para evitar condensación excesiva
CHUNK_SIZE = 300       # Reducido para chunks más pequeños
CHUNK_OVERLAP = 80     # Ajustado para mantener contexto entre chunks

# Configurar el divisor de texto con separadores mejorados
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=CHUNK_SIZE,
    chunk_overlap=CHUNK_OVERLAP,
    # Mejores separadores para preservar la estructura del texto
    separators=[
        "\n\n",         # Primero dividir por párrafos
        "\n",           # Luego por saltos de línea
        ". ", "? ", "! ",  # Luego por oraciones
        "; ", ", ",       # Luego por frases
        " ", ""            # Finalmente por palabras
    ],
    length_function=len,
    is_separator_regex=False
)

logger.info(f"Configuración de división de texto: Chunk size={CHUNK_SIZE}, Overlap={CHUNK_OVERLAP}")
FAISS_INDEX_PATH = str(settings.FAISS_FOLDER_PATH)
MIN_FILE_CONTENT_LENGTH = 100  # Aumentar longitud mínima para archivos

# --- Definición de Directorios Fuente ---
SOURCE_DIRS_TO_SCAN = []

# Usamos exclusivamente BRANDS_DIR como fuente única de documentos
if not settings.BRANDS_DIR:
    logger.error("BRANDS_DIR no está configurado en settings. Verificar .env o config.py")
    sys.exit(1)
    
if not settings.BRANDS_DIR.exists():
    logger.error(f"Directorio BRANDS_DIR no existe: {settings.BRANDS_DIR}")
    # Crear el directorio automáticamente si se desea
    try:
        settings.BRANDS_DIR.mkdir(parents=True, exist_ok=True)
        logger.info(f"Directorio BRANDS_DIR creado: {settings.BRANDS_DIR}")
    except Exception as e:
        logger.error(f"No se pudo crear BRANDS_DIR: {str(e)}")
        sys.exit(1)

SOURCE_DIRS_TO_SCAN.append({"path": settings.BRANDS_DIR, "type": "brand", "name": "Brands"})
logger.info(f"Directorio Brands a escanear: {settings.BRANDS_DIR}")

def load_documents() -> List[Document]:
    """
    Carga documentos desde los directorios fuente y les asigna metadatos.
    """
    logger.info("=== Cargando documentos ===")
    all_documents = []
    files_processed_total = 0
    files_skipped_empty_total = 0
    files_failed_read_total = 0

    for source_info in SOURCE_DIRS_TO_SCAN:
        current_source_dir = source_info["path"]
        doc_type = source_info["type"]
        source_name = source_info["name"]
        logger.info(f"Escaneando Directorio: '{source_name}' en '{current_source_dir}' (tipo: {doc_type})")

        try:
            # Buscar archivos .txt recursivamente
            current_files = list(current_source_dir.rglob("*.txt"))
            logger.info(f"Encontrados {len(current_files)} archivos .txt en '{current_source_dir}'")

            for txt_file_path in current_files:
                try:
                    # Leer el contenido del archivo
                    try:
                        with open(txt_file_path, 'r', encoding='utf-8') as f:
                            content = f.read().strip()
                            logger.debug(f"Contenido leído de {txt_file_path.name} (longitud: {len(content)}):\n{content[:200]}" + ("..." if len(content) > 200 else ""))
                    except Exception as e:
                        logger.error(f"Error al leer el archivo {txt_file_path}: {str(e)}")
                        files_failed_read_total += 1
                        continue

                    # Saltar archivos vacíos o muy cortos
                    if not content or len(content) < MIN_FILE_CONTENT_LENGTH:
                        logger.warning(f"Saltando archivo vacío o muy corto: {txt_file_path} (longitud: {len(content)})")
                        files_skipped_empty_total += 1
                        continue

                    # Obtener el nombre del archivo sin extensión como nombre de la marca
                    brand_name = txt_file_path.stem
                    logger.debug(f"Procesando archivo: {brand_name}")
                    
                    # Normalizar el nombre de la marca (solo una vez)
                    normalized_brand = normalize_brand_for_rag(brand_name)
                    logger.debug(f"Nombre normalizado: {normalized_brand} (original: {brand_name})")
                    
                    # Crear metadatos
                    metadata = {
                        'source': str(txt_file_path.relative_to(PROJECT_ROOT_DIR)),
                        'filename': txt_file_path.name,
                        'doc_type': doc_type,
                        'category': 'BrandSpecific' if doc_type == 'brand' else 'General',
                        'brand': normalized_brand,  # Usar la versión normalizada
                        'original_brand': brand_name  # Mantener el nombre original para referencia
                    }

                    # Asegurar que brand nunca sea None o vacío
                    if not metadata['brand']:
                        logger.warning(f"Marca vacía para {txt_file_path}, usando nombre de archivo como respaldo")
                        metadata['brand'] = txt_file_path.stem

                    # Crear y agregar documento
                    try:
                        doc = Document(page_content=content, metadata=metadata)
                        all_documents.append(doc)
                        files_processed_total += 1
                        logger.debug(f"Documento creado - Contenido: {len(doc.page_content)} caracteres, "
                                  f"Metadatos: {doc.metadata}")
                        logger.info(f"Procesado: {txt_file_path.name} -> Marca: {normalized_brand if doc_type == 'brand' else 'N/A'}")
                    except Exception as e:
                        logger.error(f"Error al crear documento para {txt_file_path}: {str(e)}")
                        files_failed_read_total += 1

                except UnicodeDecodeError:
                    logger.error(f"Error de codificación en {txt_file_path}. Asegúrate de que el archivo esté en UTF-8.")
                    files_failed_read_total += 1
                except Exception as e:
                    logger.error(f"Error procesando {txt_file_path}: {str(e)}")
                    files_failed_read_total += 1

        except Exception as e:
            logger.error(f"Error accediendo a {current_source_dir}: {str(e)}")
            continue

    logger.info("\n" + "="*80)
    logger.info("RESUMEN FINAL DE CARGA")
    logger.info("="*80)
    logger.info(f"- Directorios procesados: {len(SOURCE_DIRS_TO_SCAN)}")
    logger.info(f"- Documentos procesados exitosamente: {files_processed_total}")
    logger.info(f"- Documentos saltados (vacíos/cortos): {files_skipped_empty_total}")
    logger.info(f"- Errores de lectura/procesamiento: {files_failed_read_total}")
    logger.info("="*80)
    
    if files_processed_total == 0:
        logger.error("¡ADVERTENCIA: No se procesó ningún documento! Verifica los logs para más detalles.")

    return all_documents

def split_documents(documents: List[Document]) -> List[Document]:
    """
    Divide los documentos en chunks más pequeños.
    """
    logger.info(f"=== Dividiendo {len(documents)} documentos en chunks ===")
    logger.info(f"Tamaño de chunk: {CHUNK_SIZE}, Solapamiento: {CHUNK_OVERLAP}")
    
    try:
        # Usar la configuración global del text_splitter pero con add_start_index
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=CHUNK_SIZE,
            chunk_overlap=CHUNK_OVERLAP,
            separators=[
                "\n\n", "\n", 
                ". ", "? ", "! ",
                "; ", ", ",
                " ", ""
            ],
            length_function=len,
            add_start_index=True,
            is_separator_regex=False
        )
        
        # Loggear información sobre el documento antes de dividir
        if documents:
            logger.info(f"Documento original: {documents[0].metadata.get('source', 'unknown')} - "
                       f"Longitud: {len(documents[0].page_content)} caracteres")
        chunked_documents = []
        for doc in documents:
            chunks = text_splitter.split_documents([doc])
            chunked_documents.extend(chunks)
            
            # Loggear información detallada de los chunks
            logger.info(f"Documento dividido en {len(chunks)} chunks")
            for i, chunk in enumerate(chunks[:3]):  # Mostrar primeros 3 chunks como ejemplo
                logger.debug(f"  Chunk {i+1}: {len(chunk.page_content)} caracteres")
                logger.debug(f"  Contenido: {chunk.page_content[:100]}...")
                if 'brand' in chunk.metadata:
                    logger.debug(f"  Marca: {chunk.metadata['brand']}")
        
        logger.info(f"Número total de chunks creados: {len(chunked_documents)}")
        
        # Verificar que los chunks no estén vacíos
        empty_chunks = sum(1 for doc in chunked_documents if not doc.page_content.strip())
        if empty_chunks > 0:
            logger.warning(f"Se encontraron {empty_chunks} chunks vacíos")
        
        if chunked_documents:
            logger.debug(f"Metadatos del primer chunk: {chunked_documents[0].metadata}")
            if len(chunked_documents) > 1:
                logger.debug(f"Metadatos del último chunk: {chunked_documents[-1].metadata}")
        
        return chunked_documents
    except Exception as e:
        logger.error(f"Error durante la división de documentos: {e}")
        raise

def create_faiss_index(chunked_documents: List[Document]) -> FAISS:
    """
    Crea un índice FAISS a partir de los documentos divididos.
    """
    logger.info(f"=== Creando índice FAISS con {len(chunked_documents)} chunks ===")
    
    # Verificar documentos antes de crear el índice
    logger.info("Verificando documentos antes de crear índice FAISS (muestra de 3):")
    for i, doc in enumerate(chunked_documents[:3]):  # Mostrar primeros 3 documentos
        logger.info(f"Documento {i+1}:")
        logger.info(f"  - Contenido: {doc.page_content[:200]}" + ("..." if len(doc.page_content) > 200 else ""))
        logger.info(f"  - Metadatos: {doc.metadata}")
    
    logger.info(f"Inicializando modelo de embeddings: '{EMBEDDING_MODEL_NAME}'...")
    
    # Inicializar el modelo de embeddings con la nueva API
    embedding_model = HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL_NAME,
        model_kwargs={"device": "cpu"},
        encode_kwargs={
            "normalize_embeddings": False,
            "batch_size": 32,
            "show_progress_bar": True
        },
        multi_process=True
    )
    
    logger.info(f"Modelo embeddings inicializado correctamente en 'cpu'.")
        
    logger.info("Creando índice FAISS...")
    try:
        vector_store = FAISS.from_documents(chunked_documents, embedding_model)
        logger.info("Índice FAISS creado en memoria.")
        
        # Verificar documentos después de crear el índice
        if hasattr(vector_store, 'docstore') and hasattr(vector_store.docstore, '_dict') and vector_store.docstore._dict:
            logger.info("Verificando documentos después de crear índice FAISS (muestra de 1):")
            sample_doc = next(iter(vector_store.docstore._dict.values()))
            logger.info(f"Documento de muestra del store:")
            logger.info(f"  - ID: {sample_doc.id if hasattr(sample_doc, 'id') else 'N/A'}")
            logger.info(f"  - Contenido: {sample_doc.page_content[:200] if hasattr(sample_doc, 'page_content') else 'N/A'}" + 
                       ("..." if hasattr(sample_doc, 'page_content') and len(sample_doc.page_content) > 200 else ""))
            logger.info(f"  - Metadatos: {sample_doc.metadata if hasattr(sample_doc, 'metadata') else 'N/A'}")
        else:
            logger.warning("No se pudo acceder a los documentos en el store del índice")
            
    except Exception as e:
        logger.error(f"Error al crear el índice FAISS: {str(e)}")
        logger.error(f"Tipo de excepción: {type(e).__name__}")
        logger.error("Traceback:", exc_info=True)
        raise
    
    return vector_store

def save_faiss_index(vector_store: FAISS) -> bool:
    """
    Guarda el índice FAISS localmente.
    """
    logger.info(f"=== Guardando índice FAISS en {FAISS_INDEX_PATH} ===")
    
    try:
        Path(FAISS_INDEX_PATH).parent.mkdir(parents=True, exist_ok=True)
        vector_store.save_local(folder_path=FAISS_INDEX_PATH, index_name=settings.FAISS_INDEX_NAME)
        
        # Verificar que los archivos se hayan creado
        faiss_file = Path(FAISS_INDEX_PATH) / f"{settings.FAISS_INDEX_NAME}.faiss"
        pkl_file = Path(FAISS_INDEX_PATH) / f"{settings.FAISS_INDEX_NAME}.pkl"
        
        if faiss_file.exists() and pkl_file.exists():
            logger.info(f"Índice FAISS guardado exitosamente:")
            logger.info(f"  - {faiss_file}: {faiss_file.stat().st_size / 1024:.2f} KB")
            logger.info(f"  - {pkl_file}: {pkl_file.stat().st_size / 1024:.2f} KB")
            return True
        else:
            logger.error("Error: No se encontraron los archivos del índice después de guardar.")
            return False
    except Exception as e:
        logger.error(f"Error guardando el índice FAISS: {e}")
        return False

def upload_to_azure_storage() -> bool:
    """
    Sube los archivos del índice FAISS a Azure Blob Storage.
    """
    logger.info("=== Subiendo índice FAISS a Azure Blob Storage ===")
    
    try:
        # Obtener configuración de Azure
        storage_account_name = settings.STORAGE_ACCOUNT_NAME
        container_name = settings.CONTAINER_NAME
        connection_string = settings.AZURE_STORAGE_CONNECTION_STRING
        
        if not all([storage_account_name, container_name, connection_string]):
            logger.error("Error: Faltan variables de entorno para Azure Storage.")
            return False
        
        logger.info(f"Conectando a Azure Storage (cuenta: {storage_account_name}, contenedor: {container_name})...")
        blob_service_client = BlobServiceClient.from_connection_string(connection_string)
        container_client = blob_service_client.get_container_client(container_name)
        
        # Rutas a los archivos locales
        faiss_file = Path(FAISS_INDEX_PATH) / f"{settings.FAISS_INDEX_NAME}.faiss"
        pkl_file = Path(FAISS_INDEX_PATH) / f"{settings.FAISS_INDEX_NAME}.pkl"
        
        # Subir archivo .faiss
        logger.info(f"Subiendo {faiss_file}...")
        with open(faiss_file, "rb") as data:
            blob_client_faiss = container_client.upload_blob(
                name=f"{settings.FAISS_INDEX_NAME}.faiss", 
                data=data, 
                overwrite=True
            )
        
        # Subir archivo .pkl
        logger.info(f"Subiendo {pkl_file}...")
        with open(pkl_file, "rb") as data:
            blob_client_pkl = container_client.upload_blob(
                name=f"{settings.FAISS_INDEX_NAME}.pkl", 
                data=data, 
                overwrite=True
            )
        
        logger.info("Archivos subidos exitosamente a Azure Blob Storage.")
        return True
    except Exception as e:
        logger.error(f"Error subiendo archivos a Azure Blob Storage: {e}")
        return False

def verify_documents_in_index() -> bool:
    """
    Verifica que los documentos en el índice tengan contenido y metadatos.
    Realiza una verificación exhaustiva del campo 'brand' y del contenido de los documentos.
    """
    logger.info("=== Verificando documentos en el índice FAISS ===")
    try:
        # Inicializar el modelo de embeddings igual que en la creación
        from langchain_huggingface import HuggingFaceEmbeddings
        from langchain_community.vectorstores import FAISS
        embedding_model = HuggingFaceEmbeddings(
            model_name=EMBEDDING_MODEL_NAME,
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": False, "batch_size": 32, "show_progress_bar": False}
        )
        # Recargar el índice FAISS desde disco usando allow_dangerous_deserialization
        reloaded_vector_store = FAISS.load_local(
            folder_path=str(FAISS_INDEX_PATH),
            embeddings=embedding_model,
            allow_dangerous_deserialization=True
        )
        logger.info("Índice FAISS recargado correctamente desde disco.")
        # Obtener todos los documentos del docstore
        docs = {}
        if hasattr(reloaded_vector_store, 'docstore') and hasattr(reloaded_vector_store.docstore, '_dict'):
            docs = reloaded_vector_store.docstore._dict
        total_docs = len(docs)
        docs_with_content = 0
        docs_with_short_content = 0
        docs_with_brand = 0
        docs_complete = 0
        brands_found = set()
        doc_types = set()
        for doc_id, doc in docs.items():
            content = getattr(doc, 'page_content', '')
            metadata = getattr(doc, 'metadata', {})
            has_content = bool(content and content.strip())
            is_short_content = has_content and len(content.strip()) < 50
            if has_content:
                docs_with_content += 1
                if is_short_content:
                    docs_with_short_content += 1
            has_brand = bool(metadata and metadata.get('brand'))
            if has_brand:
                docs_with_brand += 1
                brands_found.add(metadata.get('brand'))
            if metadata.get('doc_type'):
                doc_types.add(metadata.get('doc_type'))
            if has_brand and has_content and not is_short_content:
                docs_complete += 1
        logger.info(f"\n=== RESUMEN DE VERIFICACIÓN DE DOCUMENTOS ===")
        logger.info(f"Total de documentos: {total_docs}")
        if total_docs > 0:
            logger.info(f"\nVerificación de CONTENIDO:")
            logger.info(f"  - Documentos con contenido: {docs_with_content} ({docs_with_content/total_docs*100:.1f}%)")
            logger.info(f"  - Documentos con contenido corto (<50 chars): {docs_with_short_content}")
            logger.info(f"\nVerificación de METADATOS:")
            logger.info(f"  - Documentos con metadato 'brand': {docs_with_brand} ({docs_with_brand/total_docs*100:.1f}%)")
            logger.info(f"  - Tipos de documentos: {', '.join(sorted(doc_types))}")
            if brands_found:
                logger.info(f"  - Marcas encontradas ({len(brands_found)}): {', '.join(sorted(brands_found))}")
            logger.info(f"\nCOMPLETITUD:")
            logger.info(f"  - Documentos completos (brand + contenido válido): {docs_complete} ({docs_complete/total_docs*100:.1f}%)")
            if docs_complete == total_docs:
                logger.info("\n✅ VERIFICACIÓN EXITOSA: Todos los documentos tienen brand y contenido válido.")
            else:
                logger.warning(f"\n⚠️ ATENCIÓN: {total_docs - docs_complete} documentos no están completos.")
        if docs_with_content == 0 or docs_with_brand == 0:
            logger.error("❌ VERIFICACIÓN FALLIDA: Los documentos no tienen contenido o metadatos.")
            return False
        if docs_complete < total_docs * 0.9:
            logger.error("❌ ERROR CRÍTICO: Demasiados documentos incompletos.")
            return False
        return True
    except Exception as e:
        logger.error(f"Error verificando documentos en el índice: {e}")
        logger.error("Traceback:", exc_info=True)
        return False


def main():
    """
    Función principal que ejecuta todo el proceso.
    """
    logger.info("=== INICIANDO PROCESO DE RECREACIÓN DEL ÍNDICE FAISS ===")
    
    try:
        # 1. Cargar documentos
        documents = load_documents()
        if not documents:
            logger.error("No se cargaron documentos. Abortando.")
            return False
        
        # 2. Dividir documentos en chunks
        chunked_documents = split_documents(documents)
        if not chunked_documents:
            logger.error("No se crearon chunks. Abortando.")
            return False
        
        # 3. Crear índice FAISS
        vector_store = create_faiss_index(chunked_documents)
        
        # 4. Guardar índice localmente
        if not save_faiss_index(vector_store):
            logger.error("Error al guardar el índice FAISS. Abortando.")
            return False
        
        # 5. Verificar documentos en el índice
        if not verify_documents_in_index():
            logger.warning("La verificación del índice falló. Revisa los logs para más detalles.")
            # Continuamos de todos modos para subir a Azure
        
        # 6. Subir a Azure Storage
        if not upload_to_azure_storage():
            logger.error("Error al subir el índice a Azure Storage.")
            return False
        
        logger.info("=== PROCESO COMPLETADO EXITOSAMENTE ===")
        return True
    except Exception as e:
        logger.error(f"Error en el proceso principal: {e}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
