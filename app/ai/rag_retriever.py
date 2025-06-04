# app/ai/rag_retriever.py
import os
import logging
from pathlib import Path 
from typing import List, Optional, Any
import asyncio

# --- Importaciones de Terceros (Langchain, Azure) ---
# Intentar importar Langchain y FAISS. Si falla, RAG no funcionará.
try:
    from langchain_community.embeddings import HuggingFaceEmbeddings
    from langchain_community.vectorstores import FAISS
    from langchain_core.documents import Document as LangchainDocument
    from langchain_core.vectorstores import VectorStoreRetriever
    LANGCHAIN_OK = True # Variable global para indicar si Langchain está disponible
    # print("DEBUG [rag_retriever.py]: Langchain components imported successfully.") # Para depuración muy temprana
except ImportError as e_langchain:
    # Configurar un logger de emergencia si el logger principal aún no está disponible
    _emergency_logger_rag = logging.getLogger("rag_retriever_langchain_import_error")
    if not _emergency_logger_rag.hasHandlers():
        _h_emerg = logging.StreamHandler(sys.stderr) # type: ignore
        _f_emerg = logging.Formatter('%(asctime)s - %(name)s - CRITICAL - %(message)s')
        _h_emerg.setFormatter(_f_emerg); _emergency_logger_rag.addHandler(_h_emerg)
    _emergency_logger_rag.critical(
        f"Faltan librerías CRÍTICAS de Langchain/FAISS (Error: {e_langchain}). "
        "El sistema RAG NO funcionará. Por favor, instala los paquetes requeridos: "
        "'pip install langchain langchain-community faiss-cpu sentence-transformers'"
    )
    LANGCHAIN_OK = False # Variable global
    
    # Clases Dummy para evitar NameError si LANGCHAIN_OK es False y el código intenta usarlas
    # Esto permite que el resto del módulo se importe sin errores fatales inmediatos,
    # aunque las funciones RAG no serán operativas.
    class HuggingFaceEmbeddings: pass # type: ignore
    class FAISS: pass # type: ignore
    class LangchainDocument: # type: ignore
        def __init__(self, page_content: str, metadata: Optional[Dict[str, Any]] = None):
            self.page_content = page_content
            self.metadata = metadata or {}
    class VectorStoreRetriever: pass # type: ignore

# Azure SDKs (solo si se usan para descarga, y dentro de try-except)
try:
    from azure.storage.blob import BlobServiceClient
    from azure.identity import DefaultAzureCredential
    AZURE_SDK_OK = True
except ImportError:
    # No es crítico si no se usa la descarga desde Azure o si los archivos ya están locales
    # El logger principal (si está disponible) advertirá si se intenta la descarga sin SDK.
    AZURE_SDK_OK = False


# --- Importar settings y logger de la aplicación ---
# Esto asume que config.py y logger.py están en paths accesibles y se cargan antes o sin problemas.
try:
    from app.core.config import settings # Importa la instancia 'settings' ya inicializada
    from app.utils.logger import logger # Importa el logger principal de la app
    CONFIG_AND_LOGGER_OK_RAG = True
    logger.info("rag_retriever.py: Configuración (settings) y logger principal cargados.")
except ImportError as e_cfg_log_rag:
    # Fallback logger si el principal no está disponible
    logger = logging.getLogger("app.ai.rag_retriever_fallback")
    if not logger.hasHandlers():
        _h_fall = logging.StreamHandler(sys.stderr) # type: ignore
        _f_fall = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s')
        _h_fall.setFormatter(_f_fall); logger.addHandler(_h_fall); logger.setLevel(logging.INFO)
    logger.error(f"Error CRÍTICO importando 'settings' o 'logger' principal en rag_retriever.py: {e_cfg_log_rag}. Usando fallback logger. La funcionalidad RAG puede estar comprometida.")
    settings = None # type: ignore # Para evitar NameError si settings no se cargó
    CONFIG_AND_LOGGER_OK_RAG = False


