import os
import logging
from pathlib import Path
from typing import List, Optional, Any

# Langchain y FAISS imports
try:
    from langchain_huggingface import HuggingFaceEmbeddings
    from langchain_community.vectorstores import FAISS
    from langchain.schema import Document as LangchainDocument # Usar el alias si hay conflicto
    from langchain_core.vectorstores import VectorStoreRetriever
    LANGCHAIN_OK = True
except ImportError:
    # Este logging básico se activará si las importaciones fallan ANTES de que el logger de la app se configure
    logging.basicConfig(level=logging.ERROR)
    logging.error("Faltan librerías de Langchain/FAISS (langchain-huggingface, langchain-community, faiss-cpu/gpu). RAG no funcionará.")
    LANGCHAIN_OK = False
    # Definir clases dummy para que el resto del archivo no falle en la definición si no se importan
    class HuggingFaceEmbeddings: pass
    class FAISS: pass
    class LangchainDocument: pass
    class VectorStoreRetriever: pass

import asyncio

# Importar configuración y logger de forma segura
try:
    from app.core.config import settings # Importar la instancia de settings
    CONFIG_LOADED = True if settings else False
except ImportError as e:
    if not LANGCHAIN_OK: # Si ya falló Langchain, este es un error secundario
        logging.error(f"FALLO AL IMPORTAR CONFIGURACIÓN en rag_retriever.py (además de Langchain): {e}")
    else: # Si Langchain estaba OK, este es el error primario
        logging.basicConfig(level=logging.ERROR)
        logging.error(f"FALLO CRÍTICO AL IMPORTAR CONFIGURACIÓN en rag_retriever.py: {e}")
    settings = None # Asegurar que settings sea None
    CONFIG_LOADED = False

try:
    from app.utils.logger import logger # Asumiendo que tienes un logger centralizado
except ImportError:
    # Fallback logger si el logger de la app no está disponible (ej. si se ejecuta standalone)
    logger = logging.getLogger("rag_retriever_fallback")
    if not logger.hasHandlers(): # Configurar solo si no tiene handlers (para evitar duplicados)
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    logger.warning("Usando logger fallback en rag_retriever.")


