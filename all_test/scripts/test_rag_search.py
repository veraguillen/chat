"""
Script para probar la funcionalidad del RAG con filtrado por marca.
Uso: python scripts/test_rag_search.py --query "pregunta de prueba" --brand "marca1"
"""
import argparse
import asyncio
import sys
from pathlib import Path

# Ajuste de rutas para importar módulos de la app
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT_DIR))

from app.core.config import settings
from app.ai.rag_retriever import load_rag_components, search_relevant_documents

async def test_rag_search(query, brand=None, k=3):
    """Prueba la búsqueda RAG con filtrado opcional por marca."""
    print(f"\n=== Prueba de Búsqueda RAG ===")
    print(f"Query: '{query}'")
    print(f"Marca: '{brand or 'Todas'}'")
    print(f"Documentos a recuperar: {k}")
    
    # Cargar componentes RAG
    print("\nCargando componentes RAG...")
    retriever = load_rag_components()
    if not retriever:
        print("Error: No se pudo cargar el retriever. Verifica los logs para más detalles.")
        return []
    print(f"Componentes cargados: {type(retriever).__name__}")
    
    # Realizar búsqueda
    print("\nRealizando búsqueda...")
    docs = await search_relevant_documents(
        user_query=query,
        retriever_instance=retriever,
        target_brand=brand,
        k_final=k
    )
    
    # Mostrar resultados
    print(f"\n=== Resultados ({len(docs)} documentos) ===")
    for i, doc in enumerate(docs):
        print(f"\nDocumento {i+1}:")
        print(f"ID: {getattr(doc, 'id', 'No disponible')}")
        print(f"Brand: {doc.metadata.get('brand', 'No disponible')}")
        print(f"Origen: {doc.metadata.get('source', 'No disponible')}")
        print(f"Contenido: {doc.page_content[:200]}...")
    
    return docs

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Prueba de búsqueda RAG")
    parser.add_argument("--query", required=True, help="Consulta para buscar")
    parser.add_argument("--brand", help="Marca para filtrar (opcional)")
    parser.add_argument("--k", type=int, default=3, help="Número de documentos a recuperar")
    
    args = parser.parse_args()
    asyncio.run(test_rag_search(args.query, args.brand, args.k))
