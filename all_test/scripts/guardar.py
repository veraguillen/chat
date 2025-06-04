import os
from pathlib import Path
import chardet

def analizar_archivos_marcas(directorio_marcas):
    print(f"=== Análisis de archivos en: {directorio_marcas} ===")
    
    # Listar todos los archivos .txt en el directorio y subdirectorios
    archivos_txt = list(Path(directorio_marcas).rglob("*.txt"))
    
    if not archivos_txt:
        print("No se encontraron archivos .txt en el directorio especificado.")
        return
    
    print(f"\nSe encontraron {len(archivos_txt)} archivos .txt")
    
    for archivo in archivos_txt:
        print(f"\n{'='*80}")
        print(f"📄 Archivo: {archivo.relative_to(directorio_marcas)}")
        print(f"📏 Tamaño: {archivo.stat().st_size} bytes")
        
        # Leer el archivo en modo binario para detectar la codificación
        with open(archivo, 'rb') as f:
            raw_data = f.read()
            
        # Detectar la codificación
        deteccion = chardet.detect(raw_data)
        print(f"🔍 Codificación detectada: {deteccion['encoding']} (confianza: {deteccion['confidence']:.1%})")
        
        # Intentar leer con la codificación detectada
        try:
            # Primero con la codificación detectada
            contenido = raw_data.decode(deteccion['encoding'] if deteccion['encoding'] else 'utf-8')
            
            # Contar líneas y palabras
            lineas = contenido.splitlines()
            palabras = sum(len(linea.split()) for linea in lineas)
            
            print(f"📊 Estadísticas:")
            print(f"   - Líneas: {len(lineas)}")
            print(f"   - Palabras: {palabras}")
            print(f"   - Caracteres: {len(contenido)}")
            
            # Mostrar caracteres no ASCII
            caracteres_especiales = set(c for c in contenido if ord(c) > 127)
            if caracteres_especiales:
                print("🔤 Caracteres especiales encontrados:")
                for c in sorted(caracteres_especiales):
                    print(f"   - '{c}' (U+{ord(c):04X})")
            
            # Mostrar las primeras 3 líneas
            print("\n📝 Contenido de muestra:")
            for i, linea in enumerate(lineas[:3]):
                print(f"   {i+1}. {linea[:100]}{'...' if len(linea) > 100 else ''}")
            
        except Exception as e:
            print(f"❌ Error al leer el archivo: {e}")
            # Intentar con UTF-8
            try:
                contenido = raw_data.decode('utf-8')
                print("✅ Se pudo leer con UTF-8 en el segundo intento")
            except:
                # Intentar con latin-1 como último recurso
                try:
                    contenido = raw_data.decode('latin-1')
                    print("⚠️  Se pudo leer con latin-1 (puede haber problemas con caracteres especiales)")
                except Exception as e2:
                    print(f"❌ No se pudo leer el archivo: {e2}")

# Ruta al directorio de marcas
directorio_marcas = os.path.join(os.path.dirname(__file__), "..", "data", "brands")

if __name__ == "__main__":
    if not os.path.exists(directorio_marcas):
        print(f"El directorio no existe: {directorio_marcas}")
        print("Directorio actual:", os.getcwd())
    else:
        analizar_archivos_marcas(directorio_marcas)