def load_rag_components() -> Optional[VectorStoreRetriever]:
    """
    Carga el modelo de embeddings y el índice FAISS desde el disco.
    Devuelve una instancia del VectorStoreRetriever configurado o None si falla.
    Esta función es SÍNCRONA.
    """
    if not LANGCHAIN_OK:
        logger.critical("Faltan librerías Langchain/FAISS. No se pueden cargar componentes RAG.")
        return None
    if not CONFIG_LOADED or not settings:
        logger.critical("Configuración (settings) no disponible. No se pueden cargar componentes RAG.")
        return None

    # --- Obtener rutas y nombres correctos desde settings ---
    faiss_folder_str = str(settings.faiss_folder_path) # Carpeta del índice, como string
    
    # Langchain FAISS usa "index" como nombre base por defecto si solo se da folder_path en save_local.
    # Usamos el valor de settings, asegurando que sea "index" si es el comportamiento por defecto.
    faiss_base_name = settings.faiss_index_name # Debería ser "index" si vectorize_data.py no especifica un nombre al guardar

    # ¡¡¡CORRECCIÓN CRÍTICA: Usar el modelo de embeddings desde settings!!!
    embedding_model_name_from_settings = settings.embedding_model_name
    
    rag_k_default = settings.rag_default_k
    k_fetch_multiplier = 2 # Cuántas veces más que k_final buscar inicialmente (para tener margen para filtrar)
    k_to_fetch_initially = rag_k_default * k_fetch_multiplier

    if not faiss_folder_str or not faiss_base_name:
        logger.critical(f"Configuración de FAISS incompleta: faiss_folder_path='{faiss_folder_str}', faiss_index_name='{faiss_base_name}'.")
        return None
    
    if not embedding_model_name_from_settings:
        logger.critical("embedding_model_name no está configurado en settings.")
        return None

    embedding_model_instance: Optional[HuggingFaceEmbeddings] = None
    vector_store_instance: Optional[FAISS] = None

    try:
        # 1. Cargar Modelo de Embeddings
        logger.info(f"Cargando modelo de embeddings desde settings: {embedding_model_name_from_settings}")
        # Forzar CPU por consistencia, a menos que tengas una gestión de GPU robusta
        device_to_use = 'cpu'
        embedding_model_instance = HuggingFaceEmbeddings(
            model_name=embedding_model_name_from_settings,
            model_kwargs={'device': device_to_use},
            # encode_kwargs={'normalize_embeddings': True} # La normalización ya se hace en vectorize_data.py
                                                         # y FAISS maneja la normalización interna para IP (producto interno).
                                                         # Si usas similitud coseno explícitamente, la normalización es buena.
                                                         # Para FAISS con IndexFlatIP, los vectores deben ser normalizados ANTES de añadir.
                                                         # El script de vectorización ya lo hace.
        )
        logger.info(f"Modelo de embeddings '{embedding_model_name_from_settings}' inicializado en '{device_to_use}'.")

        # 2. Cargar Índice FAISS
        logger.info(f"Cargando índice FAISS: Carpeta='{faiss_folder_str}', Nombre Base='{faiss_base_name}'")
        if not os.path.isdir(faiss_folder_str): # Verificar que la CARPETA exista
            logger.critical(f"Directorio del índice FAISS NO ENCONTRADO: {faiss_folder_str}.")
            return None
        
        # Verificar que los archivos específicos (index.faiss o [name].faiss) existan
        expected_faiss_file = Path(faiss_folder_str) / f"{faiss_base_name}.faiss"
        expected_pkl_file = Path(faiss_folder_str) / f"{faiss_base_name}.pkl"
        if not expected_faiss_file.is_file() or not expected_pkl_file.is_file():
            logger.critical(f"Archivos de índice FAISS no encontrados en '{faiss_folder_str}'. Se esperaba '{expected_faiss_file.name}' y '{expected_pkl_file.name}'.")
            logger.info("Asegúrate de haber ejecutado vectorize_data.py y que settings.faiss_index_name coincida.")
            return None

        vector_store_instance = FAISS.load_local(
            folder_path=faiss_folder_str,
            index_name=faiss_base_name, # Este es el nombre base de los archivos .faiss y .pkl
            embeddings=embedding_model_instance,
            allow_dangerous_deserialization=True # Necesario para cargar archivos .pkl de Langchain
        )
        logger.info(f"Índice FAISS '{faiss_base_name}' cargado exitosamente desde '{faiss_folder_str}'.")
        logger.info(f"Número total de vectores en el índice cargado: {vector_store_instance.index.ntotal}")


        # 3. Crear y Devolver el Retriever
        retriever_instance = vector_store_instance.as_retriever(
            search_type="similarity", # Puedes especificar "mmr" para Max Marginal Relevance si quieres diversidad
            search_kwargs={'k': k_to_fetch_initially}
        )
        logger.info(f"Retriever FAISS creado. k (búsqueda inicial) = {k_to_fetch_initially}.")
        return retriever_instance

    except ImportError as e_imp: # Aunque ya hay un check de LANGCHAIN_OK, por si acaso.
        logger.critical(f"Error de importación (¿FAISS o sentence-transformers instalados?) cargando RAG: {e_imp}", exc_info=True)
        return None
    except FileNotFoundError as e_fnf: # Debería ser capturado por el check de is_dir/is_file ahora.
        logger.critical(f"No se encontró archivo/directorio FAISS: {e_fnf}", exc_info=True)
        return None
    except RuntimeError as e_rt:
        if "could not open" in str(e_rt).lower() and ".faiss" in str(e_rt).lower():
            logger.critical(f"Error FAISS: No se pudo abrir '{faiss_base_name}.faiss' en '{faiss_folder_str}'. Verifica nombre, existencia y permisos.", exc_info=False)
        else:
            logger.critical(f"RuntimeError inesperado cargando componentes RAG: {e_rt}", exc_info=True)
        return None
    except Exception as e:
        logger.critical(f"Error CRÍTICO general cargando componentes RAG: {e}", exc_info=True)
        return None