def _download_faiss_files_from_azure(
    local_index_target_folder: Path, 
    faiss_index_filename_base: str, # Ej: "index" para "index.faiss", "index.pkl"
    storage_account_name_cfg: Optional[str], 
    container_name_cfg: Optional[str],
    connection_string_cfg: Optional[str] = None
) -> bool:
    """Descarga los archivos .faiss y .pkl del índice desde Azure Blob Storage."""
    
    logger.info(f"RAG_AZURE_DOWNLOAD: Intentando descarga de índice '{faiss_index_filename_base}' desde Azure Blob.")

    if not AZURE_SDK_OK:
        logger.error("RAG_AZURE_DOWNLOAD: Azure SDK (azure.storage.blob, azure.identity) no disponible. No se puede descargar de Azure.")
        return False
    if not storage_account_name_cfg or not container_name_cfg:
        logger.error("RAG_AZURE_DOWNLOAD: Nombre de cuenta de almacenamiento o nombre de contenedor no provistos en settings. Abortando descarga.")
        return False

    faiss_blob_name = f"{faiss_index_filename_base}.faiss"
    pkl_blob_name = f"{faiss_index_filename_base}.pkl"
    
    local_faiss_file_path = local_index_target_folder / faiss_blob_name
    local_pkl_file_path = local_index_target_folder / pkl_blob_name

    logger.debug(f"  Target local: '{local_index_target_folder}', FAISS file: '{faiss_blob_name}', PKL file: '{pkl_blob_name}'")

    try:
        blob_service_client: BlobServiceClient
        if connection_string_cfg:
            logger.info(f"  Autenticando en Azure Blob con CADENA DE CONEXIÓN para cuenta '{storage_account_name_cfg}'.")
            blob_service_client = BlobServiceClient.from_connection_string(connection_string_cfg)
        else:
            logger.info(f"  Autenticando en Azure Blob con DefaultAzureCredential para cuenta '{storage_account_name_cfg}'.")
            account_url = f"https://{storage_account_name_cfg}.blob.core.windows.net"
            credential = DefaultAzureCredential(logging_enable=True) # Habilitar logging de Azure Identity
            blob_service_client = BlobServiceClient(account_url=account_url, credential=credential)

        container_client = blob_service_client.get_container_client(container_name_cfg)
        logger.info(f"  Accediendo al contenedor de Azure: '{container_name_cfg}'.")
        
        local_index_target_folder.mkdir(parents=True, exist_ok=True)
        logger.debug(f"  Directorio local para el índice asegurado: '{local_index_target_folder}'.")

        # Descargar .faiss
        logger.info(f"    Descargando blob '{faiss_blob_name}' a '{local_faiss_file_path}'...")
        blob_client_faiss = container_client.get_blob_client(faiss_blob_name)
        with open(local_faiss_file_path, "wb") as download_file_faiss:
            download_stream_faiss = blob_client_faiss.download_blob(timeout=300) # Timeout 5 min
            download_file_faiss.write(download_stream_faiss.readall())
        logger.info(f"    '{faiss_blob_name}' descargado ({local_faiss_file_path.stat().st_size} bytes).")

        # Descargar .pkl
        logger.info(f"    Descargando blob '{pkl_blob_name}' a '{local_pkl_file_path}'...")
        blob_client_pkl = container_client.get_blob_client(pkl_blob_name)
        with open(local_pkl_file_path, "wb") as download_file_pkl:
            download_stream_pkl = blob_client_pkl.download_blob(timeout=300) # Timeout 5 min
            download_file_pkl.write(download_stream_pkl.readall())
        logger.info(f"    '{pkl_blob_name}' descargado ({local_pkl_file_path.stat().st_size} bytes).")
        
        logger.info(f"RAG_AZURE_DOWNLOAD: Descarga de índice '{faiss_index_filename_base}' desde Azure completada exitosamente.")
        return True

    except Exception as e_download:
        logger.error(f"RAG_AZURE_DOWNLOAD: Error al descargar archivos FAISS desde Azure. Cuenta: '{storage_account_name_cfg}', Contenedor: '{container_name_cfg}', Índice base: '{faiss_index_filename_base}'. Error: {e_download}", exc_info=True)
        if local_faiss_file_path.exists(): local_faiss_file_path.unlink(missing_ok=True)
        if local_pkl_file_path.exists(): local_pkl_file_path.unlink(missing_ok=True)
        return False

