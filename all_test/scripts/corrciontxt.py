from pathlib import Path
import shutil
import os

def corregir_archivos_marcas(directorio_marcas):
    # 1. Reemplazar el archivo con problemas
    problema = Path(directorio_marcas) / "corporativo_ehecatl.txt"
    solucion = Path(directorio_marcas) / "corporativo_ehecatl_1.txt"
    
    if problema.exists() and solucion.exists():
        problema.unlink()  # Eliminar el archivo con problemas
        shutil.copy2(solucion, problema)  # Copiar la versión buena
        print(f"✅ Se corrigió: {problema.name}")
    
    # 2. Opcional: Dividir archivos de una sola línea en párrafos
    for archivo in Path(directorio_marcas).glob("*.txt"):
        if archivo.name == "corporativo_ehecatl_1.txt":
            continue  # Saltar el archivo de respaldo
            
        with open(archivo, 'r', encoding='utf-8') as f:
            contenido = f.read().strip()
        
        # Si está todo en una línea, intentar dividir por puntos
        if contenido.count('\n') == 0 and len(contenido.split()) > 50:
            contenido = contenido.replace('. ', '.\n\n')
            with open(archivo, 'w', encoding='utf-8') as f:
                f.write(contenido)
            print(f"📝 Se formateó: {archivo.name}")

if __name__ == "__main__":
    directorio_marcas = os.path.join(os.path.dirname(__file__), "..", "data", "brands")
    corregir_archivos_marcas(directorio_marcas)