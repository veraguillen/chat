import pickle
import os
import sys
from collections import defaultdict
from pathlib import Path

def analyze_faiss_structure(pkl_file_path):
    """
    Analiza la estructura de los documentos en el archivo .pkl del índice FAISS.
    Agrupa los documentos por marca y muestra estadísticas detalladas.
    """
    print(f"\nAnalizando estructura de documentos en: {pkl_file_path}")
    
    try:
        # Cargar el archivo .pkl
        with open(pkl_file_path, "rb") as f:
            loaded_object = pickle.load(f)
        
        # Inicializar contenedores para análisis
        brands = defaultdict(list)
        docs_without_brand = []
        metadata_fields = set()
        content_stats = {"empty": 0, "with_content": 0}
        
        # Función para procesar documentos
        def process_documents(docstore):
            for doc_id, doc in docstore.items():
                metadata = {}
                content = ""
                
                # Extraer metadatos y contenido según el tipo de objeto
                if hasattr(doc, 'metadata') and hasattr(doc, 'page_content'):
                    metadata = getattr(doc, 'metadata', {})
                    content = getattr(doc, 'page_content', '')
                elif isinstance(doc, dict):
                    metadata = doc.get('metadata', {})
                    content = doc.get('page_content', '')
                
                # Actualizar campos de metadatos encontrados
                metadata_fields.update(metadata.keys())
                
                # Estadísticas de contenido
                if content and content.strip():
                    content_stats["with_content"] += 1
                else:
                    content_stats["empty"] += 1
                
                # Agrupar por marca o sin marca
                brand = metadata.get('brand', 'SIN_MARCA')
                brands[brand].append({
                    'id': doc_id,
                    'content_preview': content[:100] + ('...' if len(content) > 100 else ''),
                    'content_length': len(content),
                    'metadata': metadata
                })
        
        # Procesar según la estructura del objeto cargado
        print("\n🔍 ESTRUCTURA DEL OBJETO CARGADO:")
        if isinstance(loaded_object, dict):
            print("  Tipo: Diccionario simple")
            process_documents(loaded_object)
        elif isinstance(loaded_object, tuple) and len(loaded_object) >= 2:
            # Caso típico: (FAISS index, docstore)
            print(f"  Tipo: Tupla de {len(loaded_object)} elementos")
            print(f"  Elemento 0: {type(loaded_object[0]).__name__}")
            print(f"  Elemento 1: {type(loaded_object[1]).__name__}")
            
            docstore = loaded_object[1]
            if hasattr(docstore, '_dict'):  # Docstore de LangChain
                print("  Estructura: FAISS index + Docstore con _dict")
                process_documents(docstore._dict)
            elif hasattr(docstore, 'data'):  # InMemoryDocstore
                print("  Estructura: FAISS index + InMemoryDocstore")
                process_documents(docstore.data)
            elif isinstance(docstore, dict):
                print("  Estructura: FAISS index + Diccionario")
                process_documents(docstore)
            else:
                print(f"  ⚠️ Estructura de docstore no reconocida: {type(docstore)}")
        else:
            print(f"  ⚠️ Estructura no reconocida: {type(loaded_object)}")
        
        # Mostrar resultados del análisis
        print("\n" + "="*80)
        print("ANÁLISIS DE ESTRUCTURA DE DOCUMENTOS")
        print("="*80)
        
        # 1. Estadísticas generales
        print(f"\n📊 ESTADÍSTICAS GENERALES")
        total_docs = sum(len(docs) for docs in brands.values())
        print(f"  - Documentos totales: {total_docs}")
        print(f"  - Marcas únicas: {len(brands)}")
        print(f"  - Documentos con contenido: {content_stats['with_content']} ({content_stats['with_content']/total_docs*100:.1f}%)")
        print(f"  - Documentos vacíos: {content_stats['empty']} ({content_stats['empty']/total_docs*100:.1f}%)")
        print(f"  - Campos de metadatos encontrados: {', '.join(metadata_fields) or 'Ninguno'}")
        
        # 2. Documentos por marca
        print("\n🏷️  DOCUMENTOS POR MARCA")
        for brand, docs in sorted(brands.items(), key=lambda x: (-len(x[1]), x[0])):
            print(f"\n  🔹 {brand} ({len(docs)} documentos)")
            
            # Mostrar un ejemplo de los primeros 3 documentos
            for i, doc in enumerate(docs[:3], 1):
                print(f"     {i}. ID: {doc['id']}")
                print(f"        Contenido ({doc['content_length']} caracteres): {doc['content_preview']}")
                if doc['metadata']:
                    print(f"        Metadatos: {doc['metadata']}")
            
            if len(docs) > 3:
                print(f"     ... y {len(docs) - 3} documentos más")
        
        # 3. Documentos sin marca
        if 'SIN_MARCA' in brands:
            print(f"\n⚠️  {len(brands['SIN_MARCA'])} documentos sin marca asignada")
        
        # 4. Información del archivo
        file_stats = os.stat(pkl_file_path)
        print(f"\n📁 INFORMACIÓN DEL ARCHIVO")
        print(f"  - Tamaño: {file_stats.st_size / 1024:.2f} KB")
        print(f"  - Última modificación: {os.path.getmtime(pkl_file_path)}")
        
        print("\n" + "="*80)
        
    except Exception as e:
        print(f"\n❌ Error al analizar el archivo: {e}")
        import traceback
        traceback.print_exc()

def check_faiss_files(faiss_folder):
    """Verifica los archivos del índice FAISS"""
    print(f"\n🔍 VERIFICANDO ARCHIVOS EN: {faiss_folder}")
    
    faiss_file = os.path.join(faiss_folder, "index.faiss")
    pkl_file = os.path.join(faiss_folder, "index.pkl")
    
    files_status = []
    
    # Verificar index.faiss
    if os.path.isfile(faiss_file):
        size_kb = os.path.getsize(faiss_file) / 1024
        mod_time = os.path.getmtime(faiss_file)
        files_status.append(f"  ✅ index.faiss - Tamaño: {size_kb:.2f} KB - Modificado: {mod_time}")
    else:
        files_status.append("  ❌ index.faiss - No encontrado")
    
    # Verificar index.pkl
    if os.path.isfile(pkl_file):
        size_kb = os.path.getsize(pkl_file) / 1024
        mod_time = os.path.getmtime(pkl_file)
        files_status.append(f"  ✅ index.pkl - Tamaño: {size_kb:.2f} KB - Modificado: {mod_time}")
    else:
        files_status.append("  ❌ index.pkl - No encontrado")
    
    for status in files_status:
        print(status)
    
    return os.path.isfile(pkl_file), pkl_file

if __name__ == "__main__":
    # Ruta al archivo index.pkl
    faiss_index_folder = "C:/Users/veram/OneDrive/Escritorio/chat/data/faiss_index_kb_spanish_v1"
    
    # Verificar archivos
    pkl_exists, pkl_file = check_faiss_files(faiss_index_folder)
    
    if pkl_exists:
        analyze_faiss_structure(pkl_file)
    else:
        print(f"❌ Archivo no encontrado: {pkl_file}")
        print("Asegúrate de que la ruta al archivo index.pkl es correcta.")
