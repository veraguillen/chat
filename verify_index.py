from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings  # Actualizado
import os

def verify_faiss_index(index_path, brand_name):
    embeddings = HuggingFaceEmbeddings(model_name="paraphrase-multilingual-mpnet-base-v2")
    try:
        vectorstore = FAISS.load_local(index_path, embeddings, allow_dangerous_deserialization=True)
        docs = vectorstore.similarity_search("test query", k=10, filter={"brand": brand_name})
        print(f"Documentos encontrados para {brand_name}: {len(docs)}")
        for doc in docs:
            print(f"Contenido: {doc.page_content[:100]}... | Metadatos: {doc.metadata}")
    except Exception as e:
        print(f"Error al cargar índice: {e}")

if __name__ == "__main__":
    index_path = "C:/Users/veram/OneDrive/Escritorio/chat/data/faiss_index_kb_spanish_v1"
    verify_faiss_index(index_path, "consultor_javier_bazan")