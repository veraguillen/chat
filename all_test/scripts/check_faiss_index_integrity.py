import os
from pathlib import Path
import pickle
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings
import sys
import json

# Ajuste de rutas para importar settings
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT_DIR))

# Configurar el entorno antes de importar settings
os.environ["SETTINGS_MODULE"] = "app.core.config"

try:
    from app.core.config import settings
    print("[OK] Settings importado correctamente.")
except ImportError as e:
    print(f"[ERROR] No se pudo importar settings: {e}")
    print(f"Python path: {sys.path}")
    sys.exit(1)

FAISS_FOLDER_PATH = Path(settings.FAISS_FOLDER_PATH)
FAISS_INDEX_NAME = settings.FAISS_INDEX_NAME

index_faiss_path = FAISS_FOLDER_PATH / f"{FAISS_INDEX_NAME}.faiss"
index_pkl_path = FAISS_FOLDER_PATH / f"{FAISS_INDEX_NAME}.pkl"

print(f"\n=== Verificando rutas y archivos del índice FAISS ===")
print(f"FAISS_FOLDER_PATH: {FAISS_FOLDER_PATH}")
print(f"FAISS_INDEX_NAME: {FAISS_INDEX_NAME}")
print(f"index.faiss: {index_faiss_path}")
print(f"index.pkl: {index_pkl_path}")

# 1. Comprobar existencia de carpeta y archivos
if not FAISS_FOLDER_PATH.exists():
    print(f"[ERROR] La carpeta del índice FAISS no existe: {FAISS_FOLDER_PATH}")
    sys.exit(1)

if not index_faiss_path.exists():
    print(f"[ERROR] No se encuentra el archivo: {index_faiss_path}")
else:
    print(f"[OK] Archivo encontrado: {index_faiss_path}")

if not index_pkl_path.exists():
    print(f"[ERROR] No se encuentra el archivo: {index_pkl_path}")
    sys.exit(1)
else:
    print(f"[OK] Archivo encontrado: {index_pkl_path}")

# 2. Cargar el índice FAISS usando LangChain
print("\n=== Cargando índice FAISS con LangChain ===")
faiss_index = None # Initialize faiss_index to None
try:
    print(f"Modelo de embeddings a utilizar: {settings.EMBEDDING_MODEL_NAME}")
    # Determinar el dispositivo para los embeddings
    embedding_device = getattr(settings, 'EMBEDDING_DEVICE', 'cpu')
    model_kwargs = {'device': embedding_device}
    # encode_kwargs = {'normalize_embeddings': True} # Opcional, si se usó durante la creación

    embeddings_model = HuggingFaceEmbeddings(
        model_name=settings.EMBEDDING_MODEL_NAME,
        model_kwargs=model_kwargs,
        # encode_kwargs=encode_kwargs # Descomentar si es necesario
    )
    print(f"Embeddings inicializados en dispositivo: '{embedding_device}'")

    faiss_index = FAISS.load_local(
        folder_path=str(FAISS_FOLDER_PATH),
        embeddings=embeddings_model,
        index_name=FAISS_INDEX_NAME,
        allow_dangerous_deserialization=True
    )
    print("[OK] Índice FAISS cargado exitosamente usando LangChain.")
    print(f"Tipo del índice: {type(faiss_index)}")
    if hasattr(faiss_index, 'index') and faiss_index.index:
        print(f"  Número total de vectores en el índice: {faiss_index.index.ntotal}")
    if hasattr(faiss_index, 'docstore') and hasattr(faiss_index.docstore, '_dict'):
        print(f"  Número de documentos en el docstore: {len(faiss_index.docstore._dict)}")
    else:
        print("[ADVERTENCIA] No se pudo acceder al docstore o a su diccionario interno.")

except Exception as e:
    print(f"[ERROR] No se pudo cargar el índice FAISS con LangChain: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 3. Extraer documentos de la estructura FAISS
print("\n=== Extrayendo documentos del índice FAISS ===")
try:
    docs = []
    doc_count = 0

    if faiss_index and hasattr(faiss_index, 'docstore') and hasattr(faiss_index.docstore, '_dict'):
        docs = list(faiss_index.docstore._dict.values())
        doc_count = len(docs)
        print(f"Extracción exitosa: {doc_count} documentos encontrados desde faiss_index.docstore.")
    elif not faiss_index:
        print("[ERROR] El objeto faiss_index no está disponible (falló la carga?). No se pueden analizar documentos.")
    else:
        print("[ERROR] No se pudo acceder a faiss_index.docstore._dict. No se pueden analizar documentos.")
        # docs lista vacía, el siguiente if no se ejecutará o mostrará 0.
    
    # Análisis estadístico de los documentos
    if docs:
        print("\n=== Análisis de documentos ===")
        doc_types = set()
        docs_with_content = 0
        docs_with_brand = 0
        docs_complete = 0
        brands = set()
        
        for doc in docs:
            # Obtener atributos del documento
            metadata = getattr(doc, 'metadata', {})
            content = getattr(doc, 'page_content', '')
            
            # Verificar contenido
            has_content = bool(content and len(content.strip()) > 10)
            if has_content:
                docs_with_content += 1
            
            # Verificar metadatos
            if metadata.get('doc_type'):
                doc_types.add(metadata.get('doc_type'))
            
            # Verificar campo brand
            if metadata.get('brand'):
                docs_with_brand += 1
                brands.add(metadata.get('brand'))
            
            # Documentos completos
            if has_content and metadata.get('brand'):
                docs_complete += 1
        
        # Mostrar resultados estadísticos
        print(f"Total de documentos: {doc_count}")
        print(f"Documentos con contenido válido: {docs_with_content} ({docs_with_content/doc_count*100:.1f}%)")
        print(f"Documentos con campo 'brand': {docs_with_brand} ({docs_with_brand/doc_count*100:.1f}%)")
        print(f"Documentos completos (brand + contenido): {docs_complete} ({docs_complete/doc_count*100:.1f}%)")
        print(f"Tipos de documento: {', '.join(doc_types)}")
        print(f"Marcas encontradas ({len(brands)}): {', '.join(sorted(brands)[:10])}{'...' if len(brands) > 10 else ''}")
        
        # Evaluación final
        if docs_complete == doc_count:
            print("\n[EXCELENTE] Todos los documentos tienen brand y contenido válido.")
        elif docs_complete >= doc_count * 0.9:
            print(f"\n[BUENO] {docs_complete}/{doc_count} documentos completos (más del 90%).")
        else:
            print(f"\n[ATENCIÓN] Solo {docs_complete}/{doc_count} documentos están completos ({docs_complete/doc_count*100:.1f}%).")
        
        # Mostrar algunos ejemplos
        print("\n=== Ejemplos de documentos ===")
        for i, doc in enumerate(docs[:3]):
            print(f"\nDocumento {i+1}:")
            doc_id = getattr(doc, 'id', 'No disponible')
            page_content = getattr(doc, 'page_content', 'Sin contenido')
            metadata = getattr(doc, 'metadata', {})
            
            print(f"ID: {doc_id}")
            print(f"Contenido: {str(page_content)[:200]}...")
            print("Metadatos:")
            for key, value in metadata.items():
                print(f"  - {key}: {value}")
            
            # Verificar campos clave
            if 'brand' not in metadata:
                print("  [ADVERTENCIA] Este documento NO tiene el campo 'brand' en los metadatos")
            else:
                print(f"  [OK] Brand encontrado: {metadata['brand']}")
    
except Exception as e:
    print(f"[ERROR] Error al extraer documentos: {e}")
    import traceback
    traceback.print_exc()

print("\n=== Fin del análisis ===")