import os
import logging
from pathlib import Path # Asegurar importación de Path
from typing import List, Optional, Any
import asyncio

# Langchain y FAISS imports
try:
    from langchain_community.embeddings import HuggingFaceEmbeddings
    from langchain_community.vectorstores import FAISS
    from langchain.schema import Document as LangchainDocument
    from langchain_core.vectorstores import VectorStoreRetriever
    LANGCHAIN_OK = True
except ImportError:
    logging.basicConfig(level=logging.ERROR) # Logger básico si todo lo demás falla
    logging.error("Faltan librerías CRÍTICAS de Langchain/FAISS (langchain-huggingface, langchain-community, faiss-cpu/gpu). El sistema RAG NO funcionará.")
    LANGCHAIN_OK = False
    # Clases Dummy para evitar errores de NameError si las importaciones fallan
    class HuggingFaceEmbeddings: pass
    class FAISS: pass
    class LangchainDocument: pass
    class VectorStoreRetriever: pass

# Importar settings y logger de la aplicación
CONFIG_LOADED = False
settings_instance = None # Renombrar para evitar conflicto con el 'settings' global de config.py
try:
    from app.core.config import settings as app_settings # Usar un alias para la instancia importada
    if app_settings:
        settings_instance = app_settings # Asignar al alias local
        CONFIG_LOADED = True
        # Logger de la aplicación ya debería estar configurado si settings se cargó
        logger = logging.getLogger("app.ai.rag_retriever") # Obtener el logger específico del módulo
        logger.info("Configuración (settings) y logger principal cargados exitosamente en rag_retriever.")
    else:
        logger = logging.getLogger("rag_retriever_init_error")
        logger.error("Instancia de 'settings' importada desde app.core.config es None.")

except ImportError as e:
    # Fallback si no se puede importar config o logger
    logger = logging.getLogger("rag_retriever_fallback")
    if not logger.hasHandlers():
        _h = logging.StreamHandler()
        _f = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s')
        _h.setFormatter(_f)
        logger.addHandler(_h)
        logger.setLevel(logging.INFO)
    logger.error(f"Error CRÍTICO importando 'settings' o 'logger' desde app.core/app.utils: {e}. Usando fallback logger.")
    settings_instance = None # Asegurar que es None