# --- Función de Búsqueda ---
async def search_relevant_documents(
    retriever_instance: VectorStoreRetriever,
    user_query: str,
    target_brand: Optional[str] = None, # Espera el nombre de marca NORMALIZADO
    k_final: Optional[int] = None
) -> List[LangchainDocument]:
    """
    Busca documentos usando el retriever. Ejecuta búsqueda síncrona en un thread separado.
    Filtra por marca si se especifica (Post-Filtrado).
    """
    if not LANGCHAIN_OK or retriever_instance is None:
        logger.error("Intento de búsqueda RAG con retriever_instance=None o Langchain no disponible.")
        return []

    # Usar k_final de settings si no se provee, o un default
    final_k_to_return = k_final if k_final is not None else (settings.rag_default_k if settings else 3)

    relevant_docs_final: List[LangchainDocument] = []
    try:
        # El k para el retriever ya está configurado en load_rag_components (k_to_fetch_initially)
        # retriever_instance.search_kwargs['k'] podría usarse para cambiarlo dinámicamente si fuera necesario
        k_retriever_configured = retriever_instance.search_kwargs.get('k', final_k_to_return * 2)
        logger.debug(f"Ejecutando retriever.get_relevant_documents (k configurado={k_retriever_configured}) para query: '{user_query[:70]}...'")

        # Ejecutar la búsqueda síncrona en un thread para no bloquear el bucle de eventos de FastAPI
        initial_results: List[LangchainDocument] = await asyncio.to_thread(
            retriever_instance.get_relevant_documents, # Este es el método correcto
            query=user_query
        )
        num_initial_results = len(initial_results)
        logger.info(f"Retriever devolvió {num_initial_results} documentos iniciales.")

        if not initial_results:
            logger.info("La búsqueda inicial no devolvió documentos.")
            return []

        if target_brand:
            logger.info(f"Filtrando {num_initial_results} resultados por marca normalizada: '{target_brand}'...")
            filtered_docs_for_brand = []
            # Para evitar duplicados exactos de page_content dentro de los resultados filtrados por marca
            # Útil si el mismo chunk es relevante por múltiples razones pero solo queremos mostrarlo una vez para la marca
            seen_content_for_brand = set() 
            
            for doc in initial_results:
                # Asumimos que 'brand' en metadata es el nombre normalizado (ej. 'consultor_javier_bazan')
                doc_brand_metadata = doc.metadata.get('brand')
                
                if doc_brand_metadata == target_brand:
                    # Solo añadir si el contenido no se ha visto ya para esta marca y consulta
                    if doc.page_content not in seen_content_for_brand:
                        filtered_docs_for_brand.append(doc)
                        seen_content_for_brand.add(doc.page_content)
                    else:
                        logger.debug(f"Chunk con contenido duplicado omitido para marca '{target_brand}'. Source: {doc.metadata.get('source')}")
                
                # Detenerse si ya hemos recolectado suficientes para k_final
                if len(filtered_docs_for_brand) >= final_k_to_return:
                    break
            
            relevant_docs_final = filtered_docs_for_brand
            logger.info(f"Filtrado por marca: {len(relevant_docs_final)} documentos para '{target_brand}' (objetivo k={final_k_to_return}).")
            if not relevant_docs_final:
                logger.warning(f"No se encontraron documentos específicos para la marca '{target_brand}' después del filtrado.")
        else:
            # Si no hay target_brand, tomar los primeros k_final resultados únicos
            logger.info(f"Búsqueda RAG global (sin filtro de marca). Tomando hasta k={final_k_to_return} resultados únicos.")
            unique_docs_global = []
            seen_content_global = set()
            for doc in initial_results:
                if doc.page_content not in seen_content_global:
                    unique_docs_global.append(doc)
                    seen_content_global.add(doc.page_content)
                if len(unique_docs_global) >= final_k_to_return:
                    break
            relevant_docs_final = unique_docs_global

    except AttributeError as ae: # Por ejemplo, si retriever_instance no tiene search_kwargs
        logger.error(f"AttributeError durante búsqueda RAG (¿retriever mal configurado?): {ae}", exc_info=True)
        relevant_docs_final = []
    except Exception as e_search:
        logger.error(f"Error inesperado durante la búsqueda RAG: {e_search}", exc_info=True)
        relevant_docs_final = []

    logger.info(f"Búsqueda finalizó. Devolviendo {len(relevant_docs_final)} documentos.")
    return relevant_docs_final