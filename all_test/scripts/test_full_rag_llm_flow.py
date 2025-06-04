"""
Script para probar el flujo completo de RAG + LLM con el prompt optimizado.
Uso: python scripts/test_full_rag_llm_flow.py --query "pregunta de prueba" --brand "marca1"
"""
import argparse
import asyncio
import sys
from pathlib import Path
from typing import List, Optional

# Ajuste de rutas para importar módulos de la app
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT_DIR))

from app.core.config import settings
from app.ai.rag_retriever import load_rag_components, search_relevant_documents
from app.ai.prompt_builder import build_rag_prompt
from app.api.llm_client import get_llm_response

async def test_full_flow(query: str, brand: Optional[str] = None, k: int = 3):
    """
    Prueba el flujo completo de RAG + LLM con respuestas optimizadas por marca.
    
    Args:
        query: Consulta del usuario
        brand: Marca para filtrar documentos (opcional)
        k: Número de documentos a recuperar
    """
    print(f"\n=== PRUEBA DE FLUJO COMPLETO RAG + LLM ===")
    print(f"Query: '{query}'")
    print(f"Marca: '{brand or 'Todas'}'")
    print(f"Documentos a recuperar: {k}")
    
    # 1. Cargar componentes RAG
    print("\n[1] Cargando componentes RAG...")
    retriever = load_rag_components()
    if not retriever:
        print("❌ Error: No se pudo cargar el retriever. Verifica los logs para más detalles.")
        return None
    print(f"✅ Componentes cargados: {type(retriever).__name__}")
    
    # 2. Realizar búsqueda RAG
    print("\n[2] Realizando búsqueda RAG...")
    # Convertir el nombre de la marca al formato usado en el índice (minúsculas y con guiones bajos)
    normalized_brand = None
    if brand:
        normalized_brand = brand.lower().replace(" ", "_").replace("(", "").replace(")", "")
    print(f"  Usando nombre de marca normalizado: '{normalized_brand}'")
    
    docs = await search_relevant_documents(
        user_query=query,
        retriever_instance=retriever,
        target_brand=normalized_brand,
        k_final=k
    )
    
    if not docs:
        print("❌ No se encontraron documentos relevantes. Verificar el índice FAISS.")
        return None
    
    print(f"✅ Documentos encontrados: {len(docs)}")
    
    # 3. Construir contexto para el LLM
    print("\n[3] Construyendo contexto para el LLM...")
    context_chunks = []
    for i, doc in enumerate(docs):
        # Añadir información sobre la fuente
        source_info = f"Fuente: {doc.metadata.get('source', 'Desconocida')}"
        if 'brand' in doc.metadata:
            source_info += f" | Marca: {doc.metadata['brand']}"
            
        # Añadir fragmento de contenido
        context_chunks.append(f"--- Fragmento {i+1} ---\n{doc.page_content}\n{source_info}")
    
    # Unir los fragmentos en un solo contexto
    context = "\n\n".join(context_chunks)
    print(f"✅ Contexto construido ({len(context)} caracteres)")
    
    # 4. Construir prompt optimizado
    print("\n[4] Generando prompt optimizado...")
    prompt = build_rag_prompt(
        query=query,
        brand=brand or "Asistente Multimarca",
        context=context
    )
    print(f"✅ Prompt generado ({len(prompt)} caracteres)")
    
    # 5. Llamar al LLM
    print("\n[5] Enviando prompt al LLM...")
    response = await get_llm_response(prompt)
    
    # 6. Mostrar la respuesta
    print("\n=== RESPUESTA DEL LLM ===")
    print(response)
    
    return response

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Prueba del flujo completo RAG + LLM")
    parser.add_argument("--query", required=True, help="Consulta para buscar")
    parser.add_argument("--brand", help="Marca para filtrar (opcional)")
    parser.add_argument("--k", type=int, default=3, help="Número de documentos a recuperar")
    
    args = parser.parse_args()
    asyncio.run(test_full_flow(args.query, args.brand, args.k))