# --- ESTA ES LA FUNCIÓN QUE SE IMPORTA EN app/__init__.py ---
def load_rag_components() -> Optional[VectorStoreRetriever]:
    """
    Carga los componentes RAG: modelo de embeddings y el índice vectorial FAISS.
    Intenta cargar desde una ruta local; si no existe, intenta descargar desde Azure Blob Storage.
    Esta función es SÍNCRONA y está pensada para ser llamada en un hilo separado si es necesario
    durante el arranque de la aplicación (ej. con asyncio.to_thread).
    """
    logger.info("RAG_LOADER: Iniciando carga de componentes RAG...")

    if not LANGCHAIN_OK:
        logger.critical("RAG_LOADER: Langchain/FAISS no disponibles (LANGCHAIN_OK=False). No se pueden cargar componentes RAG.")
        return None
    if not CONFIG_AND_LOGGER_OK_RAG or not settings:
        logger.critical("RAG_LOADER: Configuración (settings) o logger principal no disponibles. No se pueden cargar componentes RAG.")
        return None

    # Validar configuraciones necesarias de 'settings'
    embedding_model = getattr(settings, 'EMBEDDING_MODEL_NAME', None)
    faiss_index_name_base = getattr(settings, 'FAISS_INDEX_NAME', None) # ej: "index"
    # FAISS_FOLDER_PATH es calculado en config.py: settings.DATA_DIR / settings.FAISS_FOLDER_NAME
    # ej: /app_root/data/faiss_index_kb_spanish_v1
    faiss_folder_full_path = getattr(settings, 'FAISS_FOLDER_PATH', None) 

    # LOCAL_FAISS_CACHE_PATH es una ruta opcional para sobreescribir dónde buscar/guardar el índice localmente.
    # Si se define, esta es la carpeta que contiene los archivos index.faiss y index.pkl.
    # Si no, se usa faiss_folder_full_path.
    local_index_dir_to_use: Optional[Path] = None
    if getattr(settings, 'LOCAL_FAISS_CACHE_PATH', None) and isinstance(settings.LOCAL_FAISS_CACHE_PATH, Path):
        local_index_dir_to_use = settings.LOCAL_FAISS_CACHE_PATH
        logger.info(f"  Usando LOCAL_FAISS_CACHE_PATH para el índice: '{local_index_dir_to_use}'")
    elif faiss_folder_full_path and isinstance(faiss_folder_full_path, Path):
        local_index_dir_to_use = faiss_folder_full_path
        logger.info(f"  LOCAL_FAISS_CACHE_PATH no definido, usando FAISS_FOLDER_PATH para el índice: '{local_index_dir_to_use}'")
    else:
        logger.critical("  Ruta del índice FAISS (FAISS_FOLDER_PATH o LOCAL_FAISS_CACHE_PATH) no configurada o inválida.")
        return None

    if not embedding_model:
        logger.critical("  EMBEDDING_MODEL_NAME no configurado en settings.")
        return None
    if not faiss_index_name_base:
        logger.critical(f"  FAISS_INDEX_NAME (nombre base de los archivos .faiss/.pkl) no configurado.")
        return None
    
    logger.info(f"  Directorio local objetivo para el índice '{faiss_index_name_base}': '{local_index_dir_to_use}'")
    logger.info(f"  Modelo de embeddings a usar: '{embedding_model}'")

    index_file_path = local_index_dir_to_use / f"{faiss_index_name_base}.faiss"
    pkl_file_path = local_index_dir_to_use / f"{faiss_index_name_base}.pkl"
    
    # 1. Verificar si los archivos existen localmente o descargar desde Azure
    if not (index_file_path.exists() and pkl_file_path.exists()):
        logger.info(f"  Índice FAISS ('{index_file_path.name}', '{pkl_file_path.name}') no encontrado localmente en '{local_index_dir_to_use}'.")
        logger.info(f"  Intentando descarga desde Azure Blob Storage...")
        
        azure_storage_name = getattr(settings, 'STORAGE_ACCOUNT_NAME', None)
        azure_container = getattr(settings, 'CONTAINER_NAME', None)
        azure_conn_str = getattr(settings, 'AZURE_STORAGE_CONNECTION_STRING', None)

        download_successful = _download_faiss_files_from_azure(
            local_index_target_folder=local_index_dir_to_use, # Carpeta donde se guardarán
            faiss_index_filename_base=faiss_index_name_base, # Nombre base, ej "index"
            storage_account_name_cfg=azure_storage_name,
            container_name_cfg=azure_container,
            connection_string_cfg=azure_conn_str
        )
        if not download_successful:
            logger.error("  Fallo al descargar el índice FAISS desde Azure. RAG no estará disponible.")
            return None
    else:
        logger.info(f"  Índice FAISS encontrado localmente en '{local_index_dir_to_use}'. Saltando descarga.")

    # 2. Cargar embeddings y el índice FAISS desde la ruta local
    try:
        logger.info(f"  Cargando modelo de embeddings: '{embedding_model}'...")
        # Podrías añadir un cache_folder para los embeddings si es necesario y no está configurado globalmente por transformers
        # embeddings_cache_dir = settings.BASE_DIR / ".cache" / "embeddings_hf"
        # embeddings_cache_dir.mkdir(parents=True, exist_ok=True)
        embedding_model_instance = HuggingFaceEmbeddings(
            model_name=embedding_model,
            model_kwargs={'device': 'cpu'}, # Forzar CPU para consistencia
            # cache_folder=str(embeddings_cache_dir) # Opcional
        )
        logger.info("  Modelo de embeddings cargado exitosamente.")

        logger.info(f"  Cargando índice FAISS desde '{local_index_dir_to_use}' (nombre base del índice: '{faiss_index_name_base}')...")
        vector_store_instance = FAISS.load_local(
            folder_path=str(local_index_dir_to_use), # Debe ser string
            embeddings=embedding_model_instance,
            index_name=faiss_index_name_base, # Importante: nombre base de los archivos .faiss y .pkl
            allow_dangerous_deserialization=True # Necesario para índices creados con algunas versiones de Langchain/FAISS
        )
        logger.info(f"  Índice FAISS '{faiss_index_name_base}' cargado exitosamente desde '{local_index_dir_to_use}'.")
        
        if hasattr(vector_store_instance, 'index') and vector_store_instance.index:
             logger.info(f"    Verificación: Número total de vectores en el índice FAISS cargado: {vector_store_instance.index.ntotal}")
        else:
            logger.warning("    Advertencia: El índice FAISS se cargó, pero el objeto 'index' interno no está disponible o es None.")

        # 3. Crear y Devolver el Retriever
        rag_k_default = getattr(settings, 'RAG_DEFAULT_K', 3)
        rag_k_mult = getattr(settings, 'RAG_K_FETCH_MULTIPLIER', 4)  # Aumentado de 2 a 4 para obtener más documentos
        k_for_retriever_search = rag_k_default * rag_k_mult
        
        logger.info(f"  Creando retriever FAISS. Tipo de búsqueda: 'similarity', k para search_kwargs: {k_for_retriever_search}.")
        retriever_instance = vector_store_instance.as_retriever(
            search_type="similarity", 
            search_kwargs={'k': k_for_retriever_search}
        )
        logger.info("  Retriever FAISS creado exitosamente.")
        logger.info("RAG_LOADER: ¡Componentes RAG (embeddings, vector store, retriever) cargados y listos!")
        return retriever_instance
        
    except Exception as e_load_local:
        logger.error(f"RAG_LOADER: Error CRÍTICO durante la carga local de embeddings o el índice FAISS desde '{local_index_dir_to_use}': {e_load_local}", exc_info=True)
        return None