def load_rag_components() -> Optional[VectorStoreRetriever]:
    logger.info("Iniciando load_rag_components...")
    if not LANGCHAIN_OK:
        logger.critical("Langchain/FAISS no están disponibles (importación fallida). No se pueden cargar componentes RAG.")
        return None
    if not CONFIG_LOADED or not settings_instance:
        logger.critical("Configuración (settings_instance) no disponible o no cargada. No se pueden cargar componentes RAG.")
        return None

    # --- Obtener rutas y nombres desde settings_instance ---
    # settings_instance.faiss_folder_path ya es un objeto Path calculado en config.py
    faiss_folder_path_obj: Path = settings_instance.faiss_folder_path
    faiss_base_name: str = settings_instance.faiss_index_name # ej: "index"
    embedding_model_name_from_settings: str = settings_instance.embedding_model_name
    rag_k_default: int = settings_instance.rag_default_k
    k_fetch_multiplier: int = settings_instance.rag_k_fetch_multiplier
    k_to_fetch_initially = rag_k_default * k_fetch_multiplier

    logger.info(f"  Path a la carpeta del índice FAISS (desde settings): '{faiss_folder_path_obj}'")
    logger.info(f"  Nombre base del índice FAISS (desde settings): '{faiss_base_name}'")
    logger.info(f"  Modelo de embeddings (desde settings): '{embedding_model_name_from_settings}'")

    if not embedding_model_name_from_settings:
        logger.critical("  embedding_model_name no está configurado en settings.")
        return None
    if not faiss_folder_path_obj or not faiss_base_name:
        logger.critical(f"  Configuración de FAISS incompleta: faiss_folder_path='{faiss_folder_path_obj}', faiss_index_name='{faiss_base_name}'.")
        return None

    embedding_model_instance: Optional[HuggingFaceEmbeddings] = None
    vector_store_instance: Optional[FAISS] = None

    try:
        # 1. Cargar Modelo de Embeddings
        logger.info(f"  Paso 1: Cargando modelo de embeddings '{embedding_model_name_from_settings}'...")
        device_to_use = 'cpu' # Forzar CPU para consistencia en App Service
        embedding_model_instance = HuggingFaceEmbeddings(
            model_name=embedding_model_name_from_settings,
            model_kwargs={'device': device_to_use},
        )
        logger.info(f"  Modelo de embeddings '{embedding_model_name_from_settings}' inicializado en dispositivo '{device_to_use}'.")

        # 2. Verificar y Cargar Índice FAISS
        logger.info(f"  Paso 2: Verificando y cargando índice FAISS desde '{faiss_folder_path_obj}' con nombre base '{faiss_base_name}'...")
        
        if not faiss_folder_path_obj.is_dir():
            logger.critical(f"  ERROR: El directorio del índice FAISS NO EXISTE: {faiss_folder_path_obj}")
            return None
        
        expected_faiss_file = faiss_folder_path_obj / f"{faiss_base_name}.faiss"
        expected_pkl_file = faiss_folder_path_obj / f"{faiss_base_name}.pkl"

        if not expected_faiss_file.is_file():
            logger.critical(f"  ERROR: Archivo '{expected_faiss_file.name}' NO ENCONTRADO en: {faiss_folder_path_obj}")
            return None
        if not expected_pkl_file.is_file():
            logger.critical(f"  ERROR: Archivo '{expected_pkl_file.name}' NO ENCONTRADO en: {faiss_folder_path_obj}")
            return None
            
        logger.info(f"  Archivos de índice (.faiss y .pkl) encontrados. Procediendo a cargar con FAISS.load_local...")
        vector_store_instance = FAISS.load_local(
            folder_path=str(faiss_folder_path_obj), # IMPORTANTE: load_local espera un string para folder_path
            index_name=faiss_base_name, # Nombre base de los archivos (sin extensión)
            embeddings=embedding_model_instance,
            allow_dangerous_deserialization=True # Necesario si el .pkl fue guardado por Langchain
        )
        logger.info(f"  Índice FAISS '{faiss_base_name}' cargado exitosamente desde '{faiss_folder_path_obj}'.")
        
        if hasattr(vector_store_instance, 'index') and vector_store_instance.index:
             logger.info(f"  Número total de vectores en el índice cargado: {vector_store_instance.index.ntotal}")
        else:
            # Esto sería muy inusual si FAISS.load_local no lanzó error, pero por si acaso.
            logger.warning("  El índice FAISS se cargó, pero el objeto 'index' interno no está disponible o es None.")


        # 3. Crear y Devolver el Retriever
        logger.info(f"  Paso 3: Creando retriever FAISS...")
        retriever_instance = vector_store_instance.as_retriever(
            search_type="similarity", # Otras opciones: "mmr", "similarity_score_threshold"
            search_kwargs={'k': k_to_fetch_initially}
        )
        logger.info(f"  Retriever FAISS creado exitosamente. k (búsqueda inicial) = {k_to_fetch_initially}.")
        logger.info("Componentes RAG cargados exitosamente.")
        return retriever_instance

    except ImportError as e_imp: # Debería ser capturado por LANGCHAIN_OK, pero como doble check.
        logger.critical(f"Error de importación tardío (inesperado) al cargar componentes RAG: {e_imp}", exc_info=True)
        return None
    except FileNotFoundError as e_fnf: # Ahora menos probable con los checks explícitos de is_dir/is_file.
        logger.critical(f"No se encontró archivo/directorio FAISS (inesperado después de los checks de existencia): {e_fnf}", exc_info=True)
        return None
    except RuntimeError as e_rt: # Errores de FAISS al cargar, etc.
        if "could not open" in str(e_rt).lower() and ".faiss" in str(e_rt).lower():
            logger.critical(f"Error FAISS específico: No se pudo abrir el archivo '{faiss_base_name}.faiss' en '{faiss_folder_path_obj}'. ¿Corrupto o problema de permisos?", exc_info=False)
        else:
            logger.critical(f"RuntimeError inesperado al cargar componentes RAG: {e_rt}", exc_info=True)
        return None
    except Exception as e:
        logger.critical(f"Error CRÍTICO y GENERAL al cargar componentes RAG: {e}", exc_info=True)
        return None

# ... (El resto de tu función search_relevant_documents se mantiene igual, pero asegúrate de que usa settings_instance en lugar de settings global si es necesario)
# Por ejemplo, dentro de search_relevant_documents:
# final_k_to_return = k_final if k_final is not None else (settings_instance.rag_default_k if settings_instance else 3)

