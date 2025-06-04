import pickle
import os
from langchain_core.documents import Document # Solo si tus objetos en el docstore son de este tipo explícito

# --- FUNCIÓN PARA INSPECCIONAR TODOS LOS METADATOS DEL PKL ---
def inspect_raw_pkl_metadata(pkl_file_path):
    print(f"\n--- Inspeccionando contenido CRUDO de metadatos del archivo: {pkl_file_path} ---")
    print("Se imprimirán los metadatos de TODOS los documentos tal como están en el .pkl.")
    
    try:
        with open(pkl_file_path, "rb") as f:
            loaded_object_from_pkl = pickle.load(f)
        
        docstore_to_inspect = None
        object_type_info = f"Tipo del objeto principal cargado desde .pkl: {type(loaded_object_from_pkl)}"

        # Intentar acceder al docstore (diccionario de documentos)
        if isinstance(loaded_object_from_pkl, dict):
            docstore_to_inspect = loaded_object_from_pkl
            object_type_info += "\n  El objeto .pkl es un diccionario (probablemente el docstore directamente)."
        elif isinstance(loaded_object_from_pkl, tuple) and len(loaded_object_from_pkl) == 2:
            # Común en FAISS.load_local, donde el segundo elemento es el docstore
            potential_docstore = loaded_object_from_pkl[1]
            if isinstance(potential_docstore, dict):
                docstore_to_inspect = potential_docstore
                object_type_info += "\n  El objeto .pkl es una tupla; el segundo elemento es un diccionario (probablemente el docstore)."
            else:
                object_type_info += f"\n  El objeto .pkl es una tupla, pero el segundo elemento no es un diccionario (es tipo: {type(potential_docstore)}). Se intentará inspeccionar si tiene '_dict' o 'data'."
                if hasattr(potential_docstore, '_dict') and isinstance(potential_docstore._dict, dict):
                    docstore_to_inspect = potential_docstore._dict
                    object_type_info += "\n    Se accedió al docstore via ._dict del segundo elemento de la tupla."
                elif hasattr(potential_docstore, 'data') and isinstance(potential_docstore.data, dict): # Para InMemoryDocstore
                    docstore_to_inspect = potential_docstore.data
                    object_type_info += f"\n    Se accedió al docstore via .data del segundo elemento de la tupla."

        elif hasattr(loaded_object_from_pkl, 'docstore'): # Si el objeto cargado tiene un atributo docstore
            docstore_attr = loaded_object_from_pkl.docstore
            object_type_info += f"\n  El objeto .pkl tiene un atributo 'docstore' de tipo: {type(docstore_attr)}"
            if hasattr(docstore_attr, '_dict') and isinstance(docstore_attr._dict, dict):
                docstore_to_inspect = docstore_attr._dict
                object_type_info += "\n    Se accedió al docstore a través de 'objeto.docstore._dict'."
            elif isinstance(docstore_attr, dict):
                docstore_to_inspect = docstore_attr
                object_type_info += "\n    El atributo 'docstore' es un diccionario."
            elif hasattr(docstore_attr, 'data') and isinstance(docstore_attr.data, dict): # Para InMemoryDocstore
                 docstore_to_inspect = docstore_attr.data
                 object_type_info += f"\n    El atributo 'docstore' tiene un '.data' que es un diccionario."
        
        print(object_type_info)

        if docstore_to_inspect:
            print(f"\n--- Metadatos de los {len(docstore_to_inspect)} Documentos Encontrados ---")
            
            for i, (doc_id, document_obj) in enumerate(docstore_to_inspect.items()):
                metadata_info = "Metadatos no extraídos o formato incorrecto"
                page_content_preview = "Contenido no extraído o formato incorrecto"

                if isinstance(document_obj, Document): # Objeto Document de LangChain
                    metadata_info = document_obj.metadata
                    page_content_preview = document_obj.page_content[:100] + "..." if document_obj.page_content else "(Sin contenido)"
                elif isinstance(document_obj, dict): # A veces los documentos son solo diccionarios
                    metadata_info = document_obj.get('metadata', {'error': 'metadata key not found in dict'})
                    page_content_preview = document_obj.get('page_content', '(page_content key not found)')[:100] + "..."
                else:
                    # Si no es ni Document ni dict, intenta obtener metadata si existe el atributo
                    if hasattr(document_obj, 'metadata'):
                        metadata_info = document_obj.metadata
                    if hasattr(document_obj, 'page_content'):
                         page_content_preview = document_obj.page_content[:100] + "..." if document_obj.page_content else "(Sin contenido)"

                print(f"\n  Documento #{i+1} (ID Interno en PKL: {doc_id})")
                print(f"    Contenido (preview): {page_content_preview}")
                print(f"    METADATOS COMPLETOS: {metadata_info}")
                if isinstance(metadata_info, dict) and 'brand' in metadata_info:
                    print(f"    >>>> VALOR DE 'brand' EN METADATOS: '{metadata_info['brand']}' <<<<")
                elif isinstance(metadata_info, dict):
                    print(f"    >>>> ALERTA: La clave 'brand' NO está presente en estos metadatos. Claves disponibles: {list(metadata_info.keys())} <<<<")
                else:
                    print(f"    >>>> ALERTA: No se pudieron extraer metadatos como diccionario para este documento. Tipo: {type(metadata_info)} <<<<")

            print("\n--- Fin de la inspección de metadatos ---")
            print("Busca en la lista de arriba los documentos para cada una de tus marcas (puedes guiarte por 'Source' o 'Content Preview').")
            print("Anota el VALOR EXACTO que tiene la clave 'brand' para cada una.")

        else:
            print("\nNo se pudo acceder al docstore (diccionario de documentos) del archivo .pkl con los métodos probados.")
            print("El objeto cargado podría tener una estructura diferente a la esperada por LangChain FAISS .pkl.")
            print("Intenta imprimir 'loaded_object_from_pkl' o 'dir(loaded_object_from_pkl)' para investigar más su estructura.")

    except FileNotFoundError:
        print(f"ERROR: El archivo {pkl_file_path} no fue encontrado.")
    except Exception as e:
        print(f"ERROR al inspeccionar {pkl_file_path}: {e}")
        import traceback
        traceback.print_exc()

# --- SCRIPT PRINCIPAL DE EJECUCIÓN ---
if __name__ == "__main__":
    # Ruta a la CARPETA que contiene index.faiss e index.pkl
    faiss_index_folder_path = "C:/Users/veram/OneDrive/Escritorio/chat/data/faiss_index_kb_spanish_v1"
    # Ruta completa al archivo index.pkl
    pkl_file_path_to_inspect = os.path.join(faiss_index_folder_path, "index.pkl")

    print("Iniciando script de inspección cruda de 'index.pkl'...\n")

    if not os.path.isfile(pkl_file_path_to_inspect):
        print(f"ERROR CRÍTICO: Archivo 'index.pkl' no encontrado en la ruta especificada: '{pkl_file_path_to_inspect}'")
        print("Asegúrate de que la ruta es correcta y que el archivo existe.")
    else:
        inspect_raw_pkl_metadata(pkl_file_path_to_inspect)

    print("\n--- Script de inspección finalizado ---")