async def search_relevant_documents(
    retriever_instance: VectorStoreRetriever, # Este es el objeto devuelto por load_rag_components
    user_query: str,
    target_brand: Optional[str] = None, # Nombre normalizado de la marca para filtrar
    k_final: Optional[int] = None       # Número final de documentos a devolver
) -> List[LangchainDocument]:
    """
    Busca documentos relevantes usando el retriever y opcionalmente filtra por marca.
    """
    logger.debug(f"RAG_SEARCH: Iniciando búsqueda. Query (preview): '{user_query[:70]}...', Marca Obj: '{target_brand}', K Final: {k_final}")

    if not LANGCHAIN_OK or retriever_instance is None:
        logger.error("RAG_SEARCH: Langchain no disponible o retriever_instance es None. Devolviendo lista vacía.")
        return []
    if not CONFIG_AND_LOGGER_OK_RAG or not settings: # Doble chequeo por si settings no está
        logger.error("RAG_SEARCH: Settings no disponible. Usando k por defecto. Funcionalidad RAG limitada.")
        _k_final_to_use = k_final if k_final is not None and k_final > 0 else 3 # Fallback K
    else:
        _k_final_to_use = k_final if k_final is not None and k_final > 0 else getattr(settings, 'RAG_DEFAULT_K', 3)
    
    logger.debug(f"  K final a usar para selección de documentos: {_k_final_to_use}")
    
    relevant_docs_final: List[LangchainDocument] = []
    try:
        # El retriever ya tiene configurado su 'k' para la búsqueda inicial (k_for_retriever_search)
        # get_relevant_documents usará ese 'k'
        retriever_k_cfg_val = "N/A"
        if hasattr(retriever_instance, 'search_kwargs') and isinstance(retriever_instance.search_kwargs, dict):
            retriever_k_cfg_val = retriever_instance.search_kwargs.get('k', "No definido en search_kwargs")

        logger.debug(f"  Ejecutando retriever.get_relevant_documents (k del retriever: {retriever_k_cfg_val}) para query...")
        
        # La llamada a get_relevant_documents de Langchain es síncrona, por eso se usa to_thread
        initial_docs_found: List[LangchainDocument] = await asyncio.to_thread(
            retriever_instance.get_relevant_documents, 
            user_query # El 'query' es el único argumento necesario aquí
        )
        num_initial_docs = len(initial_docs_found)
        logger.info(f"  Retriever devolvió {num_initial_docs} documentos iniciales.")

        if not initial_docs_found:
            logger.info("  La búsqueda inicial del retriever no devolvió ningún documento.")
            return []

        # Filtrar y seleccionar los documentos finales
        if target_brand: # target_brand debe ser el nombre normalizado
            logger.info(f"  Filtrando {num_initial_docs} resultados por metadato 'brand' == '{target_brand}'...")
            filtered_by_brand_docs = []
            seen_content_in_brand_filter = set()
            
            for i, doc in enumerate(initial_docs_found):
                # Asumimos que la metadata 'brand' contiene el nombre normalizado de la marca
                doc_brand_meta = doc.metadata.get('brand') 
                # logger.debug(f"    Doc {i} - Brand en metadata: '{doc_brand_meta}', Content preview: '{doc.page_content[:50]}...'")
                if doc_brand_meta == target_brand:
                    if doc.page_content not in seen_content_in_brand_filter: # Evitar duplicados de contenido exacto
                        filtered_by_brand_docs.append(doc)
                        seen_content_in_brand_filter.add(doc.page_content)
                    # else: logger.debug(f"      Doc {i} OMITIDO (contenido duplicado) para marca '{target_brand}'.")
                
                if len(filtered_by_brand_docs) >= _k_final_to_use: # Si ya tenemos suficientes para esta marca
                    logger.debug(f"    Alcanzado límite de k_final ({_k_final_to_use}) para marca '{target_brand}'.")
                    break
            relevant_docs_final = filtered_by_brand_docs
            logger.info(f"  Filtrado por marca completado. {len(relevant_docs_final)} docs para '{target_brand}' (objetivo k={_k_final_to_use}).")
            if not relevant_docs_final and num_initial_docs > 0:
                logger.warning(f"  ADVERTENCIA RAG: No se encontraron docs para marca '{target_brand}' tras filtrar {num_initial_docs} iniciales. "
                               "Verifica que la metadata 'brand' en tus documentos coincida y que el retriever inicial traiga suficientes resultados.")
        
        else: # Sin filtro de marca, tomar los k_final mejores resultados únicos de los iniciales
            logger.info(f"  Búsqueda RAG global (sin filtro de marca). Tomando hasta k={_k_final_to_use} resultados únicos de {num_initial_docs} iniciales.")
            unique_global_docs = []
            seen_content_globally = set()
            for i, doc in enumerate(initial_docs_found):
                if doc.page_content not in seen_content_globally:
                    unique_global_docs.append(doc)
                    seen_content_globally.add(doc.page_content)
                if len(unique_global_docs) >= _k_final_to_use: break
            relevant_docs_final = unique_global_docs
            logger.info(f"  Selección global completada. {len(relevant_docs_final)} documentos únicos seleccionados.")

    except AttributeError as ae_search: 
        logger.error(f"RAG_SEARCH: AttributeError durante búsqueda (¿retriever mal configurado o settings es None?): {ae_search}", exc_info=True)
        relevant_docs_final = []
    except Exception as e_search_unexp:
        logger.error(f"RAG_SEARCH: Error inesperado durante la búsqueda: {e_search_unexp}", exc_info=True)
        relevant_docs_final = []

    logger.info(f"RAG_SEARCH: Búsqueda finalizada. Devolviendo {len(relevant_docs_final)} documentos.")
    # if relevant_docs_final: # Loguear los documentos finales si es necesario para depuración
    #     for i, doc_f in enumerate(relevant_docs_final):
    #          logger.debug(f"    Doc Final {i}: Metadata={doc_f.metadata}, Preview='{doc_f.page_content[:100]}...'")
    return relevant_docs_final