async def search_relevant_documents(
    retriever_instance: VectorStoreRetriever,
    user_query: str,
    target_brand: Optional[str] = None,
    k_final: Optional[int] = None
) -> List[LangchainDocument]:
    if not LANGCHAIN_OK or retriever_instance is None:
        logger.error("Intento de búsqueda RAG con retriever_instance=None o Langchain no disponible.")
        return []

    # Usar k_final de settings_instance si no se provee, o un default
    _k_final_to_use = final_k_to_return = k_final if k_final is not None else (settings_instance.rag_default_k if settings_instance else 3)
    _k_multiplier = settings_instance.rag_k_fetch_multiplier if settings_instance else 2
    
    # Asegurar que k en search_kwargs del retriever sea al menos k_final * multiplicador
    # Esto es más una guía, el retriever ya fue configurado con k_to_fetch_initially al crearse.
    # Si se necesita k dinámico, se podría reconfigurar search_kwargs aquí.
    # Por ahora, confiamos en la configuración inicial del retriever.
    # k_for_retriever = retriever_instance.search_kwargs.get('k', _k_final_to_use * _k_multiplier)


    relevant_docs_final: List[LangchainDocument] = []
    try:
        logger.debug(f"Ejecutando retriever.get_relevant_documents para query: '{user_query[:70]}...' (target_brand: {target_brand}, k_final: {_k_final_to_use})")

        initial_results: List[LangchainDocument] = await asyncio.to_thread(
            retriever_instance.get_relevant_documents, # Este es el método correcto
            query=user_query
        )
        num_initial_results = len(initial_results)
        logger.info(f"Retriever devolvió {num_initial_results} documentos iniciales (k configurado en retriever: {retriever_instance.search_kwargs.get('k')}).")


        if not initial_results:
            logger.info("La búsqueda inicial no devolvió documentos.")
            return []

        if target_brand:
            logger.info(f"Filtrando {num_initial_results} resultados por marca normalizada: '{target_brand}'...")
            filtered_docs_for_brand = []
            seen_content_for_brand = set() 
            
            for doc in initial_results:
                doc_brand_metadata = doc.metadata.get('brand') # Asumimos que 'brand' está en minúsculas y normalizado
                
                if doc_brand_metadata == target_brand: # Comparar con target_brand normalizado
                    if doc.page_content not in seen_content_for_brand:
                        filtered_docs_for_brand.append(doc)
                        seen_content_for_brand.add(doc.page_content)
                    else:
                        logger.debug(f"Chunk con contenido duplicado omitido para marca '{target_brand}'. Source: {doc.metadata.get('source')}")
                
                if len(filtered_docs_for_brand) >= _k_final_to_use:
                    break # Salir si ya tenemos suficientes para k_final
            
            relevant_docs_final = filtered_docs_for_brand
            logger.info(f"Filtrado por marca: {len(relevant_docs_final)} documentos para '{target_brand}' (objetivo k={_k_final_to_use}).")
            if not relevant_docs_final and num_initial_results > 0 : # Solo advertir si había resultados iniciales
                logger.warning(f"No se encontraron documentos específicos para la marca '{target_brand}' después del filtrado (de {num_initial_results} iniciales).")
        else:
            logger.info(f"Búsqueda RAG global (sin filtro de marca). Tomando hasta k={_k_final_to_use} resultados únicos.")
            unique_docs_global = []
            seen_content_global = set()
            for doc in initial_results:
                if doc.page_content not in seen_content_global:
                    unique_docs_global.append(doc)
                    seen_content_global.add(doc.page_content)
                if len(unique_docs_global) >= _k_final_to_use:
                    break
            relevant_docs_final = unique_docs_global

    except AttributeError as ae: 
        logger.error(f"AttributeError durante búsqueda RAG (¿retriever mal configurado o settings_instance es None?): {ae}", exc_info=True)
        relevant_docs_final = []
    except Exception as e_search:
        logger.error(f"Error inesperado durante la búsqueda RAG: {e_search}", exc_info=True)
        relevant_docs_final = []

    logger.info(f"Búsqueda RAG finalizó. Devolviendo {len(relevant_docs_final)} documentos.")
    return relevant_docs_final